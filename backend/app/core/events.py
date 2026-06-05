"""In-process pub/sub for live training progress.

The training subprocess appends metric points to ``runs/<id>/metrics.jsonl`` and
the API tails that file (see ``features.training.manager``). Tailers publish each
point here; WebSocket clients subscribe per run and receive points in real time.
This keeps the GUI's loss curve / GPU-memory gauges updating live without
polling.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class EventBus:
    """Tiny async fan-out keyed by ``run_id``.

    One asyncio.Queue per subscriber. Publishers never block: a full queue drops
    the oldest point (a stale loss sample is worth less than back-pressure).
    """

    def __init__(self, maxsize: int = 1000) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._maxsize = maxsize

    def subscribe(self, topic: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers[topic].add(q)
        return q

    def unsubscribe(self, topic: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(topic)
        if subs:
            subs.discard(q)
            if not subs:
                self._subscribers.pop(topic, None)

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        for q in list(self._subscribers.get(topic, ())):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await q.put(payload)


bus = EventBus()
