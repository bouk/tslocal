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
import type {
  ClientVersion,
  DERPMap,
  DNSOSConfig,
  DNSQueryResponse,
  ExitNodeSuggestionResponse,
  FileTarget,
  LoginProfile,
  MaskedPrefs,
  NetworkLockStatus,
  OptionalFeatures,
  PingResult,
  Prefs,
  ProfileStatus,
  ReloadConfigResponse,
  Status,
  WaitingFile,
  WhoIsResponse,
} from "./types.js";

/**
 * Client for the Tailscale Local API.
 *
 * Connections are reused via HTTP keep-alive.
 */
export class LocalClient {
  private readonly transport: Transport;

  constructor(opts: TransportOptions = {}) {
    this.transport = new Transport(opts);
  }

  private async doRequest(
    method: string,
    path: string,
    body?: Buffer | string,
    headers?: Record<string, string>,
  ): Promise<{ status: number; body: Buffer }> {
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

  async status(): Promise<Status> {
    const data = await this.get200("/localapi/v0/status");
    return JSON.parse(data.toString("utf-8"));
  }

  async statusWithoutPeers(): Promise<Status> {
    const data = await this.get200("/localapi/v0/status?peers=false");
    return JSON.parse(data.toString("utf-8"));
  }

  // --- WhoIs ---

  async whoIs(remoteAddr: string): Promise<WhoIsResponse> {
    const resp = await this.doRequest(
      "GET",
      `/localapi/v0/whois?addr=${encodeURIComponent(remoteAddr)}`,
    );
    if (resp.status === 404) {
      throw new PeerNotFoundError(remoteAddr);
    }
    if (resp.status !== 200) {
      const bodyStr = resp.body.toString("utf-8");
      const msg = errorMessageFromBody(bodyStr) ?? bodyStr;
      if (resp.status === 403) throw new AccessDeniedError(msg);
      throw new HttpError(resp.status, msg);
    }
    return JSON.parse(resp.body.toString("utf-8"));
  }

  async whoIsNodeKey(nodeKey: string): Promise<WhoIsResponse> {
    return this.whoIs(nodeKey);
  }

  // --- Auth ---

  async startLoginInteractive(): Promise<void> {
    await this.post200("/localapi/v0/login-interactive");
  }

  async logout(): Promise<void> {
    await this.post200("/localapi/v0/logout");
  }

  // --- Prefs ---

  async getPrefs(): Promise<Prefs> {
    const data = await this.get200("/localapi/v0/prefs");
    return JSON.parse(data.toString("utf-8"));
  }

  async editPrefs(prefs: MaskedPrefs): Promise<Prefs> {
    const body = JSON.stringify(prefs);
    const data = await this.doRequestNice("PATCH", "/localapi/v0/prefs", body);
    return JSON.parse(data.toString("utf-8"));
  }

  async checkPrefs(prefs: Prefs): Promise<void> {
    const body = JSON.stringify(prefs);
    await this.post200("/localapi/v0/check-prefs", body);
  }

  // --- Profiles ---

  async profileStatus(): Promise<ProfileStatus> {
    const data = await this.get200("/localapi/v0/profiles/current");
    return JSON.parse(data.toString("utf-8"));
  }

  async switchProfile(profileId: string): Promise<void> {
    await this.post200(
      `/localapi/v0/profiles/${encodeURIComponent(profileId)}`,
    );
  }

  async switchToEmptyProfile(): Promise<void> {
    await this.doRequestNice("PUT", "/localapi/v0/profiles/");
  }

  async deleteProfile(profileId: string): Promise<void> {
    await this.doRequestNice(
      "DELETE",
      `/localapi/v0/profiles/${encodeURIComponent(profileId)}`,
    );
  }

  // --- DNS ---

  async setDns(name: string, value: string): Promise<void> {
    await this.post200(
      `/localapi/v0/set-dns?name=${encodeURIComponent(name)}&value=${encodeURIComponent(value)}`,
    );
  }

  async queryDns(name: string, queryType: string): Promise<DNSQueryResponse> {
    const data = await this.get200(
      `/localapi/v0/dns-query?name=${encodeURIComponent(name)}&type=${encodeURIComponent(queryType)}`,
    );
    return JSON.parse(data.toString("utf-8"));
  }

  async getDnsOsConfig(): Promise<DNSOSConfig> {
    const data = await this.get200("/localapi/v0/dns-osconfig");
    return JSON.parse(data.toString("utf-8"));
  }

  // --- Diagnostics ---

  async checkIpForwarding(): Promise<string | null> {
    const data = await this.get200("/localapi/v0/check-ip-forwarding");
    const resp = JSON.parse(data.toString("utf-8"));
    return resp.Warning || null;
  }

  async checkUdpGroForwarding(): Promise<string | null> {
    const data = await this.get200("/localapi/v0/check-udp-gro-forwarding");
    const resp = JSON.parse(data.toString("utf-8"));
    return resp.Warning || null;
  }

  async checkReversePathFiltering(): Promise<string | null> {
    const data = await this.get200("/localapi/v0/check-reverse-path-filtering");
    const resp = JSON.parse(data.toString("utf-8"));
    return resp.Warning || null;
  }

  async setUdpGroForwarding(): Promise<string | null> {
    const data = await this.get200("/localapi/v0/set-udp-gro-forwarding");
    const resp = JSON.parse(data.toString("utf-8"));
    return resp.Warning || null;
  }

  async checkSoMarkInUse(): Promise<boolean> {
    const data = await this.get200("/localapi/v0/check-so-mark-in-use");
    const resp = JSON.parse(data.toString("utf-8"));
    return resp.useSoMark ?? false;
  }

  async daemonMetrics(): Promise<string> {
    const data = await this.get200("/localapi/v0/metrics");
    return data.toString("utf-8");
  }

  async userMetrics(): Promise<string> {
    const data = await this.get200("/localapi/v0/usermetrics");
    return data.toString("utf-8");
  }

  async goroutines(): Promise<string> {
    const data = await this.get200("/localapi/v0/goroutines");
    return data.toString("utf-8");
  }

  async pprof(pprofType: string, secs: number): Promise<Buffer> {
    return this.get200(
      `/localapi/v0/pprof?name=${encodeURIComponent(pprofType)}&seconds=${secs}`,
    );
  }

  async getAppConnectorRouteInfo(): Promise<Record<string, unknown>> {
    const data = await this.get200("/localapi/v0/appc-route-info");
    return JSON.parse(data.toString("utf-8"));
  }

  async idToken(aud: string): Promise<Record<string, unknown>> {
    const data = await this.get200(
      `/localapi/v0/id-token?aud=${encodeURIComponent(aud)}`,
    );
    return JSON.parse(data.toString("utf-8"));
  }

  async disconnectControl(): Promise<void> {
    await this.post200("/localapi/v0/disconnect-control");
  }

  async queryOptionalFeatures(): Promise<OptionalFeatures> {
    const data = await this.post200("/localapi/v0/debug-optional-features");
    return JSON.parse(data.toString("utf-8"));
  }

  // --- Config ---

  async getServeConfig(): Promise<{ config: Record<string, unknown>; etag: string }> {
    const resp = await this.doRequest("GET", "/localapi/v0/serve-config");
    if (resp.status !== 200) {
      const msg = resp.body.toString("utf-8");
      throw new HttpError(resp.status, msg);
    }
    return { config: JSON.parse(resp.body.toString("utf-8")), etag: "" };
  }

  async setServeConfig(
    config: Record<string, unknown>,
    etag?: string,
  ): Promise<void> {
    const headers: Record<string, string> = {};
    if (etag) headers["If-Match"] = etag;
    const body = JSON.stringify(config);
    await this.doRequestNice("POST", "/localapi/v0/serve-config", body, headers);
  }

  // --- Exit Node ---

  async setUseExitNode(enabled: boolean): Promise<void> {
    await this.post200(
      `/localapi/v0/set-use-exit-node-enabled?enabled=${enabled}`,
    );
  }

  async suggestExitNode(): Promise<ExitNodeSuggestionResponse> {
    const data = await this.get200("/localapi/v0/suggest-exit-node");
    return JSON.parse(data.toString("utf-8"));
  }

  // --- System ---

  async bugReport(note = ""): Promise<string> {
    const data = await this.post200(
      `/localapi/v0/bugreport?note=${encodeURIComponent(note)}`,
    );
    return data.toString("utf-8").trim();
  }

  async shutdownTailscaled(): Promise<void> {
    await this.post200("/localapi/v0/shutdown");
  }

  async reloadConfig(): Promise<ReloadConfigResponse> {
    const data = await this.post200("/localapi/v0/reload-config");
    return JSON.parse(data.toString("utf-8"));
  }

  // --- Ping ---

  async ping(
    ip: string,
    pingType = "disco",
  ): Promise<PingResult> {
    return this.pingWithOpts(ip, pingType, 0);
  }

  async pingWithOpts(
    ip: string,
    pingType: string,
    size: number,
  ): Promise<PingResult> {
    const data = await this.post200(
      `/localapi/v0/ping?ip=${encodeURIComponent(ip)}&type=${encodeURIComponent(pingType)}&size=${size}`,
    );
    return JSON.parse(data.toString("utf-8"));
  }

  // --- DERP ---

  async currentDerpMap(): Promise<DERPMap> {
    const data = await this.get200("/localapi/v0/derpmap");
    return JSON.parse(data.toString("utf-8"));
  }

  async debugDerpRegion(regionIdOrCode: string): Promise<Record<string, unknown>> {
    const data = await this.post200(
      `/localapi/v0/debug-derp-region?region=${encodeURIComponent(regionIdOrCode)}`,
    );
    return JSON.parse(data.toString("utf-8"));
  }

  async debugPeerRelaySessions(): Promise<Record<string, unknown>> {
    const data = await this.get200("/localapi/v0/debug-peer-relay-sessions");
    return JSON.parse(data.toString("utf-8"));
  }

  // --- Cert ---

  async certPair(domain: string): Promise<{ cert: Buffer; key: Buffer }> {
    return this.certPairWithValidity(domain, 0);
  }

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

  // --- Taildrop ---

  async waitingFiles(): Promise<WaitingFile[]> {
    const data = await this.get200("/localapi/v0/files/?waitsec=0");
    return JSON.parse(data.toString("utf-8"));
  }

  async awaitWaitingFiles(waitSecs: number): Promise<WaitingFile[]> {
    const data = await this.get200(`/localapi/v0/files/?waitsec=${waitSecs}`);
    return JSON.parse(data.toString("utf-8"));
  }

  async deleteWaitingFile(baseName: string): Promise<void> {
    await this.doRequestNice(
      "DELETE",
      `/localapi/v0/files/${encodeURIComponent(baseName)}`,
    );
  }

  async fileTargets(): Promise<FileTarget[]> {
    const data = await this.get200("/localapi/v0/file-targets");
    return JSON.parse(data.toString("utf-8"));
  }

  async pushFile(target: string, name: string, data: Buffer): Promise<void> {
    await this.doRequestNice(
      "PUT",
      `/localapi/v0/file-put/${encodeURIComponent(target)}/${encodeURIComponent(name)}`,
      data,
    );
  }

  // --- Drive ---

  async driveShareList(): Promise<unknown[]> {
    const data = await this.get200("/localapi/v0/drive/shares");
    return JSON.parse(data.toString("utf-8"));
  }

  async driveShareSet(share: Record<string, unknown>): Promise<void> {
    const body = JSON.stringify(share);
    await this.doRequestNice("PUT", "/localapi/v0/drive/shares", body);
  }

  async driveShareRemove(name: string): Promise<void> {
    await this.doRequestNice("DELETE", "/localapi/v0/drive/shares", name);
  }

  async driveShareRename(oldName: string, newName: string): Promise<void> {
    const body = JSON.stringify([oldName, newName]);
    await this.post200("/localapi/v0/drive/shares", body);
  }

  async driveSetServerAddr(addr: string): Promise<void> {
    await this.doRequestNice("PUT", "/localapi/v0/drive/fileserver-address", addr);
  }

  // --- Metrics ---

  async incrementCounter(name: string, delta: number): Promise<void> {
    const body = JSON.stringify([{ Name: name, Type: "counter", Value: delta, Op: "add" }]);
    await this.post200("/localapi/v0/upload-client-metrics", body);
  }

  async incrementGauge(name: string, delta: number): Promise<void> {
    const body = JSON.stringify([{ Name: name, Type: "gauge", Value: delta, Op: "add" }]);
    await this.post200("/localapi/v0/upload-client-metrics", body);
  }

  async setGauge(name: string, value: number): Promise<void> {
    const body = JSON.stringify([{ Name: name, Type: "gauge", Value: value, Op: "set" }]);
    await this.post200("/localapi/v0/upload-client-metrics", body);
  }

  // --- Logging ---

  async setComponentDebugLogging(component: string, secs: number): Promise<void> {
    const data = await this.post200(
      `/localapi/v0/component-debug-logging?component=${encodeURIComponent(component)}&secs=${secs}`,
    );
    const resp = JSON.parse(data.toString("utf-8"));
    if (resp.Error) {
      throw new Error(resp.Error);
    }
  }

  async setDevStoreKeyValue(key: string, value: string): Promise<void> {
    await this.post200(
      `/localapi/v0/dev-set-state-store?key=${encodeURIComponent(key)}&value=${encodeURIComponent(value)}`,
    );
  }

  // --- Network Lock ---

  async networkLockStatus(): Promise<NetworkLockStatus> {
    const data = await this.get200("/localapi/v0/tka/status");
    return JSON.parse(data.toString("utf-8"));
  }

  async networkLockInit(
    keys: unknown[],
    disablementValues: string[],
    supportDisablement: boolean,
  ): Promise<NetworkLockStatus> {
    const body = JSON.stringify({
      Keys: keys,
      DisablementValues: disablementValues,
      SupportDisablement: supportDisablement,
    });
    const data = await this.post200("/localapi/v0/tka/init", body);
    return JSON.parse(data.toString("utf-8"));
  }

  async networkLockWrapPreauthKey(tsKey: string, tkaKey: string): Promise<string> {
    const body = JSON.stringify({ TSKey: tsKey, TKAKey: tkaKey });
    const data = await this.post200("/localapi/v0/tka/wrap-preauth-key", body);
    return data.toString("utf-8");
  }

  async networkLockModify(addKeys: unknown[], removeKeys: unknown[]): Promise<void> {
    const body = JSON.stringify({ AddKeys: addKeys, RemoveKeys: removeKeys });
    await this.post200("/localapi/v0/tka/modify", body);
  }

  async networkLockSign(nodeKey: string, rotationPublic: string): Promise<void> {
    const body = JSON.stringify({ NodeKey: nodeKey, RotationPublic: rotationPublic });
    await this.post200("/localapi/v0/tka/sign", body);
  }

  async networkLockAffectedSigs(keyId: Buffer): Promise<string[][]> {
    const data = await this.post200("/localapi/v0/tka/affected-sigs", keyId);
    return JSON.parse(data.toString("utf-8"));
  }

  async networkLockLog(maxEntries: number): Promise<unknown[]> {
    const data = await this.get200(`/localapi/v0/tka/log?limit=${maxEntries}`);
    return JSON.parse(data.toString("utf-8"));
  }

  async networkLockForceLocalDisable(): Promise<void> {
    await this.post200("/localapi/v0/tka/force-local-disable", "{}");
  }

  async networkLockVerifySigningDeeplink(url: string): Promise<Record<string, unknown>> {
    const body = JSON.stringify({ URL: url });
    const data = await this.post200("/localapi/v0/tka/verify-deeplink", body);
    return JSON.parse(data.toString("utf-8"));
  }

  async networkLockGenRecoveryAum(removeKeys: string[], forkFrom: string): Promise<Buffer> {
    const body = JSON.stringify({ Keys: removeKeys, ForkFrom: forkFrom });
    return this.post200("/localapi/v0/tka/generate-recovery-aum", body);
  }

  async networkLockCosignRecoveryAum(aum: Buffer): Promise<Buffer> {
    return this.post200("/localapi/v0/tka/cosign-recovery-aum", aum);
  }

  async networkLockSubmitRecoveryAum(aum: Buffer): Promise<void> {
    await this.post200("/localapi/v0/tka/submit-recovery-aum", aum);
  }

  async networkLockDisable(secret: Buffer): Promise<void> {
    await this.post200("/localapi/v0/tka/disable", secret);
  }

  // --- Debug ---

  async debugAction(action: string): Promise<void> {
    await this.post200(`/localapi/v0/debug?action=${encodeURIComponent(action)}`);
  }

  async debugActionBody(action: string, body: Buffer | string): Promise<void> {
    await this.post200(`/localapi/v0/debug?action=${encodeURIComponent(action)}`, body);
  }

  async debugResultJson(action: string): Promise<unknown> {
    const data = await this.post200(
      `/localapi/v0/debug?action=${encodeURIComponent(action)}`,
    );
    return JSON.parse(data.toString("utf-8"));
  }

  async debugPacketFilterRules(): Promise<unknown[]> {
    const data = await this.post200("/localapi/v0/debug-packet-filter-rules");
    return JSON.parse(data.toString("utf-8"));
  }

  async debugSetExpireIn(secs: number): Promise<void> {
    const expiry = Math.floor(Date.now() / 1000) + secs;
    await this.post200(`/localapi/v0/set-expiry-sooner?expiry=${expiry}`);
  }

  async eventBusGraph(): Promise<string> {
    const data = await this.get200("/localapi/v0/debug-bus-graph");
    return data.toString("utf-8");
  }

  async queryFeature(feature: string): Promise<Record<string, unknown>> {
    const data = await this.post200(
      `/localapi/v0/query-feature?feature=${encodeURIComponent(feature)}`,
    );
    return JSON.parse(data.toString("utf-8"));
  }

  async checkUpdate(): Promise<ClientVersion> {
    const data = await this.get200("/localapi/v0/update/check");
    return JSON.parse(data.toString("utf-8"));
  }

  destroy(): void {
    this.transport.destroy();
  }
}
