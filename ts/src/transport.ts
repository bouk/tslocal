import * as http from "node:http";
import {
  CURRENT_CAP_VERSION,
  LOCAL_API_HOST,
  type PortAndToken,
  defaultSocketPath,
  localTcpPortAndToken,
} from "./safesocket.js";

export interface TransportOptions {
  socketPath?: string;
  useSocketOnly?: boolean;
}

/**
 * Discover TCP port and token for this request.
 */
async function resolvePortAndToken(useSocketOnly: boolean): Promise<PortAndToken | undefined> {
  if (useSocketOnly) return undefined;
  return localTcpPortAndToken();
}

/**
 * HTTP transport that connects to tailscaled.
 * Reuses connections via Node.js http.Agent keep-alive.
 * Port and token are discovered per-request (matching Go's behavior),
 * so the client adapts to daemon restarts and late starts.
 */
export class Transport {
  private readonly socketPath: string;
  private readonly useSocketOnly: boolean;
  private readonly agent: http.Agent;

  constructor(opts: TransportOptions = {}) {
    this.socketPath = opts.socketPath ?? defaultSocketPath();
    this.useSocketOnly = opts.useSocketOnly ?? false;

    // Single agent with keep-alive — pools connections by host:port key
    this.agent = new http.Agent({
      keepAlive: true,
      keepAliveMsecs: 60_000,
    });
  }

  async request(
    method: string,
    path: string,
    body?: Buffer | string,
    extraHeaders?: Record<string, string>,
  ): Promise<{ status: number; body: Buffer; headers: http.IncomingHttpHeaders }> {
    const portAndToken = await resolvePortAndToken(this.useSocketOnly);

    return new Promise((resolve, reject) => {
      const headers: Record<string, string> = {
        Host: LOCAL_API_HOST,
        "Tailscale-Cap": String(CURRENT_CAP_VERSION),
        ...extraHeaders,
      };

      if (portAndToken) {
        const cred = Buffer.from(`:${portAndToken.token}`).toString("base64");
        headers["Authorization"] = `Basic ${cred}`;
      }

      const options: http.RequestOptions = {
        method,
        path,
        headers,
        agent: this.agent,
      };

      if (portAndToken) {
        options.host = "127.0.0.1";
        options.port = portAndToken.port;
      } else {
        options.socketPath = this.socketPath;
      }

      const req = http.request(options, (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (chunk: Buffer) => chunks.push(chunk));
        res.on("end", () => {
          resolve({
            status: res.statusCode ?? 0,
            body: Buffer.concat(chunks),
            headers: res.headers,
          });
        });
        res.on("error", reject);
      });

      req.on("error", reject);

      if (body !== undefined) {
        req.write(body);
      }
      req.end();
    });
  }

  destroy(): void {
    this.agent.destroy();
  }
}
