"""Client library for the Tailscale Local API."""

from tslocal._client import LocalClient
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
    Node,
    Hostinfo,
)

__version__ = "0.1.0"

__all__ = [
    "LocalClient",
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
    "Node",
    "Hostinfo",
]
