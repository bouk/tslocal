import * as http from "node:http";
import { describe, expect, it, beforeAll, afterAll } from "vitest";
import { LocalClient } from "../src/client.js";
import {
  AccessDeniedError,
  HttpError,
  PeerNotFoundError,
  PreconditionsFailedError,
} from "../src/errors.js";

let server: http.Server;
let port: number;
let responses: Record<string, { status: number; body: unknown; method?: string }> = {};
let lastRequestBody: string | undefined;
let lastRequestMethod: string | undefined;
let lastRequestUrl: string | undefined;

beforeAll(
  () =>
    new Promise<void>((resolve) => {
      server = http.createServer((req, res) => {
        // Verify required headers
        expect(req.headers["tailscale-cap"]).toBe("131");
        expect(req.headers["host"]).toBe("local-tailscaled.sock");

        lastRequestMethod = req.method;
        lastRequestUrl = req.url;

        const chunks: Buffer[] = [];
        req.on("data", (chunk: Buffer) => chunks.push(chunk));
        req.on("end", () => {
          lastRequestBody = Buffer.concat(chunks).toString("utf-8");

          const entry = responses[req.url ?? ""];
          if (entry && (!entry.method || entry.method === req.method)) {
            const body =
              typeof entry.body === "string"
                ? entry.body
                : entry.body instanceof Buffer
                  ? entry.body
                  : JSON.stringify(entry.body);
            res.writeHead(entry.status, { "Content-Type": "application/json" });
            res.end(body);
          } else {
            res.writeHead(404);
            res.end(JSON.stringify({ error: "not found" }));
          }
        });
      });

      server.listen(0, "127.0.0.1", () => {
        const addr = server.address();
        if (addr && typeof addr === "object") {
          port = addr.port;
        }
        resolve();
      });
    }),
);

afterAll(
  () =>
    new Promise<void>((resolve) => {
      server.close(() => resolve());
    }),
);

function makeClient(): LocalClient {
  return new LocalClient({
    tcpPort: port,
    token: "test-token",
  });
}

describe("LocalClient", () => {
  it("fetches status", async () => {
    responses = {
      "/localapi/v0/status": {
        status: 200,
        body: {
          Version: "1.94.1",
          BackendState: "Running",
          TUN: true,
          Self: {
            ID: "n123",
            PublicKey: "key123",
            HostName: "myhost",
            DNSName: "myhost.example.ts.net.",
            OS: "linux",
            TailscaleIPs: ["100.64.0.1"],
            Online: true,
          },
          Peer: {},
          AuthURL: "",
        },
      },
    };

    const client = makeClient();
    const status = await client.status();
    expect(status.Version).toBe("1.94.1");
    expect(status.BackendState).toBe("Running");
    expect(status.Self?.HostName).toBe("myhost");
    client.destroy();
  });

  it("fetches status without peers", async () => {
    responses = {
      "/localapi/v0/status?peers=false": {
        status: 200,
        body: {
          Version: "1.94.1",
          BackendState: "Running",
          TUN: true,
          Peer: {},
          AuthURL: "",
        },
      },
    };

    const client = makeClient();
    const status = await client.statusWithoutPeers();
    expect(status.Version).toBe("1.94.1");
    client.destroy();
  });

  it("throws PeerNotFoundError on whois 404", async () => {
    responses = {
      "/localapi/v0/whois?addr=1.2.3.4": {
        status: 404,
        body: { error: "peer not found" },
      },
    };

    const client = makeClient();
    await expect(client.whoIs("1.2.3.4")).rejects.toThrow(PeerNotFoundError);
    client.destroy();
  });

  it("throws AccessDeniedError on 403", async () => {
    responses = {
      "/localapi/v0/status": {
        status: 403,
        body: { error: "access denied" },
      },
    };

    const client = makeClient();
    await expect(client.status()).rejects.toThrow(AccessDeniedError);
    client.destroy();
  });

  it("throws PreconditionsFailedError on 412", async () => {
    responses = {
      "/localapi/v0/status": {
        status: 412,
        body: { error: "state mismatch" },
      },
    };

    const client = makeClient();
    await expect(client.status()).rejects.toThrow(PreconditionsFailedError);
    client.destroy();
  });

  it("throws HttpError on other errors", async () => {
    responses = {
      "/localapi/v0/status": {
        status: 500,
        body: { error: "internal error" },
      },
    };

    const client = makeClient();
    await expect(client.status()).rejects.toThrow(HttpError);
    client.destroy();
  });

  it("fetches prefs", async () => {
    responses = {
      "/localapi/v0/prefs": {
        status: 200,
        body: {
          ControlURL: "https://controlplane.tailscale.com",
          RouteAll: false,
          CorpDNS: true,
          WantRunning: true,
          Hostname: "myhost",
          AdvertiseTags: [],
        },
      },
    };

    const client = makeClient();
    const prefs = await client.getPrefs();
    expect(prefs.ControlURL).toBe("https://controlplane.tailscale.com");
    expect(prefs.WantRunning).toBe(true);
    client.destroy();
  });

  it("sends auth header", async () => {
    let receivedAuth = "";
    const authServer = http.createServer((req, res) => {
      receivedAuth = req.headers["authorization"] ?? "";
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          Version: "1.94.1",
          BackendState: "Running",
          TUN: false,
          Peer: {},
          AuthURL: "",
        }),
      );
    });

    await new Promise<void>((resolve) => {
      authServer.listen(0, "127.0.0.1", resolve);
    });
    const authPort = (authServer.address() as { port: number }).port;

    const client = new LocalClient({ tcpPort: authPort, token: "test-token" });
    await client.status();
    expect(receivedAuth).toMatch(/^Basic /);
    client.destroy();
    await new Promise<void>((resolve) => authServer.close(() => resolve()));
  });

  it("certPair parses combined PEM response", async () => {
    const keyPem = "-----BEGIN PRIVATE KEY-----\nkey-data\n-----END PRIVATE KEY-----\n";
    const certPem = "-----BEGIN CERTIFICATE-----\ncert-data\n-----END CERTIFICATE-----\n";
    // The wire format is key PEM then cert PEM concatenated, with the
    // split point at the "--\n--" boundary between them.
    const combined = keyPem + certPem;

    responses = {
      "/localapi/v0/cert/example.ts.net?type=pair&min_validity=0s": {
        status: 200,
        body: combined,
      },
    };

    const client = makeClient();
    const { cert, key } = await client.certPair("example.ts.net");
    expect(key.toString("utf-8")).toBe(keyPem);
    expect(cert.toString("utf-8")).toBe(certPem);
    client.destroy();
  });

  it("certPairWithValidity passes min_validity param", async () => {
    const keyPem = "-----BEGIN PRIVATE KEY-----\nkey-data\n-----END PRIVATE KEY-----\n";
    const certPem = "-----BEGIN CERTIFICATE-----\ncert-data\n-----END CERTIFICATE-----\n";
    const combined = keyPem + certPem;

    responses = {
      "/localapi/v0/cert/example.ts.net?type=pair&min_validity=3600s": {
        status: 200,
        body: combined,
      },
    };

    const client = makeClient();
    const { cert, key } = await client.certPairWithValidity("example.ts.net", 3600);
    expect(key.toString("utf-8")).toBe(keyPem);
    expect(cert.toString("utf-8")).toBe(certPem);
    client.destroy();
  });

  it("checkIpForwarding returns warning", async () => {
    responses = {
      "/localapi/v0/check-ip-forwarding": {
        status: 200,
        body: { Warning: "IP forwarding is disabled" },
      },
    };

    const client = makeClient();
    const warning = await client.checkIpForwarding();
    expect(warning).toBe("IP forwarding is disabled");
    client.destroy();
  });

  it("checkIpForwarding returns null when no warning", async () => {
    responses = {
      "/localapi/v0/check-ip-forwarding": {
        status: 200,
        body: {},
      },
    };

    const client = makeClient();
    const warning = await client.checkIpForwarding();
    expect(warning).toBeNull();
    client.destroy();
  });

  it("suggestExitNode returns suggestion", async () => {
    responses = {
      "/localapi/v0/suggest-exit-node": {
        status: 200,
        body: {
          ID: "node123",
          Name: "us-east-1",
          Location: {
            Country: "US",
            CountryCode: "US",
            City: "New York",
            CityCode: "nyc",
          },
        },
      },
    };

    const client = makeClient();
    const suggestion = await client.suggestExitNode();
    expect(suggestion.ID).toBe("node123");
    expect(suggestion.Name).toBe("us-east-1");
    client.destroy();
  });

  it("ping returns PingResult", async () => {
    responses = {
      "/localapi/v0/ping?ip=100.64.0.2&type=disco&size=0": {
        status: 200,
        body: {
          IP: "100.64.0.2",
          NodeIP: "100.64.0.2",
          NodeName: "peer1",
          LatencySeconds: 0.05,
        },
      },
    };

    const client = makeClient();
    const result = await client.ping("100.64.0.2");
    expect(result.IP).toBe("100.64.0.2");
    expect(result.LatencySeconds).toBe(0.05);
    client.destroy();
  });

  it("pingWithOpts passes size parameter", async () => {
    responses = {
      "/localapi/v0/ping?ip=100.64.0.2&type=TSMP&size=512": {
        status: 200,
        body: {
          IP: "100.64.0.2",
          NodeIP: "100.64.0.2",
          NodeName: "peer1",
          LatencySeconds: 0.1,
        },
      },
    };

    const client = makeClient();
    const result = await client.pingWithOpts("100.64.0.2", "TSMP", 512);
    expect(result.LatencySeconds).toBe(0.1);
    client.destroy();
  });

  it("incrementCounter sends correct metric format", async () => {
    responses = {
      "/localapi/v0/upload-client-metrics": {
        status: 200,
        body: "",
      },
    };

    const client = makeClient();
    await client.incrementCounter("my_counter", 5);
    const parsed = JSON.parse(lastRequestBody!);
    expect(parsed).toEqual([{ Name: "my_counter", Type: "counter", Value: 5, Op: "add" }]);
    client.destroy();
  });

  it("setGauge sends correct metric format", async () => {
    responses = {
      "/localapi/v0/upload-client-metrics": {
        status: 200,
        body: "",
      },
    };

    const client = makeClient();
    await client.setGauge("my_gauge", 42);
    const parsed = JSON.parse(lastRequestBody!);
    expect(parsed).toEqual([{ Name: "my_gauge", Type: "gauge", Value: 42, Op: "set" }]);
    client.destroy();
  });

  it("incrementGauge sends correct metric format", async () => {
    responses = {
      "/localapi/v0/upload-client-metrics": {
        status: 200,
        body: "",
      },
    };

    const client = makeClient();
    await client.incrementGauge("my_gauge", 3);
    const parsed = JSON.parse(lastRequestBody!);
    expect(parsed).toEqual([{ Name: "my_gauge", Type: "gauge", Value: 3, Op: "add" }]);
    client.destroy();
  });

  it("waitingFiles returns file list", async () => {
    responses = {
      "/localapi/v0/files/?waitsec=0": {
        status: 200,
        body: [{ Name: "file.txt", Size: 1024 }],
      },
    };

    const client = makeClient();
    const files = await client.waitingFiles();
    expect(files).toHaveLength(1);
    expect(files[0].Name).toBe("file.txt");
    expect(files[0].Size).toBe(1024);
    client.destroy();
  });

  it("awaitWaitingFiles passes wait duration", async () => {
    responses = {
      "/localapi/v0/files/?waitsec=30": {
        status: 200,
        body: [],
      },
    };

    const client = makeClient();
    const files = await client.awaitWaitingFiles(30);
    expect(files).toEqual([]);
    client.destroy();
  });

  it("fileTargets returns targets", async () => {
    responses = {
      "/localapi/v0/file-targets": {
        status: 200,
        body: [{ Node: { ID: "n1", HostName: "peer" }, PeerAPIURL: "http://100.64.0.2:123" }],
      },
    };

    const client = makeClient();
    const targets = await client.fileTargets();
    expect(targets).toHaveLength(1);
    expect(targets[0].PeerAPIURL).toBe("http://100.64.0.2:123");
    client.destroy();
  });

  it("driveShareRename sends old and new names", async () => {
    responses = {
      "/localapi/v0/drive/shares": {
        status: 200,
        method: "POST",
        body: "",
      },
    };

    const client = makeClient();
    await client.driveShareRename("old-share", "new-share");
    expect(JSON.parse(lastRequestBody!)).toEqual(["old-share", "new-share"]);
    client.destroy();
  });

  it("networkLockStatus returns status", async () => {
    responses = {
      "/localapi/v0/tka/status": {
        status: 200,
        body: {
          Enabled: false,
          Head: "",
          PublicKey: "",
          NodeKey: "",
          NodeKeySigned: false,
        },
      },
    };

    const client = makeClient();
    const status = await client.networkLockStatus();
    expect(status.Enabled).toBe(false);
    client.destroy();
  });

  it("debugSetExpireIn computes unix timestamp", async () => {
    const now = Math.floor(Date.now() / 1000);
    // We need to match the URL dynamically since the timestamp depends on current time
    let requestedUrl = "";
    const expServer = http.createServer((req, res) => {
      requestedUrl = req.url ?? "";
      res.writeHead(200);
      res.end("");
    });

    await new Promise<void>((resolve) => {
      expServer.listen(0, "127.0.0.1", resolve);
    });
    const expPort = (expServer.address() as { port: number }).port;

    const client = new LocalClient({ tcpPort: expPort, token: "test-token" });
    await client.debugSetExpireIn(3600);
    const match = requestedUrl.match(/expiry=(\d+)/);
    expect(match).not.toBeNull();
    const expiry = parseInt(match![1], 10);
    // Should be approximately now + 3600, allow 5 second tolerance
    expect(expiry).toBeGreaterThanOrEqual(now + 3595);
    expect(expiry).toBeLessThanOrEqual(now + 3605);
    client.destroy();
    await new Promise<void>((resolve) => expServer.close(() => resolve()));
  });

  it("setComponentDebugLogging throws on error response", async () => {
    responses = {
      "/localapi/v0/component-debug-logging?component=magicsock&secs=60": {
        status: 200,
        body: { Error: "unknown component" },
      },
    };

    const client = makeClient();
    await expect(
      client.setComponentDebugLogging("magicsock", 60),
    ).rejects.toThrow("unknown component");
    client.destroy();
  });

  it("setComponentDebugLogging succeeds when no error", async () => {
    responses = {
      "/localapi/v0/component-debug-logging?component=magicsock&secs=60": {
        status: 200,
        body: {},
      },
    };

    const client = makeClient();
    await client.setComponentDebugLogging("magicsock", 60);
    client.destroy();
  });

  it("queryDns returns response", async () => {
    responses = {
      "/localapi/v0/dns-query?name=example.com&type=A": {
        status: 200,
        body: { Bytes: "AAAA", Resolvers: [] },
      },
    };

    const client = makeClient();
    const resp = await client.queryDns("example.com", "A");
    expect(resp.Bytes).toBe("AAAA");
    client.destroy();
  });

  it("getDnsOsConfig returns config", async () => {
    responses = {
      "/localapi/v0/dns-osconfig": {
        status: 200,
        body: { Nameservers: ["1.1.1.1"], SearchDomains: [], MatchDomains: [] },
      },
    };

    const client = makeClient();
    const config = await client.getDnsOsConfig();
    expect(config.Nameservers).toEqual(["1.1.1.1"]);
    client.destroy();
  });

  it("checkUpdate returns client version", async () => {
    responses = {
      "/localapi/v0/update/check": {
        status: 200,
        body: { RunningLatest: true },
      },
    };

    const client = makeClient();
    const version = await client.checkUpdate();
    expect(version.RunningLatest).toBe(true);
    client.destroy();
  });

  it("setDns uses set-dns endpoint", async () => {
    responses = {
      "/localapi/v0/set-dns?name=_acme-challenge.example.com&value=token123": {
        status: 200,
        body: "",
      },
    };

    const client = makeClient();
    await client.setDns("_acme-challenge.example.com", "token123");
    client.destroy();
  });
});
