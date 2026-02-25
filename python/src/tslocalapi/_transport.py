"""HTTP transport over Unix socket or TCP for the Tailscale Local API."""

from __future__ import annotations

import asyncio
import http.client
import io
import json
import platform
import socket
from base64 import b64encode
from typing import Any

from tslocalapi._safesocket import (
    CURRENT_CAP_VERSION,
    LOCAL_API_HOST,
    PortAndToken,
    default_socket_path,
    local_tcp_port_and_token,
)


class Transport:
    """HTTP transport that connects to tailscaled.

    Reuses connections where possible via HTTP/1.1 keep-alive.
    """

    def __init__(
        self,
        socket_path: str | None = None,
        tcp_port: int | None = None,
        token: str | None = None,
        use_socket_only: bool = False,
    ) -> None:
        self._socket_path = socket_path or default_socket_path()
        self._tcp_port = tcp_port
        self._token = token
        self._use_socket_only = use_socket_only
        self._conn: http.client.HTTPConnection | None = None

        # Auto-detect macOS TCP if not provided
        if not use_socket_only and tcp_port is None and platform.system() == "Darwin":
            result = local_tcp_port_and_token()
            if result is not None:
                self._tcp_port = result.port
                self._token = result.token

    @classmethod
    def detect(cls) -> Transport:
        """Create a transport with auto-detected settings."""
        return cls()

    @property
    def uses_tcp(self) -> bool:
        return (
            not self._use_socket_only
            and self._tcp_port is not None
            and self._token is not None
        )

    def _get_connection(self) -> http.client.HTTPConnection:
        """Get or create an HTTP connection, reusing existing ones."""
        if self._conn is not None:
            return self._conn

        if self.uses_tcp:
            assert self._tcp_port is not None
            self._conn = http.client.HTTPConnection("127.0.0.1", self._tcp_port)
        else:
            self._conn = _UnixHTTPConnection(self._socket_path)
        return self._conn

    def _close_connection(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    async def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        """Send an HTTP request and return (status_code, body)."""
        all_headers: dict[str, str] = {
            "Host": LOCAL_API_HOST,
            "Tailscale-Cap": str(CURRENT_CAP_VERSION),
        }
        if self.uses_tcp and self._token:
            cred = b64encode(f":{self._token}".encode()).decode()
            all_headers["Authorization"] = f"Basic {cred}"
        if headers:
            all_headers.update(headers)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_request, method, path, body, all_headers
        )

    def _sync_request(
        self,
        method: str,
        path: str,
        body: bytes | None,
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        """Synchronous HTTP request (run in executor for async)."""
        try:
            conn = self._get_connection()
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, data
        except (ConnectionError, OSError, http.client.HTTPException):
            # Connection broken, close and retry once
            self._close_connection()
            conn = self._get_connection()
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, data

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
