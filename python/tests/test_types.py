"""Tests for type definitions."""

import msgspec

from tslocal._decode import decode_json
from tslocal._types import (
    CurrentTailnet,
    PeerStatus,
    Status,
    UserProfile,
    WhoIsResponse,
)


def test_status_from_dict() -> None:
    data = {
        "Version": "1.94.1",
        "BackendState": "Running",
        "TUN": True,
        "AuthURL": "",
        "Self": {
            "ID": "n123",
            "PublicKey": "key123",
            "HostName": "myhost",
            "DNSName": "myhost.example.ts.net.",
            "OS": "linux",
            "TailscaleIPs": ["100.64.0.1"],
            "Online": True,
            "Relay": "nyc",
            "ExitNode": False,
            "ExitNodeOption": False,
            "UserID": 1,
        },
        "Peer": {
            "key456": {
                "ID": "n456",
                "PublicKey": "key456",
                "HostName": "otherhost",
                "DNSName": "otherhost.example.ts.net.",
                "OS": "macos",
                "TailscaleIPs": ["100.64.0.2"],
                "Online": True,
                "Relay": "sfo",
                "ExitNode": False,
                "ExitNodeOption": True,
                "UserID": 2,
            }
        },
        "CurrentTailnet": {
            "Name": "example.ts.net",
            "MagicDNSSuffix": "example.ts.net",
            "MagicDNSEnabled": True,
        },
    }
    status = msgspec.convert(data, Status)
    assert status.version == "1.94.1"
    assert status.backend_state == "Running"
    assert status.tun is True
    assert status.self_.host_name == "myhost"
    assert status.self_.tailscale_ips == ["100.64.0.1"]
    assert "key456" in status.peer
    assert status.peer["key456"].host_name == "otherhost"
    assert status.current_tailnet is not None
    assert status.current_tailnet.name == "example.ts.net"


def test_status_to_dict_roundtrip() -> None:
    data = {
        "Version": "1.94.1",
        "BackendState": "Running",
        "TUN": True,
    }
    status = msgspec.convert(data, Status)
    result = msgspec.to_builtins(status)
    assert result["Version"] == "1.94.1"
    assert result["BackendState"] == "Running"


def test_whois_response_from_dict() -> None:
    data = {
        "Node": {"ID": 123, "Name": "myhost"},
        "UserProfile": {
            "ID": 1,
            "LoginName": "user@example.com",
            "DisplayName": "User",
            "ProfilePicURL": "",
        },
    }
    resp = msgspec.convert(data, WhoIsResponse)
    assert resp.node.name == "myhost"
    assert resp.user_profile.login_name == "user@example.com"


def test_null_collections_become_empty() -> None:
    """Go nil slices/maps serialize as JSON null; decode_json should convert them to empty collections."""
    data = msgspec.json.encode(
        {
            "Version": "1.94.1",
            "TUN": True,
            "BackendState": "Running",
            "TailscaleIPs": None,
            "Health": None,
            "CertDomains": None,
            "Peer": None,
            "User": None,
            "Self": {
                "ID": "n1",
                "PublicKey": "key1",
                "TailscaleIPs": None,
                "AllowedIPs": None,
                "Tags": None,
                "PrimaryRoutes": None,
                "Addrs": None,
                "PeerAPIURL": None,
            },
        }
    )
    status = decode_json(data, Status)
    # Top-level collections
    assert status.tailscale_ips == []
    assert status.health == []
    assert status.cert_domains == []
    assert status.peer == {}
    assert status.user == {}
    # Nested struct collections
    assert status.self_.tailscale_ips == []
    assert status.self_.allowed_ips == []
    assert status.self_.tags == []
    assert status.self_.primary_routes == []
    assert status.self_.addrs == []
    assert status.self_.peer_api_url == []


def test_null_collections_in_dict_values() -> None:
    """Collections inside dict-of-struct values should also be converted."""
    data = msgspec.json.encode(
        {
            "Version": "1.94.1",
            "BackendState": "Running",
            "Peer": {
                "key1": {
                    "ID": "n1",
                    "PublicKey": "key1",
                    "TailscaleIPs": None,
                    "Tags": None,
                }
            },
        }
    )
    status = decode_json(data, Status)
    peer = status.peer["key1"]
    assert peer.tailscale_ips == []
    assert peer.tags == []


def test_missing_collections_are_empty() -> None:
    """Absent collection fields (omitempty) should default to empty."""
    data = msgspec.json.encode({"Version": "1.94.1", "BackendState": "Running"})
    status = decode_json(data, Status)
    assert status.peer == {}
    assert status.user == {}
    assert status.health == []
