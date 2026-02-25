import * as http from "node:http";
import * as net from "node:net";
import {
  CURRENT_CAP_VERSION,
  LOCAL_API_HOST,
  type PortAndToken,
  defaultSocketPath,
  localTcpPortAndToken,
} from "./safesocket.js";

export interface TransportOptions {
  socketPath?: string;
  tcpPort?: number;
  token?: string;
  useSocketOnly?: boolean;
}

/**
 * HTTP transport that connects to tailscaled.
 * Reuses connections via Node.js http.Agent keep-alive.
 */
export class Transport {
  private readonly socketPath: string;
  private readonly tcpPort?: number;
  private readonly token?: string;
  private readonly useSocketOnly: boolean;
  private readonly agent: http.Agent;

  constructor(opts: TransportOptions = {}) {
    this.socketPath = opts.socketPath ?? defaultSocketPath();
    this.tcpPort = opts.tcpPort;
    this.token = opts.token;
    this.useSocketOnly = opts.useSocketOnly ?? false;

    // Auto-detect macOS TCP if not provided
    if (!this.useSocketOnly && this.tcpPort === undefined) {
      const detected = localTcpPortAndToken();
      if (detected) {
        this.tcpPort = detected.port;
        this.token = detected.token;
      }
    }

    // Create agent with keep-alive for connection reuse
    if (this.usesTcp) {
      this.agent = new http.Agent({
        keepAlive: true,
        keepAliveMsecs: 60_000,
      });
    } else {
      this.agent = new http.Agent({
        keepAlive: true,
        keepAliveMsecs: 60_000,
      });
    }
  }

  get usesTcp(): boolean {
    return !this.useSocketOnly && this.tcpPort !== undefined && this.token !== undefined;
  }

  async request(
    method: string,
    path: string,
    body?: Buffer | string,
    extraHeaders?: Record<string, string>,
  ): Promise<{ status: number; body: Buffer; headers: http.IncomingHttpHeaders }> {
    return new Promise((resolve, reject) => {
      const headers: Record<string, string> = {
        Host: LOCAL_API_HOST,
        "Tailscale-Cap": String(CURRENT_CAP_VERSION),
        ...extraHeaders,
      };

      if (this.usesTcp && this.token) {
        const cred = Buffer.from(`:${this.token}`).toString("base64");
        headers["Authorization"] = `Basic ${cred}`;
      }

      const options: http.RequestOptions = {
        method,
        path,
        headers,
        agent: this.agent,
      };

      if (this.usesTcp) {
        options.host = "127.0.0.1";
        options.port = this.tcpPort;
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
