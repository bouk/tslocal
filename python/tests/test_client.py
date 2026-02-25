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


def test_who_is_proto(mock_server: tuple[http.server.HTTPServer, int]) -> None:
    _, port = mock_server
    MockHandler.responses = {
        "/localapi/v0/whois?proto=tcp&addr=100.64.0.1%3A80": (
            200,
            {
                "Node": {"ID": 1, "Name": "myhost"},
                "UserProfile": {"ID": 1, "LoginName": "user@example.com", "DisplayName": "User"},
            },
        ),
    }

    client = make_client(port)
    result = client.who_is_proto("tcp", "100.64.0.1:80")
    assert result.user_profile is not None
    assert result.user_profile.login_name == "user@example.com"
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


# --- ID Token ---


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
