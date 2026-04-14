"""Type definitions for the Tailscale Local API.

This module re-exports types from the generated _generated_types module
and provides additional client-library specific types.
"""

from __future__ import annotations

import msgspec

from tslocal._generated_types import (  # noqa: F401
    Status,
    PeerStatus,
    TailnetStatus,
    ExitNodeStatus,
    UserProfile,
    Node as _GeneratedNode,
    Hostinfo,
    NetInfo,
    Service,
    Location,
    TPMInfo,
    ClientVersion,
    ServeConfig as _GeneratedServeConfig,
    TCPPortHandler,
    WebServerConfig,
    HTTPHandler,
    ServiceConfig,
    WhoIsResponse,
    Resolver,
)


class Node(_GeneratedNode):
    """Node with helper methods."""

    def is_tagged(self) -> bool:
        """Reports whether the node has any ACL tags."""
        return len(self.tags) > 0


class ServeConfig(_GeneratedServeConfig, omit_defaults=True):
    """ServeConfig with ETag field for conditional updates.

    The e_tag field is populated by get_serve_config from the HTTP Etag
    header and used by set_serve_config for the If-Match header.
    """

    e_tag: str = ""


class CurrentTailnet(msgspec.Struct, rename="pascal"):
    """Alias for TailnetStatus for backward compatibility."""

    name: str = ""
    magic_dns_suffix: str = msgspec.field(default="", name="MagicDNSSuffix")
    magic_dns_enabled: bool = msgspec.field(default=False, name="MagicDNSEnabled")
