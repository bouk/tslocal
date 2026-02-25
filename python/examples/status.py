"""Print tailscaled status as JSON."""

import json
import sys

import msgspec

from tslocalapi import LocalClient

with LocalClient() as client:
    status = client.status()
    json.dump(msgspec.to_builtins(status), sys.stdout, indent=2)
    sys.stdout.write("\n")
