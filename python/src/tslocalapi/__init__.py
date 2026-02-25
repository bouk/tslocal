"""Client library for the Tailscale Local API."""

from tslocalapi._client import LocalClient
from tslocalapi._errors import (
    TailscaleError,
    AccessDeniedError,
    PreconditionsFailedError,
    PeerNotFoundError,
    ConnectionError as TailscaleConnectionError,
    DaemonNotRunningError,
    HttpError,
)
from tslocalapi._types import (
    Status,
    PeerStatus,
    UserProfile,
    CurrentTailnet,
    TailnetStatus,
    WhoIsResponse,
    Notify,
    ServeConfig,
    Node,
    Hostinfo,
)

__version__ = "0.0.4"

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
    "Notify",
    "ServeConfig",
    "Node",
    "Hostinfo",
]
