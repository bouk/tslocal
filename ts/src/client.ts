import { parseJSON, jsonReplacer } from "./json.js";
import {
  AccessDeniedError,
  ConnectionError,
  DaemonNotRunningError,
  HttpError,
  PeerNotFoundError,
  PreconditionsFailedError,
  errorMessageFromBody,
} from "./errors.js";
import { Transport, type TransportOptions } from "./transport.js";
import {
  ServeConfigSchema,
  StatusSchema,
  WhoIsResponseSchema,
  type ServeConfig,
  type Status,
  type WhoIsResponse,
} from "./types.js";

/**
 * Client for the Tailscale Local API.
 *
 * Connections are reused via HTTP keep-alive.
 */
export class Client {
  private readonly transport: Transport;

  constructor(opts: TransportOptions = {}) {
    this.transport = new Transport(opts);
  }

  private async doRequest(
    method: string,
    path: string,
    body?: Buffer | string,
    headers?: Record<string, string>,
  ): Promise<{ status: number; body: Buffer; headers: Record<string, string | string[] | undefined> }> {
    try {
      return await this.transport.request(method, path, body, headers);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("ECONNREFUSED") || msg.includes("ENOENT")) {
        throw new DaemonNotRunningError(msg);
      }
      throw new ConnectionError(msg);
    }
  }

  private async doRequestNice(
    method: string,
    path: string,
    body?: Buffer | string,
    headers?: Record<string, string>,
  ): Promise<Buffer> {
    const resp = await this.doRequest(method, path, body, headers);
    if (resp.status >= 200 && resp.status < 300) {
      return resp.body;
    }

    const bodyStr = resp.body.toString("utf-8");
    const msg = errorMessageFromBody(bodyStr) ?? bodyStr;

    if (resp.status === 403) throw new AccessDeniedError(msg);
    if (resp.status === 412) throw new PreconditionsFailedError(msg);
    throw new HttpError(resp.status, msg);
  }

  private async get200(path: string): Promise<Buffer> {
    return this.doRequestNice("GET", path);
  }

  private async post200(path: string, body?: Buffer | string): Promise<Buffer> {
    return this.doRequestNice("POST", path, body);
  }

  // --- Status ---

  /** Get the current tailscaled status. */
  async status(): Promise<Status> {
    const data = await this.get200("/localapi/v0/status");
    return StatusSchema.parse(parseJSON(data.toString("utf-8")));
  }

  /** Get the current tailscaled status without peer information. */
  async statusWithoutPeers(): Promise<Status> {
    const data = await this.get200("/localapi/v0/status?peers=false");
    return StatusSchema.parse(parseJSON(data.toString("utf-8")));
  }

  // --- WhoIs ---

  private async doWhoIs(params: string): Promise<WhoIsResponse> {
    const resp = await this.doRequest(
      "GET",
      `/localapi/v0/whois?${params}`,
    );
    if (resp.status === 404) {
      throw new PeerNotFoundError(params);
    }
    if (resp.status !== 200) {
      const bodyStr = resp.body.toString("utf-8");
      const msg = errorMessageFromBody(bodyStr) ?? bodyStr;
      if (resp.status === 403) throw new AccessDeniedError(msg);
      throw new HttpError(resp.status, msg);
    }
    return WhoIsResponseSchema.parse(parseJSON(resp.body.toString("utf-8")));
  }

  /** Look up the owner of an IP address or IP:port. */
  async whoIs(remoteAddr: string): Promise<WhoIsResponse> {
    return this.doWhoIs(`addr=${encodeURIComponent(remoteAddr)}`);
  }

  /** Look up a peer by node key. */
  async whoIsNodeKey(nodeKey: string): Promise<WhoIsResponse> {
    return this.whoIs(nodeKey);
  }

  /** Look up the owner of an IP address with a specific protocol ("tcp" or "udp"). */
  async whoIsProto(proto: string, remoteAddr: string): Promise<WhoIsResponse> {
    return this.doWhoIs(`proto=${encodeURIComponent(proto)}&addr=${encodeURIComponent(remoteAddr)}`);
  }

  // --- Cert ---

  /** Get a TLS certificate and private key for the given domain. */
  async certPair(domain: string): Promise<{ cert: Buffer; key: Buffer }> {
    return this.certPairWithValidity(domain, 0);
  }

  /** Get a TLS certificate with minimum validity duration (in seconds). */
  async certPairWithValidity(
    domain: string,
    minValiditySecs: number,
  ): Promise<{ cert: Buffer; key: Buffer }> {
    const body = await this.get200(
      `/localapi/v0/cert/${encodeURIComponent(domain)}?type=pair&min_validity=${minValiditySecs}s`,
    );
    // Response is key PEM then cert PEM, separated by "--\n--"
    const delimiter = Buffer.from("--\n--");
    const pos = body.indexOf(delimiter);
    if (pos === -1) {
      throw new Error("unexpected cert response: no delimiter");
    }
    const split = pos + 3; // include "--\n"
    const key = body.subarray(0, split);
    const cert = body.subarray(split);
    return { cert, key };
  }

  // --- Config ---

  /**
   * Get the current serve configuration.
   *
   * The returned ServeConfig has its ETag field populated from the
   * HTTP Etag response header.
   */
  async getServeConfig(): Promise<ServeConfig> {
    const resp = await this.doRequest("GET", "/localapi/v0/serve-config");
    if (resp.status !== 200) {
      const bodyStr = resp.body.toString("utf-8");
      const msg = errorMessageFromBody(bodyStr) ?? bodyStr;
      if (resp.status === 403) throw new AccessDeniedError(msg);
      if (resp.status === 412) throw new PreconditionsFailedError(msg);
      throw new HttpError(resp.status, msg);
    }
    const config = ServeConfigSchema.parse(parseJSON(resp.body.toString("utf-8"))) as ServeConfig;
    config.ETag = (resp.headers["etag"] as string) ?? "";
    return config;
  }

  /**
   * Set the serve configuration.
   *
   * The ETag field on the config is sent as the If-Match header
   * for conditional updates.
   */
  async setServeConfig(config: ServeConfig): Promise<void> {
    const headers: Record<string, string> = {};
    if (config.ETag) headers["If-Match"] = config.ETag;
    const body = JSON.stringify(config, jsonReplacer);
    await this.doRequestNice("POST", "/localapi/v0/serve-config", body, headers);
  }

  /** Close the underlying transport and release resources. */
  destroy(): void {
    this.transport.destroy();
  }
}
