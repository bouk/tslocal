"""Print tailscaled status as JSON."""

import asyncio
import json
import sys

import msgspec

from tslocalapi import LocalClient


async def main() -> None:
    async with LocalClient() as client:
        status = await client.status()
        json.dump(msgspec.to_builtins(status), sys.stdout, indent=2)
        sys.stdout.write("\n")


asyncio.run(main())
