"""Client library for the Tailscale Local API."""

from tslocal._client import Client
from tslocal._errors import (
    TailscaleError,
    AccessDeniedError,
    PreconditionsFailedError,
    PeerNotFoundError,
    ConnectionError as TailscaleConnectionError,
    DaemonNotRunningError,
    HttpError,
)
from tslocal._types import (
    Status,
    PeerStatus,
    UserProfile,
    CurrentTailnet,
    TailnetStatus,
    WhoIsResponse,
    ServeConfig,
    TokenResponse,
    Node,
    Hostinfo,
)

__version__ = "1.0.1"

__all__ = [
    "Client",
    "TailscaleError",
    "AccessDeniedError",
    "PreconditionsFailedError",
    "PeerNotFoundError",
    "TailscaleConnectionError",
    "DaemonNotRunningError",
    "HttpError",
    "Status",
    "PeerStatus",
    "UserProfile",
    "CurrentTailnet",
    "TailnetStatus",
    "WhoIsResponse",
    "ServeConfig",
    "TokenResponse",
    "Node",
    "Hostinfo",
]
