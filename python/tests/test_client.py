"""Tests for the LocalClient using a mock HTTP server."""

from __future__ import annotations

import http.server
import json
import socket
import threading
from typing import Any

import pytest

from tslocalapi._client import LocalClient
from tslocalapi._errors import (
    AccessDeniedError,
    HttpError,
    PeerNotFoundError,
    PreconditionsFailedError,
)


class MockHandler(http.server.BaseHTTPRequestHandler):
    """Mock HTTP handler that returns predefined responses."""

    responses: dict[str, tuple[int, dict[str, Any] | list[Any] | str | bytes]] = {}
    last_method: str = ""
    last_path: str = ""
    last_body: bytes = b""
    last_headers: dict[str, str] = {}

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def _handle(self) -> None:
        # Check required headers
        cap = self.headers.get("Tailscale-Cap")
        host = self.headers.get("Host")
        assert cap == "131", f"Expected Tailscale-Cap: 131, got {cap}"
        assert host == "local-tailscaled.sock", f"Expected Host: local-tailscaled.sock, got {host}"

        # Record request details
        MockHandler.last_method = self.command
        MockHandler.last_path = self.path
        content_length = int(self.headers.get("Content-Length", 0))
        MockHandler.last_body = self.rfile.read(content_length) if content_length else b""
        MockHandler.last_headers = dict(self.headers)

        path = self.path
        if path in self.responses:
            status, body = self.responses[path]
        else:
            status = 404
            body = {"error": "not found"}

        if isinstance(body, (dict, list)):
            body_bytes = json.dumps(body).encode()
        elif isinstance(body, bytes):
            body_bytes = body
        else:
            body_bytes = body.encode()

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress log output


@pytest.fixture
def mock_server() -> tuple[http.server.HTTPServer, int]:
    """Create a mock HTTP server on a random port."""
    # Find free port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = http.server.HTTPServer(("127.0.0.1", port), MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield server, port

    server.shutdown()


def make_client(port: int) -> LocalClient:
    """Create a client pointing at the mock server."""
    return LocalClient(tcp_port=port, token="test-token", use_socket_only=False)


def test_status(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/status": (
            200,
            {
                "Version": "1.94.1",
                "BackendState": "Running",
                "TUN": True,
                "Self": {
                    "ID": "n123",
                    "PublicKey": "key123",
                    "HostName": "myhost",
                    "DNSName": "myhost.example.ts.net.",
                    "OS": "linux",
                    "TailscaleIPs": ["100.64.0.1"],
                    "Online": True,
                    "Relay": "",
                    "ExitNode": False,
                    "ExitNodeOption": False,
                    "UserID": 1,
                },
                "Peer": {},
                "AuthURL": "",
            },
        ),
    }

    client = make_client(port)
    status = client.status()
    assert status.version == "1.94.1"
    assert status.backend_state == "Running"
    assert status.self_node is not None
    assert status.self_node.host_name == "myhost"
    client.close()


def test_status_without_peers(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/status?peers=false": (
            200,
            {
                "Version": "1.94.1",
                "BackendState": "Running",
                "TUN": True,
                "Peer": {},
                "AuthURL": "",
            },
        ),
    }

    client = make_client(port)
    status = client.status_without_peers()
    assert status.version == "1.94.1"
    client.close()


def test_whois_not_found(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/whois?addr=1.2.3.4": (404, {"error": "peer not found"}),
    }

    client = make_client(port)
    with pytest.raises(PeerNotFoundError):
        client.who_is("1.2.3.4")
    client.close()


def test_access_denied(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/status": (403, {"error": "access denied"}),
    }

    client = make_client(port)
    with pytest.raises(AccessDeniedError):
        client.status()
    client.close()


def test_preconditions_failed(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/status": (412, {"error": "state mismatch"}),
    }

    client = make_client(port)
    with pytest.raises(PreconditionsFailedError):
        client.status()
    client.close()


def test_http_error(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/status": (500, {"error": "internal error"}),
    }

    client = make_client(port)
    with pytest.raises(HttpError) as exc_info:
        client.status()
    assert exc_info.value.status == 500
    client.close()


def test_get_prefs(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/prefs": (
            200,
            {
                "ControlURL": "https://controlplane.tailscale.com",
                "RouteAll": False,
                "ExitNodeID": "",
                "ExitNodeIP": "",
                "ExitNodeAllowLANAccess": False,
                "CorpDNS": True,
                "RunSSH": False,
                "WantRunning": True,
                "ShieldsUp": False,
                "Hostname": "myhost",
                "AdvertiseTags": [],
            },
        ),
    }

    client = make_client(port)
    prefs = client.get_prefs()
    assert prefs.control_url == "https://controlplane.tailscale.com"
    assert prefs.want_running is True
    client.close()


def test_auth_header_sent(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    """Verify that the auth token is sent as Basic auth."""
    _, port = mock_server
    received_auth: list[str] = []

    original_handle = MockHandler._handle

    def capture_auth(self: MockHandler) -> None:
        auth = self.headers.get("Authorization", "")
        received_auth.append(auth)
        original_handle(self)

    MockHandler._handle = capture_auth  # type: ignore[assignment]
    MockHandler.responses = {
        "/localapi/v0/status": (200, {"Version": "1.94.1", "BackendState": "Running", "TUN": False, "Peer": {}, "AuthURL": ""}),
    }

    try:
        client = make_client(port)
        client.status()
        assert len(received_auth) > 0
        assert received_auth[0].startswith("Basic ")
        client.close()
    finally:
        MockHandler._handle = original_handle  # type: ignore[assignment]


# --- Ping ---


def test_ping(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/ping?ip=100.64.0.1&type=disco&size=0": (
            200,
            {
                "IP": "100.64.0.1",
                "NodeIP": "100.64.0.1",
                "NodeName": "myhost",
                "Err": "",
                "LatencySeconds": 0.005,
                "Endpoint": "1.2.3.4:41641",
                "DERPRegionID": 0,
                "DERPRegionCode": "",
            },
        ),
    }

    client = make_client(port)
    result = client.ping("100.64.0.1")
    assert result.ip == "100.64.0.1"
    assert result.node_name == "myhost"
    assert result.latency_seconds == 0.005
    assert MockHandler.last_method == "POST"
    client.close()


def test_ping_with_opts(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/ping?ip=100.64.0.1&type=TSMP&size=512": (
            200,
            {
                "IP": "100.64.0.1",
                "NodeIP": "100.64.0.1",
                "NodeName": "myhost",
                "Err": "",
                "LatencySeconds": 0.01,
            },
        ),
    }

    client = make_client(port)
    result = client.ping_with_opts("100.64.0.1", "TSMP", size=512)
    assert result.latency_seconds == 0.01
    client.close()


# --- DERP ---


def test_current_derp_map(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/derpmap": (
            200,
            {
                "Regions": {
                    "1": {
                        "RegionID": 1,
                        "RegionCode": "nyc",
                        "RegionName": "New York City",
                        "Nodes": [],
                    }
                }
            },
        ),
    }

    client = make_client(port)
    derp_map = client.current_derp_map()
    assert "1" in derp_map.regions
    assert derp_map.regions["1"].region_code == "nyc"
    client.close()


# --- Certificates ---


def test_cert_pair(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    key_pem = b"-----BEGIN PRIVATE KEY-----\nfakekey\n-----END PRIVATE KEY--"
    cert_pem = b"---BEGIN CERTIFICATE-----\nfakecert\n-----END CERTIFICATE-----"
    combined = key_pem + b"\n" + cert_pem
    MockHandler.responses = {
        "/localapi/v0/cert/example.ts.net?type=pair&min_validity=0s": (
            200,
            combined,
        ),
    }

    client = make_client(port)
    cert, key = client.cert_pair("example.ts.net")
    assert b"CERTIFICATE" in cert
    assert b"PRIVATE KEY" in key
    client.close()


# --- Diagnostics ---


def test_check_ip_forwarding_no_warning(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/check-ip-forwarding": (200, {"Warning": ""}),
    }

    client = make_client(port)
    result = client.check_ip_forwarding()
    assert result is None
    client.close()


def test_check_ip_forwarding_with_warning(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/check-ip-forwarding": (200, {"Warning": "IP forwarding is disabled"}),
    }

    client = make_client(port)
    result = client.check_ip_forwarding()
    assert result == "IP forwarding is disabled"
    client.close()


def test_check_udp_gro_forwarding(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/check-udp-gro-forwarding": (200, {"Warning": ""}),
    }

    client = make_client(port)
    result = client.check_udp_gro_forwarding()
    assert result is None
    client.close()


def test_check_so_mark_in_use(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/check-so-mark-in-use": (200, {"useSoMark": True}),
    }

    client = make_client(port)
    result = client.check_so_mark_in_use()
    assert result is True
    client.close()


def test_daemon_metrics(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/metrics": (200, "tailscaled_inbound_bytes_total 1234"),
    }

    client = make_client(port)
    metrics = client.daemon_metrics()
    assert "tailscaled_inbound_bytes_total" in metrics
    client.close()


def test_goroutines(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/goroutines": (200, "goroutine 1 [running]:"),
    }

    client = make_client(port)
    output = client.goroutines()
    assert "goroutine" in output
    client.close()


def test_pprof(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/pprof?name=heap&seconds=30": (200, b"pprof-data"),
    }

    client = make_client(port)
    data = client.pprof("heap", 30)
    assert data == b"pprof-data"
    client.close()


def test_query_feature(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/query-feature?feature=serve": (200, {"Complete": True}),
    }

    client = make_client(port)
    result = client.query_feature("serve")
    assert result["Complete"] is True
    assert MockHandler.last_method == "POST"
    client.close()


def test_check_update(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/update/check": (
            200,
            {"RunningLatest": True, "LatestVersion": ""},
        ),
    }

    client = make_client(port)
    result = client.check_update()
    assert result.running_latest is True
    client.close()


def test_id_token(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/id-token?aud=https%3A//example.com": (
            200,
            {"IDToken": "fake-token"},
        ),
    }

    client = make_client(port)
    result = client.id_token("https://example.com")
    assert result["IDToken"] == "fake-token"
    client.close()


# --- Taildrop ---


def test_waiting_files(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/files/?waitsec=0": (
            200,
            [{"Name": "hello.txt", "Size": 42}],
        ),
    }

    client = make_client(port)
    files = client.waiting_files()
    assert len(files) == 1
    assert files[0].name == "hello.txt"
    assert files[0].size == 42
    client.close()


def test_delete_waiting_file(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/files/hello.txt": (200, ""),
    }

    client = make_client(port)
    client.delete_waiting_file("hello.txt")
    assert MockHandler.last_method == "DELETE"
    client.close()


def test_file_targets(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/file-targets": (
            200,
            [{"Node": {"ID": 1, "Name": "peer"}, "PeerAPIURL": "http://100.64.0.2:1234"}],
        ),
    }

    client = make_client(port)
    targets = client.file_targets()
    assert len(targets) == 1
    assert targets[0].peer_api_url == "http://100.64.0.2:1234"
    client.close()


def test_push_file(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/file-put/stable-id-123/test.txt": (200, ""),
    }

    client = make_client(port)
    client.push_file("stable-id-123", "test.txt", b"file content")
    assert MockHandler.last_method == "PUT"
    assert MockHandler.last_body == b"file content"
    client.close()


# --- Taildrive ---


def test_drive_share_list(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/drive/shares": (
            200,
            [{"Name": "photos", "Path": "/home/user/photos"}],
        ),
    }

    client = make_client(port)
    shares = client.drive_share_list()
    assert len(shares) == 1
    assert shares[0]["Name"] == "photos"
    assert MockHandler.last_method == "GET"
    client.close()


def test_drive_share_set(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/drive/shares": (200, ""),
    }

    client = make_client(port)
    client.drive_share_set({"Name": "photos", "Path": "/home/user/photos"})
    assert MockHandler.last_method == "PUT"
    body = json.loads(MockHandler.last_body)
    assert body["Name"] == "photos"
    client.close()


def test_drive_share_remove(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/drive/shares": (200, ""),
    }

    client = make_client(port)
    client.drive_share_remove("photos")
    assert MockHandler.last_method == "DELETE"
    assert MockHandler.last_body == b"photos"
    client.close()


def test_drive_share_rename(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/drive/shares": (200, ""),
    }

    client = make_client(port)
    client.drive_share_rename("old-name", "new-name")
    assert MockHandler.last_method == "POST"
    body = json.loads(MockHandler.last_body)
    assert body == ["old-name", "new-name"]
    client.close()


# --- Network Lock ---


def test_network_lock_status(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/tka/status": (200, {"Enabled": False, "PublicKey": ""}),
    }

    client = make_client(port)
    result = client.network_lock_status()
    assert result["Enabled"] is False
    client.close()


def test_network_lock_force_local_disable(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/tka/force-local-disable": (200, ""),
    }

    client = make_client(port)
    client.network_lock_force_local_disable()
    assert MockHandler.last_method == "POST"
    assert MockHandler.last_body == b"{}"
    client.close()


# --- Metrics ---


def test_increment_counter(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/upload-client-metrics": (200, ""),
    }

    client = make_client(port)
    client.increment_counter("my_counter", 5)
    body = json.loads(MockHandler.last_body)
    assert body == [{"Name": "my_counter", "Type": "counter", "Value": 5}]
    client.close()


def test_set_gauge(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/upload-client-metrics": (200, ""),
    }

    client = make_client(port)
    client.set_gauge("my_gauge", 42)
    body = json.loads(MockHandler.last_body)
    assert body == [{"Name": "my_gauge", "Type": "gauge", "Value": 42, "Op": "set"}]
    client.close()


# --- Debug ---


def test_debug_action(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/debug?action=rebind": (200, ""),
    }

    client = make_client(port)
    client.debug_action("rebind")
    assert MockHandler.last_method == "POST"
    client.close()


def test_debug_packet_filter_rules(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/debug-packet-filter-rules": (
            200,
            [{"SrcIPs": ["*"], "DstPorts": [{"IP": "*", "Ports": {"First": 0, "Last": 65535}}]}],
        ),
    }

    client = make_client(port)
    rules = client.debug_packet_filter_rules()
    assert len(rules) == 1
    assert MockHandler.last_method == "POST"
    client.close()


# --- System ---


def test_bug_report(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/bugreport?note=test%20note": (200, "BUG-12345\n"),
    }

    client = make_client(port)
    marker = client.bug_report("test note")
    assert marker == "BUG-12345"
    client.close()


def test_reload_config_success(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/reload-config": (200, {"Reloaded": True, "Err": ""}),
    }

    client = make_client(port)
    result = client.reload_config()
    assert result is True
    client.close()


def test_reload_config_error(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/reload-config": (200, {"Reloaded": False, "Err": "config not found"}),
    }

    client = make_client(port)
    with pytest.raises(HttpError) as exc_info:
        client.reload_config()
    assert "config not found" in str(exc_info.value)
    client.close()


def test_reload_config_no_config(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/reload-config": (200, {"Reloaded": False, "Err": ""}),
    }

    client = make_client(port)
    result = client.reload_config()
    assert result is False
    client.close()


# --- Exit Node ---


def test_suggest_exit_node(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/suggest-exit-node": (
            200,
            {"ID": "stable-123", "Name": "us-exit", "Location": {"Country": "US", "City": "New York"}},
        ),
    }

    client = make_client(port)
    result = client.suggest_exit_node()
    assert result.id == "stable-123"
    assert result.name == "us-exit"
    client.close()


# --- DNS ---


def test_query_dns(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/dns-query?name=example.com&type=A": (
            200,
            {"Bytes": "AAAA", "Resolvers": []},
        ),
    }

    client = make_client(port)
    result = client.query_dns("example.com", "A")
    assert result["Bytes"] == "AAAA"
    client.close()


def test_get_dns_os_config(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/dns-osconfig": (
            200,
            {"Nameservers": ["8.8.8.8"], "SearchDomains": ["ts.net"], "MatchDomains": []},
        ),
    }

    client = make_client(port)
    result = client.get_dns_os_config()
    assert result.nameservers == ["8.8.8.8"]
    assert result.search_domains == ["ts.net"]
    client.close()


# --- Optional Features ---


def test_query_optional_features(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/debug-optional-features": (
            200,
            {"Features": {"serve": True, "funnel": False}},
        ),
    }

    client = make_client(port)
    result = client.query_optional_features()
    assert result.features["serve"] is True
    assert result.features["funnel"] is False
    assert MockHandler.last_method == "POST"
    client.close()


# --- Context Manager ---


def test_context_manager(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/status": (
            200,
            {"Version": "1.94.1", "BackendState": "Running", "TUN": False, "Peer": {}, "AuthURL": ""},
        ),
    }

    with make_client(port) as client:
        status = client.status()
        assert status.version == "1.94.1"
