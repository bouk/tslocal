"""Print the current serve config and its ETag."""

import json
import sys

from tslocalapi import LocalClient

with LocalClient() as client:
    config, etag = client.get_serve_config()
    print(f"ETag: {etag}", file=sys.stderr)
    json.dump(config, sys.stdout, indent=2)
    sys.stdout.write("\n")
