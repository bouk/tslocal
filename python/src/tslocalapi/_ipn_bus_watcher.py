"""IPNBusWatcher for streaming IPN bus notifications."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator


class Notify:
    """A notification from the IPN bus."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def version(self) -> str:
        return str(self._data.get("Version", ""))

    @property
    def state(self) -> int | None:
        return self._data.get("State")

    @property
    def err_message(self) -> str | None:
        return self._data.get("ErrMessage")

    @property
    def browse_to_url(self) -> str | None:
        return self._data.get("BrowseToURL")

    @property
    def raw(self) -> dict[str, Any]:
        """Access the raw notification data."""
        return self._data

    def __repr__(self) -> str:
        return f"Notify({self._data!r})"


class NotifyWatchOpt:
    """Bitmask options for WatchIPNBus."""

    ENGINE_UPDATES = 1 << 0
    INITIAL_STATE = 1 << 1
    INITIAL_PREFS = 1 << 2
    INITIAL_NETMAP = 1 << 3
    INITIAL_DRIVE_SHARES = 1 << 5
    INITIAL_OUTGOING_FILES = 1 << 6
    INITIAL_HEALTH_STATE = 1 << 7
    RATE_LIMIT = 1 << 8
    HEALTH_ACTIONS = 1 << 9
    INITIAL_SUGGESTED_EXIT_NODE = 1 << 10


class IPNBusWatcher:
    """Async iterator over IPN bus notifications.

    Usage:
        async for notify in watcher:
            print(notify.state)
    """

    def __init__(self, reader: Any) -> None:
        self._reader = reader
        self._closed = False
        self._buffer = b""

    async def next(self) -> Notify:
        """Get the next notification."""
        while True:
            # Check for complete JSON line in buffer
            newline_idx = self._buffer.find(b"\n")
            if newline_idx != -1:
                line = self._buffer[:newline_idx]
                self._buffer = self._buffer[newline_idx + 1 :]
                if line.strip():
                    return Notify(json.loads(line))
                continue

            if self._closed:
                raise StopAsyncIteration

            chunk = await self._reader.read(4096)
            if not chunk:
                raise StopAsyncIteration
            self._buffer += chunk

    async def close(self) -> None:
        """Close the watcher."""
        self._closed = True
        if hasattr(self._reader, "close"):
            self._reader.close()

    def __aiter__(self) -> AsyncIterator[Notify]:
        return self

    async def __anext__(self) -> Notify:
        return await self.next()
