"""Tailscale Local API client."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import quote

import msgspec

from tslocalapi._errors import (
    AccessDeniedError,
    ConnectionError,
    DaemonNotRunningError,
    HttpError,
    PeerNotFoundError,
    PreconditionsFailedError,
    error_message_from_body,
)
from tslocalapi._transport import Transport
from tslocalapi._types import (
    ClientVersion,
    DERPMap,
    DNSOSConfig,
    ExitNodeSuggestionResponse,
    FileTarget,
    LoginProfile,
    MaskedPrefs,
    OptionalFeatures,
    PingResult,
    Prefs,
    ProfileStatus,
    ReloadConfigResponse,
    Status,
    WaitingFile,
    WhoIsResponse,
)


class LocalClient:
    """Async client for the Tailscale Local API.

    Connections are reused via HTTP/1.1 keep-alive.
    """

    def __init__(
        self,
        socket_path: str | None = None,
        tcp_port: int | None = None,
        token: str | None = None,
        use_socket_only: bool = False,
    ) -> None:
        self._transport = Transport(
            socket_path=socket_path,
            tcp_port=tcp_port,
            token=token,
            use_socket_only=use_socket_only,
        )

    async def _do_request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        """Send a request and return (status, body)."""
        try:
            return await self._transport.request(method, path, body, headers)
        except OSError as e:
            if "Connection refused" in str(e) or "No such file" in str(e):
                raise DaemonNotRunningError(str(e)) from e
            raise ConnectionError(str(e)) from e

    async def _do_request_nice(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        """Send a request and map error status codes to exceptions."""
        status, resp_body = await self._do_request(method, path, body, headers)
        if 200 <= status < 300:
            return resp_body

        msg = error_message_from_body(resp_body)
        if msg is None:
            msg = resp_body.decode("utf-8", errors="replace")

        if status == 403:
            raise AccessDeniedError(msg)
        elif status == 412:
            raise PreconditionsFailedError(msg)
        else:
            raise HttpError(status, msg)

    async def _get200(self, path: str) -> bytes:
        return await self._do_request_nice("GET", path)

    async def _post200(self, path: str, body: bytes | None = None) -> bytes:
        return await self._do_request_nice("POST", path, body)

    # --- Status ---

    async def status(self) -> Status:
        """Get the current tailscaled status."""
        data = await self._get200("/localapi/v0/status")
        return msgspec.json.decode(data, type=Status)

    async def status_without_peers(self) -> Status:
        """Get the current tailscaled status without peer information."""
        data = await self._get200("/localapi/v0/status?peers=false")
        return msgspec.json.decode(data, type=Status)

    # --- WhoIs ---

    async def who_is(self, remote_addr: str) -> WhoIsResponse:
        """Look up the owner of an IP address or IP:port."""
        status, body = await self._do_request(
            "GET", f"/localapi/v0/whois?addr={quote(remote_addr)}"
        )
        if status == 404:
            raise PeerNotFoundError(f"peer not found: {remote_addr}")
        if status != 200:
            msg = error_message_from_body(body) or body.decode("utf-8", errors="replace")
            if status == 403:
                raise AccessDeniedError(msg)
            raise HttpError(status, msg)
        return msgspec.json.decode(body, type=WhoIsResponse)

    async def who_is_node_key(self, node_key: str) -> WhoIsResponse:
        """Look up a peer by node key."""
        return await self.who_is(node_key)

    # --- Auth ---

    async def start_login_interactive(self) -> None:
        """Start an interactive login flow."""
        await self._post200("/localapi/v0/login-interactive")

    async def logout(self) -> None:
        """Log out the current node."""
        await self._post200("/localapi/v0/logout")

    # --- Prefs ---

    async def get_prefs(self) -> Prefs:
        """Get current prefs."""
        data = await self._get200("/localapi/v0/prefs")
        return msgspec.json.decode(data, type=Prefs)

    async def edit_prefs(self, prefs: MaskedPrefs) -> Prefs:
        """Edit prefs with a MaskedPrefs patch."""
        body = msgspec.json.encode(prefs)
        data = await self._do_request_nice("PATCH", "/localapi/v0/prefs", body)
        return msgspec.json.decode(data, type=Prefs)

    async def check_prefs(self, prefs: Prefs) -> None:
        """Validate prefs without making changes."""
        body = msgspec.json.encode(prefs)
        await self._post200("/localapi/v0/check-prefs", body)

    # --- Profiles ---

    async def profile_status(self) -> ProfileStatus:
        """Get profile status (current profile and all profiles)."""
        data = await self._get200("/localapi/v0/profiles/current")
        return msgspec.json.decode(data, type=ProfileStatus)

    async def switch_profile(self, profile_id: str) -> None:
        """Switch to the profile with the given ID."""
        await self._post200(f"/localapi/v0/profiles/{quote(profile_id)}")

    async def switch_to_empty_profile(self) -> None:
        """Switch to an empty (new) profile."""
        await self._do_request_nice("PUT", "/localapi/v0/profiles/")

    async def delete_profile(self, profile_id: str) -> None:
        """Delete the profile with the given ID."""
        await self._do_request_nice(
            "DELETE", f"/localapi/v0/profiles/{quote(profile_id)}"
        )

    # --- DNS ---

    async def set_dns(self, name: str, value: str) -> None:
        """Set a DNS record."""
        await self._post200(
            f"/localapi/v0/dns?name={quote(name)}&value={quote(value)}"
        )

    async def query_dns(self, name: str, query_type: str) -> dict[str, Any]:
        """Query DNS for a name with the given query type."""
        data = await self._get200(
            f"/localapi/v0/dns-query?name={quote(name)}&type={quote(query_type)}"
        )
        return json.loads(data)
    async def get_dns_os_config(self) -> DNSOSConfig:
        """Get the OS DNS configuration."""
        data = await self._get200("/localapi/v0/dns-osconfig")
        return msgspec.json.decode(data, type=DNSOSConfig)

    # --- Diagnostics ---

    async def check_ip_forwarding(self) -> str | None:
        """Check IP forwarding status. Returns warning string if any."""
        data = await self._get200("/localapi/v0/check-ip-forwarding")
        result: dict[str, Any] = json.loads(data)
        warning = result.get("Warning", "")
        return warning if warning else None

    async def check_udp_gro_forwarding(self) -> str | None:
        """Check UDP GRO forwarding status. Returns warning string if any."""
        data = await self._get200("/localapi/v0/check-udp-gro-forwarding")
        result: dict[str, Any] = json.loads(data)
        warning = result.get("Warning", "")
        return warning if warning else None

    async def check_reverse_path_filtering(self) -> str | None:
        """Check reverse path filtering status. Returns warning string if any."""
        data = await self._get200("/localapi/v0/check-reverse-path-filtering")
        result: dict[str, Any] = json.loads(data)
        warning = result.get("Warning", "")
        return warning if warning else None

    async def set_udp_gro_forwarding(self) -> str | None:
        """Set UDP GRO forwarding. Returns warning string if any."""
        data = await self._get200("/localapi/v0/set-udp-gro-forwarding")
        result: dict[str, Any] = json.loads(data)
        warning = result.get("Warning", "")
        return warning if warning else None

    async def check_so_mark_in_use(self) -> bool:
        """Check if SO_MARK is in use (Linux-only)."""
        data = await self._get200("/localapi/v0/check-so-mark-in-use")
        result: dict[str, Any] = json.loads(data)
        return bool(result.get("useSoMark", False))

    async def daemon_metrics(self) -> str:
        """Get daemon metrics in Prometheus format."""
        data = await self._get200("/localapi/v0/metrics")
        return data.decode()

    async def user_metrics(self) -> str:
        """Get user metrics in Prometheus format."""
        data = await self._get200("/localapi/v0/usermetrics")
        return data.decode()

    async def goroutines(self) -> str:
        """Get goroutine dump."""
        data = await self._get200("/localapi/v0/goroutines")
        return data.decode()

    async def pprof(self, pprof_type: str, secs: int) -> bytes:
        """Get pprof profile data."""
        data = await self._get200(
            f"/localapi/v0/pprof?name={quote(pprof_type)}&seconds={secs}"
        )
        return data

    async def get_app_connector_route_info(self) -> dict[str, Any]:
        """Get AppConnector route information."""
        data = await self._get200("/localapi/v0/appc-route-info")
        return json.loads(data)
    async def query_feature(self, feature: str) -> dict[str, Any]:
        """Query a feature (e.g. 'serve', 'funnel')."""
        data = await self._post200(
            f"/localapi/v0/query-feature?feature={quote(feature)}"
        )
        return json.loads(data)
    async def query_optional_features(self) -> OptionalFeatures:
        """Query supported optional features."""
        data = await self._post200("/localapi/v0/debug-optional-features")
        return msgspec.json.decode(data, type=OptionalFeatures)

    async def check_update(self) -> ClientVersion:
        """Check for available updates."""
        data = await self._get200("/localapi/v0/update/check")
        return msgspec.json.decode(data, type=ClientVersion)

    async def id_token(self, aud: str) -> dict[str, Any]:
        """Get an OIDC ID token for the given audience."""
        data = await self._get200(f"/localapi/v0/id-token?aud={quote(aud)}")
        return json.loads(data)
    async def disconnect_control(self) -> None:
        """Disconnect from the control server."""
        await self._post200("/localapi/v0/disconnect-control")

    # --- Ping ---

    async def ping(self, ip: str, ping_type: str = "disco") -> PingResult:
        """Ping a Tailscale IP address."""
        data = await self._post200(
            f"/localapi/v0/ping?ip={quote(ip)}&type={quote(ping_type)}&size=0"
        )
        return msgspec.json.decode(data, type=PingResult)

    async def ping_with_opts(
        self, ip: str, ping_type: str, size: int = 0
    ) -> PingResult:
        """Ping a Tailscale IP address with options."""
        data = await self._post200(
            f"/localapi/v0/ping?ip={quote(ip)}&type={quote(ping_type)}&size={size}"
        )
        return msgspec.json.decode(data, type=PingResult)

    # --- DERP ---

    async def current_derp_map(self) -> DERPMap:
        """Get the current DERP map."""
        data = await self._get200("/localapi/v0/derpmap")
        return msgspec.json.decode(data, type=DERPMap)

    async def debug_derp_region(self, region_id_or_code: str) -> dict[str, Any]:
        """Debug a DERP region."""
        data = await self._post200(
            f"/localapi/v0/debug-derp-region?region={quote(region_id_or_code)}"
        )
        return json.loads(data)
    async def debug_peer_relay_sessions(self) -> dict[str, Any]:
        """Get debug peer relay sessions."""
        data = await self._get200("/localapi/v0/debug-peer-relay-sessions")
        return json.loads(data)
    # --- Certificates ---

    async def cert_pair(self, domain: str) -> tuple[bytes, bytes]:
        """Get a TLS certificate pair (cert_pem, key_pem) for a domain."""
        return await self.cert_pair_with_validity(domain, 0)

    async def cert_pair_with_validity(
        self, domain: str, min_validity_secs: int = 0
    ) -> tuple[bytes, bytes]:
        """Get a TLS certificate pair with minimum validity."""
        data = await self._get200(
            f"/localapi/v0/cert/{quote(domain)}?type=pair&min_validity={min_validity_secs}s"
        )
        # Response is key PEM + "--\n--" + cert PEM
        delimiter = b"--\n--"
        idx = data.find(delimiter)
        if idx == -1:
            return data, b""
        key_pem = data[: idx + 3]  # includes the "--"
        cert_pem = data[idx + 3 :]  # starts with "--"
        return cert_pem, key_pem

    # --- Config ---

    async def get_serve_config(self) -> tuple[dict[str, Any], str]:
        """Get the current serve config. Returns (config, etag)."""
        status, body = await self._do_request("GET", "/localapi/v0/serve-config")
        if status != 200:
            msg = error_message_from_body(body) or body.decode()
            raise HttpError(status, msg)
        # ETag would come from response headers; for now return empty
        return json.loads(body), ""

    async def set_serve_config(self, config: dict[str, Any], etag: str = "") -> None:
        """Set the serve config."""
        headers: dict[str, str] = {}
        if etag:
            headers["If-Match"] = etag
        body = json.dumps(config).encode()
        await self._do_request_nice(
            "POST", "/localapi/v0/serve-config", body, headers
        )

    # --- Exit Node ---

    async def set_use_exit_node(self, enabled: bool) -> None:
        """Enable or disable the exit node."""
        val = "true" if enabled else "false"
        await self._post200(f"/localapi/v0/set-use-exit-node-enabled?enabled={val}")

    async def suggest_exit_node(self) -> ExitNodeSuggestionResponse:
        """Get a suggested exit node."""
        data = await self._get200("/localapi/v0/suggest-exit-node")
        return msgspec.json.decode(data, type=ExitNodeSuggestionResponse)

    # --- Taildrop (File Sharing) ---

    async def waiting_files(self) -> list[WaitingFile]:
        """Get the list of waiting files."""
        data = await self._get200("/localapi/v0/files/?waitsec=0")
        return msgspec.json.decode(data, type=list[WaitingFile])

    async def await_waiting_files(self, wait_secs: int) -> list[WaitingFile]:
        """Wait for files and return them. Blocks up to wait_secs."""
        data = await self._get200(f"/localapi/v0/files/?waitsec={wait_secs}")
        return msgspec.json.decode(data, type=list[WaitingFile])

    async def delete_waiting_file(self, base_name: str) -> None:
        """Delete a waiting file by name."""
        await self._do_request_nice(
            "DELETE", f"/localapi/v0/files/{quote(base_name)}"
        )

    async def file_targets(self) -> list[FileTarget]:
        """Get the list of file targets (peers that can receive files)."""
        data = await self._get200("/localapi/v0/file-targets")
        return msgspec.json.decode(data, type=list[FileTarget])

    async def push_file(self, target: str, name: str, data: bytes) -> None:
        """Send a file to a target peer."""
        await self._do_request_nice(
            "PUT", f"/localapi/v0/file-put/{quote(target)}/{quote(name)}", data
        )

    # --- Taildrive (Drive Shares) ---

    async def drive_share_list(self) -> list[dict[str, Any]]:
        """List drive shares."""
        data = await self._get200("/localapi/v0/drive/shares")
        return json.loads(data)
    async def drive_share_set(self, share: dict[str, Any]) -> None:
        """Set a drive share."""
        body = json.dumps(share).encode()
        await self._do_request_nice("PUT", "/localapi/v0/drive/shares", body)

    async def drive_share_remove(self, name: str) -> None:
        """Remove a drive share by name."""
        await self._do_request_nice(
            "DELETE", "/localapi/v0/drive/shares", name.encode()
        )

    async def drive_share_rename(self, old_name: str, new_name: str) -> None:
        """Rename a drive share."""
        body = json.dumps([old_name, new_name]).encode()
        await self._post200("/localapi/v0/drive/shares", body)

    async def drive_set_server_addr(self, addr: str) -> None:
        """Set the drive fileserver address."""
        await self._do_request_nice(
            "PUT", "/localapi/v0/drive/fileserver-address", addr.encode()
        )

    # --- Network Lock ---

    async def network_lock_status(self) -> dict[str, Any]:
        """Get network lock status."""
        data = await self._get200("/localapi/v0/tka/status")
        return json.loads(data)
    async def network_lock_init(
        self,
        keys: Any,
        disablement_values: list[list[int]],
        support_disablement: list[int],
    ) -> dict[str, Any]:
        """Initialize network lock."""
        body = json.dumps(
            {
                "Keys": keys,
                "DisablementValues": disablement_values,
                "SupportDisablement": support_disablement,
            }
        ).encode()
        data = await self._post200("/localapi/v0/tka/init", body)
        return json.loads(data)
    async def network_lock_wrap_preauth_key(
        self, ts_key: str, tka_key: str
    ) -> str:
        """Wrap a preauth key with network lock."""
        body = json.dumps({"TSKey": ts_key, "TKAKey": tka_key}).encode()
        data = await self._post200("/localapi/v0/tka/wrap-preauth-key", body)
        return data.decode()

    async def network_lock_modify(
        self, add_keys: Any, remove_keys: Any
    ) -> None:
        """Modify network lock keys."""
        body = json.dumps(
            {"AddKeys": add_keys, "RemoveKeys": remove_keys}
        ).encode()
        await self._post200("/localapi/v0/tka/modify", body)

    async def network_lock_sign(
        self, node_key: str, rotation_public: list[int]
    ) -> None:
        """Sign a node key for network lock."""
        body = json.dumps(
            {"NodeKey": node_key, "RotationPublic": rotation_public}
        ).encode()
        await self._post200("/localapi/v0/tka/sign", body)

    async def network_lock_affected_sigs(
        self, key_id: bytes
    ) -> dict[str, Any]:
        """Get affected signatures for a key ID."""
        data = await self._post200("/localapi/v0/tka/affected-sigs", key_id)
        return json.loads(data)
    async def network_lock_log(self, max_entries: int) -> dict[str, Any]:
        """Get network lock log entries."""
        data = await self._get200(f"/localapi/v0/tka/log?limit={max_entries}")
        return json.loads(data)
    async def network_lock_force_local_disable(self) -> None:
        """Force local disable of network lock."""
        await self._post200("/localapi/v0/tka/force-local-disable", b"{}")

    async def network_lock_verify_signing_deeplink(
        self, url: str
    ) -> dict[str, Any]:
        """Verify a network lock signing deeplink."""
        body = json.dumps({"URL": url}).encode()
        data = await self._post200("/localapi/v0/tka/verify-deeplink", body)
        return json.loads(data)
    async def network_lock_gen_recovery_aum(
        self, remove_keys: Any, fork_from: str
    ) -> bytes:
        """Generate a recovery AUM."""
        body = json.dumps(
            {"Keys": remove_keys, "ForkFrom": fork_from}
        ).encode()
        return await self._post200(
            "/localapi/v0/tka/generate-recovery-aum", body
        )

    async def network_lock_cosign_recovery_aum(self, aum: bytes) -> bytes:
        """Cosign a recovery AUM."""
        return await self._post200("/localapi/v0/tka/cosign-recovery-aum", aum)

    async def network_lock_submit_recovery_aum(self, aum: bytes) -> None:
        """Submit a recovery AUM."""
        await self._post200("/localapi/v0/tka/submit-recovery-aum", aum)

    async def network_lock_disable(self, secret: bytes) -> None:
        """Disable network lock with a disablement secret."""
        await self._post200("/localapi/v0/tka/disable", secret)

    # --- Metrics ---

    async def increment_counter(self, name: str, delta: int) -> None:
        """Increment a user metric counter."""
        body = json.dumps(
            [{"Name": name, "Type": "counter", "Value": delta}]
        ).encode()
        await self._post200("/localapi/v0/upload-client-metrics", body)

    async def increment_gauge(self, name: str, delta: int) -> None:
        """Increment a user metric gauge."""
        body = json.dumps(
            [{"Name": name, "Type": "gauge", "Value": delta, "Op": "add"}]
        ).encode()
        await self._post200("/localapi/v0/upload-client-metrics", body)

    async def set_gauge(self, name: str, value: int) -> None:
        """Set a user metric gauge to a value."""
        body = json.dumps(
            [{"Name": name, "Type": "gauge", "Value": value, "Op": "set"}]
        ).encode()
        await self._post200("/localapi/v0/upload-client-metrics", body)

    # --- Logging ---

    async def set_component_debug_logging(
        self, component: str, secs: int
    ) -> None:
        """Enable debug logging for a component for the given duration."""
        data = await self._post200(
            f"/localapi/v0/component-debug-logging?component={quote(component)}&secs={secs}"
        )
        result: dict[str, Any] = json.loads(data)
        error = result.get("Error", "")
        if error:
            raise HttpError(500, error)

    async def set_dev_store_key_value(self, key: str, value: str) -> None:
        """Set a dev store key-value pair."""
        await self._post200(
            f"/localapi/v0/dev-set-state-store?key={quote(key)}&value={quote(value)}"
        )

    # --- Debug ---

    async def debug_action(self, action: str) -> None:
        """Perform a debug action."""
        await self._post200(f"/localapi/v0/debug?action={quote(action)}")

    async def debug_action_body(self, action: str, body: bytes) -> None:
        """Perform a debug action with a body."""
        await self._post200(
            f"/localapi/v0/debug?action={quote(action)}", body
        )

    async def debug_result_json(self, action: str) -> dict[str, Any]:
        """Perform a debug action and return JSON result."""
        data = await self._post200(
            f"/localapi/v0/debug?action={quote(action)}"
        )
        return json.loads(data)
    async def debug_packet_filter_rules(self) -> list[Any]:
        """Get debug packet filter rules."""
        data = await self._post200("/localapi/v0/debug-packet-filter-rules")
        return json.loads(data)
    async def debug_set_expire_in(self, secs: int) -> None:
        """Set key expiry to secs from now."""
        expiry = int(time.time()) + secs
        await self._post200(
            f"/localapi/v0/set-expiry-sooner?expiry={expiry}"
        )

    async def event_bus_graph(self) -> bytes:
        """Get the event bus graph."""
        return await self._get200("/localapi/v0/debug-bus-graph")

    # --- System ---

    async def bug_report(self, note: str = "") -> str:
        """File a bug report. Returns the log marker."""
        data = await self._post200(f"/localapi/v0/bugreport?note={quote(note)}")
        return data.decode().strip()

    async def shutdown_tailscaled(self) -> None:
        """Shut down the tailscaled daemon."""
        await self._post200("/localapi/v0/shutdown")

    async def reload_config(self) -> bool:
        """Reload the daemon config. Returns whether the reload succeeded."""
        data = await self._post200("/localapi/v0/reload-config")
        result = msgspec.json.decode(data, type=ReloadConfigResponse)
        if result.err:
            raise HttpError(500, result.err)
        return result.reloaded

    def close(self) -> None:
        """Close the underlying transport."""
        self._transport.close()

    async def __aenter__(self) -> LocalClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.close()
