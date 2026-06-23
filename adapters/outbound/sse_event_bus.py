"""
Server-Sent Events implementation of IEventBus.

This is the production upgrade path mentioned in the design doc for
stock-sync lag: instead of patrons polling /api/menu every 10s, the
server pushes a stock_update event the instant a decrement happens.

v1 ships this adapter fully implemented, but the patron frontend still
uses polling (see frontend/patron/index.html) — wiring the frontend to
this stream is the next increment, not required for the deliverable's
core guarantee (which is correctness, not latency).
"""
import asyncio
import json
from collections import defaultdict
from typing import Any

from core.ports.event_port import IEventBus


class SSEEventBus(IEventBus):
    def __init__(self):
        # topic -> set of asyncio.Queue, one per connected subscriber
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Synchronous publish — safe to call from a regular (non-async)
        service method. Each subscriber queue is filled without blocking;
        if a queue is full we drop the update rather than risk blocking
        the stock-decrement hot path on a slow consumer."""
        for queue in list(self._subscribers.get(topic, [])):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, topic: str):
        """Async generator yielding SSE-formatted strings. Used directly
        by the FastAPI route as a StreamingResponse body."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[topic].add(queue)
        try:
            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            self._subscribers[topic].discard(queue)
