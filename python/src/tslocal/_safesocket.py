"""Platform-specific socket connection to tailscaled."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


LOCAL_API_HOST = "local-tailscaled.sock"
CURRENT_CAP_VERSION = 138


class PortAndToken(NamedTuple):
    port: int
    token: str


def default_socket_path() -> str:
    """Return the default socket path for the current platform."""
    if platform.system() == "Darwin":
        return "/var/run/tailscaled.socket"
    # Linux and other Unix
    return "/var/run/tailscale/tailscaled.sock"


def local_tcp_port_and_token() -> PortAndToken | None:
    """Attempt to discover macOS TCP port and token for tailscaled.

    Returns None if not on macOS or discovery fails.
    """
    if platform.system() != "Darwin":
        return None

    # Try lsof method first (macOS GUI app)
    result = _read_macos_same_user_proof()
    if result is not None:
        return result

    # Try filesystem method (macOS system extension)
    return _read_macsys_same_user_proof()


def _read_macos_same_user_proof() -> PortAndToken | None:
    """Try lsof to find IPNExtension sameuserproof."""
    try:
        uid = os.getuid()
        result = subprocess.run(
            ["lsof", "-n", "-a", f"-u{uid}", "-c", "IPNExtension", "-F"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return parse_lsof_output(result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse_lsof_output(output: str) -> PortAndToken | None:
    """Parse lsof -F output looking for sameuserproof-PORT-TOKEN."""
    needle = ".tailscale.ipn.macos/sameuserproof-"
    for line in output.splitlines():
        idx = line.find(needle)
        if idx == -1:
            continue
        rest = line[idx + len(needle) :]
        dash = rest.find("-")
        if dash == -1:
            continue
        port_str = rest[:dash]
        token = rest[dash + 1 :]
        try:
            port = int(port_str)
            return PortAndToken(port, token)
        except ValueError:
            continue
    return None


def _read_macsys_same_user_proof(
    shared_dir: str = "/Library/Tailscale",
) -> PortAndToken | None:
    """Try filesystem at /Library/Tailscale/ for system extension."""
    try:
        port_path = Path(shared_dir) / "ipnport"
        port_str = os.readlink(port_path)
        port = int(port_str)
        token_path = Path(shared_dir) / f"sameuserproof-{port}"
        token = token_path.read_text().strip()
        return PortAndToken(port, token)
    except (OSError, ValueError):
        return None
