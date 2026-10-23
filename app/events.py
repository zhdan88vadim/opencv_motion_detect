from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator
from typing import Any

log = logging.getLogger(__name__)


class EventBus:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._subs: set[asyncio.Queue[str]] = set()
        self._lock = threading.Lock()

    async def subscribe(self) -> AsyncIterator[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=32)
        with self._lock:
            self._subs.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            with self._lock:
                self._subs.discard(q)

    def publish_threadsafe(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, default=str)
        asyncio.run_coroutine_threadsafe(self._broadcast(data), self._loop)

    async def _broadcast(self, data: str) -> None:
        with self._lock:
            queues = list(self._subs)
        for q in queues:
            if q.full():
                try:
                    q.get_nowait()  # drop oldest
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

    async def close(self) -> None:
        with self._lock:
            for q in self._subs:
                try:
                    q.put_nowait('{"kind":"shutdown"}')
                except asyncio.QueueFull:
                    pass
