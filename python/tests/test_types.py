"""Tests for type definitions."""

import msgspec

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
    assert status.self_ is not None
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
    assert resp.node is not None
    assert resp.node.name == "myhost"
    assert resp.user_profile is not None
    assert resp.user_profile.login_name == "user@example.com"
