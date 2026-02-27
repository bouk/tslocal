"""HTTP transport over Unix socket or TCP for the Tailscale Local API."""

from __future__ import annotations

import http.client
import io
import json
import platform
import socket
from base64 import b64encode
from typing import Any

from tslocal._safesocket import (
    CURRENT_CAP_VERSION,
    LOCAL_API_HOST,
    PortAndToken,
    default_socket_path,
    local_tcp_port_and_token,
)


def _resolve_port_and_token(use_socket_only: bool) -> PortAndToken | None:
    """Discover TCP port and token for this request."""
    if use_socket_only:
        return None
    if platform.system() == "Darwin":
        return local_tcp_port_and_token()
    return None


class Transport:
    """HTTP transport that connects to tailscaled.

    Reuses connections where possible via HTTP/1.1 keep-alive.
    Port and token are discovered per-request (matching Go's behavior),
    so the client adapts to daemon restarts and late starts.
    """

    def __init__(
        self,
        socket_path: str | None = None,
        use_socket_only: bool = False,
    ) -> None:
        self._socket_path = socket_path or default_socket_path()
        self._use_socket_only = use_socket_only
        self._conn: http.client.HTTPConnection | None = None
        self._conn_port: int | None = None

    @classmethod
    def detect(cls) -> Transport:
        """Create a transport with auto-detected settings."""
        return cls()

    def _get_connection(self, port_and_token: PortAndToken | None) -> http.client.HTTPConnection:
        """Get or create an HTTP connection, reusing existing ones."""
        if port_and_token is not None:
            # If port changed, close old connection
            if self._conn is not None and self._conn_port != port_and_token.port:
                self._close_connection()
            if self._conn is not None:
                return self._conn
            self._conn = http.client.HTTPConnection("127.0.0.1", port_and_token.port)
            self._conn_port = port_and_token.port
        else:
            if self._conn is not None and self._conn_port is not None:
                # Was TCP, now Unix — close old connection
                self._close_connection()
            if self._conn is not None:
                return self._conn
            self._conn = _UnixHTTPConnection(self._socket_path)
            self._conn_port = None
        return self._conn

    def _close_connection(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            self._conn_port = None

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        """Send an HTTP request and return (status_code, body, response_headers)."""
        port_and_token = _resolve_port_and_token(self._use_socket_only)

        all_headers: dict[str, str] = {
            "Host": LOCAL_API_HOST,
            "Tailscale-Cap": str(CURRENT_CAP_VERSION),
        }
        if port_and_token is not None:
            cred = b64encode(f":{port_and_token.token}".encode()).decode()
            all_headers["Authorization"] = f"Basic {cred}"
        if headers:
            all_headers.update(headers)

        try:
            conn = self._get_connection(port_and_token)
            conn.request(method, path, body=body, headers=all_headers)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, data, dict(resp.getheaders())
        except (ConnectionError, OSError, http.client.HTTPException):
            # Connection broken, close and retry once
            self._close_connection()
            conn = self._get_connection(port_and_token)
            conn.request(method, path, body=body, headers=all_headers)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, data, dict(resp.getheaders())

    def close(self) -> None:
        """Close the underlying connection."""
        self._close_connection()


class _UnixHTTPConnection(http.client.HTTPConnection):
    """HTTPConnection subclass that connects via Unix domain socket."""

    def __init__(self, socket_path: str) -> None:
        super().__init__(LOCAL_API_HOST)
        self._socket_path = socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self._socket_path)
        self.sock = sock
