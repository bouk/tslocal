"""Exception hierarchy for the Tailscale Local API client."""

from __future__ import annotations

import json
from typing import Any


class TailscaleError(Exception):
    """Base exception for all Tailscale Local API errors."""


class AccessDeniedError(TailscaleError):
    """Raised when the server returns HTTP 403."""


class PreconditionsFailedError(TailscaleError):
    """Raised when the server returns HTTP 412."""


class PeerNotFoundError(TailscaleError):
    """Raised when a WhoIs lookup returns HTTP 404."""


class ConnectionError(TailscaleError):
    """Raised when the connection to tailscaled fails."""


class DaemonNotRunningError(ConnectionError):
    """Raised when tailscaled is not running."""


class HttpError(TailscaleError):
    """Raised for unexpected HTTP status codes."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


def error_message_from_body(body: bytes) -> str | None:
    """Extract error message from a JSON body like Go's errorMessageFromBody."""
    try:
        data: dict[str, Any] = json.loads(body)
        return data.get("error")
    except (json.JSONDecodeError, TypeError):
        return None
