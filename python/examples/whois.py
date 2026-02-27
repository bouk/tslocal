"""Look up the owner of an IP address and print as JSON."""

import json
import sys

import msgspec

from tslocal import Client

if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} <addr>", file=sys.stderr)
    sys.exit(1)

with Client() as client:
    resp = client.who_is(sys.argv[1])
    json.dump(msgspec.to_builtins(resp), sys.stdout, indent=2)
    sys.stdout.write("\n")
