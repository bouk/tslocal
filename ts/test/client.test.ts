import * as http from "node:http";
import { describe, expect, it, beforeAll, afterAll, vi } from "vitest";
import { Client } from "../src/client.js";
import {
  AccessDeniedError,
  HttpError,
  PeerNotFoundError,
  PreconditionsFailedError,
} from "../src/errors.js";

// Mock safesocket so localTcpPortAndToken returns our test server
vi.mock("../src/safesocket.js", async (importOriginal) => {
  const mod = (await importOriginal()) as Record<string, unknown>;
  return {
    ...mod,
    localTcpPortAndToken: vi.fn(async () => undefined),
  };
});

import { localTcpPortAndToken } from "../src/safesocket.js";

let server: http.Server;
let port: number;
let responses: Record<string, { status: number; body: unknown; method?: string; headers?: Record<string, string> }> = {};
let lastRequestBody: string | undefined;
let lastRequestMethod: string | undefined;
let lastRequestUrl: string | undefined;
let lastRequestHeaders: http.IncomingHttpHeaders = {};

beforeAll(
  () =>
    new Promise<void>((resolve) => {
      server = http.createServer((req, res) => {
        // Verify required headers
        expect(req.headers["tailscale-cap"]).toBe("131");
        expect(req.headers["host"]).toBe("local-tailscaled.sock");

        lastRequestMethod = req.method;
        lastRequestUrl = req.url;
        lastRequestHeaders = req.headers;

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
            res.writeHead(entry.status, { "Content-Type": "application/json", ...entry.headers });
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
        // Point discovery at mock server
        vi.mocked(localTcpPortAndToken).mockResolvedValue({
          port,
          token: "test-token",
        });
        resolve();
      });
    }),
);

afterAll(
  () =>
    new Promise<void>((resolve) => {
      vi.restoreAllMocks();
      server.close(() => resolve());
    }),
);

function makeClient(): Client {
  return new Client();
}

describe("Client", () => {
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
    expect(status.Self.HostName).toBe("myhost");
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

  it("sends auth header", async () => {
    responses = {
      "/localapi/v0/status": {
        status: 200,
        body: {
          Version: "1.94.1",
          BackendState: "Running",
          TUN: false,
          Peer: {},
          AuthURL: "",
        },
      },
    };

    const client = makeClient();
    await client.status();
    expect(lastRequestHeaders["authorization"]).toMatch(/^Basic /);
    client.destroy();
  });

  it("certPair parses combined PEM response", async () => {
    const keyPem = "-----BEGIN PRIVATE KEY-----\nkey-data\n-----END PRIVATE KEY-----\n";
    const certPem = "-----BEGIN CERTIFICATE-----\ncert-data\n-----END CERTIFICATE-----\n";
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

  it("whoIsProto passes proto parameter", async () => {
    responses = {
      "/localapi/v0/whois?proto=tcp&addr=100.64.0.1%3A80": {
        status: 200,
        body: {
          Node: { ID: 1, Name: "myhost" },
          UserProfile: { ID: 1, LoginName: "user@example.com", DisplayName: "User" },
        },
      },
    };

    const client = makeClient();
    const result = await client.whoIsProto("tcp", "100.64.0.1:80");
    expect(result.UserProfile.LoginName).toBe("user@example.com");
    client.destroy();
  });

  it("getServeConfig returns config with etag", async () => {
    responses = {
      "/localapi/v0/serve-config": {
        status: 200,
        body: { TCP: {}, Web: {} },
        headers: { Etag: '"abc123"' },
      },
    };

    const client = makeClient();
    const config = await client.getServeConfig();
    expect(config.TCP).toEqual({});
    expect(config.Web).toEqual({});
    expect(config.ETag).toBe('"abc123"');
    client.destroy();
  });

  it("getServeConfig throws with error message on failure", async () => {
    responses = {
      "/localapi/v0/serve-config": {
        status: 500,
        body: { error: "internal error" },
      },
    };

    const client = makeClient();
    await expect(client.getServeConfig()).rejects.toThrow(HttpError);
    await expect(client.getServeConfig()).rejects.toThrow("internal error");
    client.destroy();
  });

  it("setServeConfig sends config with etag", async () => {
    responses = {
      "/localapi/v0/serve-config": {
        status: 200,
        body: {},
        method: "POST",
      },
    };

    const client = makeClient();
    const config = { TCP: {}, Web: {}, Services: {}, AllowFunnel: {}, Foreground: {}, ETag: '"etag-value"' };
    await client.setServeConfig(config);
    expect(lastRequestMethod).toBe("POST");
    expect(lastRequestUrl).toBe("/localapi/v0/serve-config");
    client.destroy();
  });
});
