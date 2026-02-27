"""Print the current serve config and its ETag."""

import sys

import msgspec

from tslocal import Client

with Client() as client:
    config = client.get_serve_config()
    print(f"ETag: {config.e_tag}", file=sys.stderr)
    # Reset e_tag to default so omit_defaults excludes it from output
    config.e_tag = ""
    sys.stdout.buffer.write(msgspec.json.format(msgspec.json.encode(config)))
    sys.stdout.write("\n")
