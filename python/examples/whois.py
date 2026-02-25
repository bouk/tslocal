"""Look up the owner of an IP address and print as JSON."""

import asyncio
import json
import sys

import msgspec

from tslocalapi import LocalClient


async def main() -> None:
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <addr>", file=sys.stderr)
        sys.exit(1)

    async with LocalClient() as client:
        resp = await client.who_is(sys.argv[1])
        json.dump(msgspec.to_builtins(resp), sys.stdout, indent=2)
        sys.stdout.write("\n")


asyncio.run(main())
