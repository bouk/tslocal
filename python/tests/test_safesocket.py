"""Tests for safesocket module."""

import os
import platform
from pathlib import Path

from tslocalapi._safesocket import (
    CURRENT_CAP_VERSION,
    LOCAL_API_HOST,
    default_socket_path,
    parse_lsof_output,
)


def test_local_api_host() -> None:
    assert LOCAL_API_HOST == "local-tailscaled.sock"


def test_current_cap_version() -> None:
    assert CURRENT_CAP_VERSION == 131


def test_default_socket_path() -> None:
    path = default_socket_path()
    assert path
    system = platform.system()
    if system == "Darwin":
        assert path == "/var/run/tailscaled.socket"
    elif system == "Linux":
        assert path == "/var/run/tailscale/tailscaled.sock"


def test_parse_lsof_output_found() -> None:
    output = (
        "p1234\n"
        "f5\n"
        "n/Users/someone/Library/Group Containers/"
        "io.tailscale.ipn.macos/sameuserproof-12345-abcdef0123456789abcd\n"
    )
    result = parse_lsof_output(output)
    assert result is not None
    assert result.port == 12345
    assert result.token == "abcdef0123456789abcd"


def test_parse_lsof_output_not_found() -> None:
    output = "p1234\nf5\nn/some/other/file\n"
    assert parse_lsof_output(output) is None


def test_parse_lsof_output_empty() -> None:
    assert parse_lsof_output("") is None


def test_read_macsys_same_user_proof_from_dir(tmp_path: Path) -> None:
    from tslocalapi._safesocket import _read_macsys_same_user_proof

    # Create symlink for port
    port_link = tmp_path / "ipnport"
    os.symlink("8080", port_link)

    # Create token file
    token_file = tmp_path / "sameuserproof-8080"
    token_file.write_text("mytoken123\n")

    result = _read_macsys_same_user_proof(str(tmp_path))
    assert result is not None
    assert result.port == 8080
    assert result.token == "mytoken123"


def test_read_macsys_same_user_proof_missing(tmp_path: Path) -> None:
    from tslocalapi._safesocket import _read_macsys_same_user_proof

    result = _read_macsys_same_user_proof(str(tmp_path))
    assert result is None
