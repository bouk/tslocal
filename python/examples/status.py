"""Print tailscaled status as JSON."""

import json
import sys

import msgspec

from tslocal import Client

with Client() as client:
    status = client.status()
    json.dump(msgspec.to_builtins(status), sys.stdout, indent=2)
    sys.stdout.write("\n")
