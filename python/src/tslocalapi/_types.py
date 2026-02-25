"""Type definitions for the Tailscale Local API.

This module re-exports types from the generated _generated_types module
and provides the ProfileStatus type (not in Go source, client-library specific).
"""

from __future__ import annotations

import msgspec

from tslocalapi._generated_types import (  # noqa: F401
    Status,
    PeerStatus,
    TailnetStatus,
    ExitNodeStatus,
    PingResult,
    NetworkLockStatus,
    TKAKey,
    TKAPeer,
    PeerStatusLite,
    UserProfile,
    Node,
    Hostinfo,
    NetInfo,
    Service,
    Location,
    TPMInfo,
    ClientVersion,
    DERPMap,
    DERPRegion,
    DERPNode,
    DERPHomeParams,
    VIPService,
    PortRange,
    ProtoPortRange,
    Prefs,
    MaskedPrefs,
    AutoUpdatePrefs,
    AppConnectorPrefs,
    Notify,
    PartialFile,
    OutgoingFile,
    EngineStatus,
    ServeConfig,
    TCPPortHandler,
    WebServerConfig,
    HTTPHandler,
    ServiceConfig,
    LoginProfile,
    NetworkProfile,
    AutoUpdatePrefsMask,
    WhoIsResponse,
    WaitingFile,
    FileTarget,
    ExitNodeSuggestionResponse,
    ReloadConfigResponse,
    DNSOSConfig,
    DNSQueryResponse,
    OptionalFeatures,
    SetPushDeviceTokenRequest,
    Resolver,
)


class CurrentTailnet(msgspec.Struct, rename="pascal"):
    """Alias for TailnetStatus for backward compatibility."""

    name: str = ""
    magic_dns_suffix: str = msgspec.field(default="", name="MagicDNSSuffix")
    magic_dns_enabled: bool = msgspec.field(default=False, name="MagicDNSEnabled")


class ProfileStatus(msgspec.Struct, rename="pascal"):
    """Profile status containing current and all profiles."""

    current_profile: LoginProfile = msgspec.field(default_factory=LoginProfile)
    all_profiles: list[LoginProfile] = []
