"""Tailscale Local API client."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import msgspec

from tslocal._decode import decode_json
from tslocal._errors import (
    AccessDeniedError,
    ConnectionError,
    DaemonNotRunningError,
    HttpError,
    PeerNotFoundError,
    PreconditionsFailedError,
    error_message_from_body,
)
from tslocal._transport import Transport
from tslocal._types import (
    ServeConfig,
    Status,
    WhoIsResponse,
)


class Client:
    """Client for the Tailscale Local API.

    Connections are reused via HTTP/1.1 keep-alive.
    """

    def __init__(
        self,
        socket_path: str | None = None,
        use_socket_only: bool = False,
    ) -> None:
        self._transport = Transport(
            socket_path=socket_path,
            use_socket_only=use_socket_only,
        )

    def _do_request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        """Send a request and return (status, body, response_headers)."""
        try:
            return self._transport.request(method, path, body, headers)
        except OSError as e:
            if "Connection refused" in str(e) or "No such file" in str(e):
                raise DaemonNotRunningError(str(e)) from e
            raise ConnectionError(str(e)) from e

    def _do_request_nice(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        """Send a request and map error status codes to exceptions."""
        status, resp_body, _ = self._do_request(method, path, body, headers)
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

    def _get200(self, path: str) -> bytes:
        return self._do_request_nice("GET", path)

    def _post200(self, path: str, body: bytes | None = None) -> bytes:
        return self._do_request_nice("POST", path, body)

    # --- Status ---

    def status(self) -> Status:
        """Get the current tailscaled status."""
        data = self._get200("/localapi/v0/status")
        return decode_json(data, Status)

    def status_without_peers(self) -> Status:
        """Get the current tailscaled status without peer information."""
        data = self._get200("/localapi/v0/status?peers=false")
        return decode_json(data, Status)

    # --- WhoIs ---

    def who_is(self, remote_addr: str) -> WhoIsResponse:
        """Look up the owner of an IP address or IP:port."""
        status, body, _ = self._do_request(
            "GET", f"/localapi/v0/whois?addr={quote(remote_addr)}"
        )
        if status == 404:
            raise PeerNotFoundError(f"peer not found: {remote_addr}")
        if status != 200:
            msg = error_message_from_body(body) or body.decode("utf-8", errors="replace")
            if status == 403:
                raise AccessDeniedError(msg)
            raise HttpError(status, msg)
        return decode_json(body, WhoIsResponse)

    def who_is_node_key(self, node_key: str) -> WhoIsResponse:
        """Look up a peer by node key."""
        return self.who_is(node_key)

    def who_is_proto(self, proto: str, remote_addr: str) -> WhoIsResponse:
        """Look up the owner of an IP address with a specific protocol.

        The proto parameter should be "tcp" or "udp".
        """
        status, body, _ = self._do_request(
            "GET",
            f"/localapi/v0/whois?proto={quote(proto)}&addr={quote(remote_addr)}",
        )
        if status == 404:
            raise PeerNotFoundError(f"peer not found: {remote_addr}")
        if status != 200:
            msg = error_message_from_body(body) or body.decode("utf-8", errors="replace")
            if status == 403:
                raise AccessDeniedError(msg)
            raise HttpError(status, msg)
        return decode_json(body, WhoIsResponse)

    # --- Certificates ---

    def cert_pair(self, domain: str) -> tuple[bytes, bytes]:
        """Get a TLS certificate pair (cert_pem, key_pem) for a domain."""
        return self.cert_pair_with_validity(domain, 0)

    def cert_pair_with_validity(
        self, domain: str, min_validity_secs: int = 0
    ) -> tuple[bytes, bytes]:
        """Get a TLS certificate pair with minimum validity."""
        data = self._get200(
            f"/localapi/v0/cert/{quote(domain)}?type=pair&min_validity={min_validity_secs}s"
        )
        # Response is key PEM + "--\n--" + cert PEM
        delimiter = b"--\n--"
        idx = data.find(delimiter)
        if idx == -1:
            raise ValueError("unexpected cert response: no delimiter")
        key_pem = data[: idx + 3]  # includes the "--"
        cert_pem = data[idx + 3 :]  # starts with "--"
        return cert_pem, key_pem

    # --- Config ---

    def get_serve_config(self) -> ServeConfig:
        """Get the current serve config.

        The returned ServeConfig has its e_tag field populated from the
        HTTP Etag response header.
        """
        status, body, resp_headers = self._do_request("GET", "/localapi/v0/serve-config")
        if status != 200:
            msg = error_message_from_body(body) or body.decode()
            raise HttpError(status, msg)
        config = decode_json(body, ServeConfig)
        config.e_tag = resp_headers.get("Etag", resp_headers.get("etag", ""))
        return config

    def set_serve_config(self, config: ServeConfig) -> None:
        """Set the serve config.

        The e_tag field on the config is sent as the If-Match header
        for conditional updates.
        """
        headers: dict[str, str] = {}
        if config.e_tag:
            headers["If-Match"] = config.e_tag
        body = msgspec.json.encode(config)
        self._do_request_nice(
            "POST", "/localapi/v0/serve-config", body, headers
        )

    def close(self) -> None:
        """Close the underlying transport."""
        self._transport.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
