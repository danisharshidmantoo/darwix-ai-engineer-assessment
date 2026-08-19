from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Set

from darwix.q4.nudges import Nudge


@dataclass
class DashboardEvent:
    event_type: str
    timestamp: float
    nudge_type: str
    priority: int
    message: str
    source_signal_type: str
    evidence: str
    sequence_id: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "nudge_type": self.nudge_type,
            "priority": self.priority,
            "message": self.message,
            "source_signal_type": self.source_signal_type,
            "evidence": self.evidence,
            "sequence_id": self.sequence_id,
        }


class ConnectionManager:
    """Manage WebSocket-compatible client connections.

    Clients are expected to implement an async `send_json(obj)` coroutine.
    """

    def __init__(self):
        self._clients: Set[Any] = set()
        self._lock = asyncio.Lock()

    async def connect(self, client: Any) -> None:
        if client is None:
            raise ValueError("client is None")
        if not hasattr(client, "send_json") or not asyncio.iscoroutinefunction(getattr(client, "send_json")):
            raise ValueError("client must implement async send_json(obj)")
        async with self._lock:
            self._clients.add(client)

    async def disconnect(self, client: Any) -> None:
        async with self._lock:
            self._clients.discard(client)

    async def broadcast(self, event: Dict[str, Any]) -> None:
        # copy clients to avoid mutation during iteration
        async with self._lock:
            clients = list(self._clients)
        if not clients:
            # nothing to do
            return

        # deliver concurrently but isolate failures per-client
        async def _send(c):
            try:
                await c.send_json(event)
            except Exception:
                # on failure, remove the client to avoid repeated errors
                await self.disconnect(c)

        await asyncio.gather(*[_send(c) for c in clients])


class DashboardService:
    def __init__(self, manager: ConnectionManager):
        self.manager = manager

    async def deliver(self, nudge: Nudge) -> None:
        # do not modify the original nudge
        ev = DashboardEvent(
            event_type="nudge",
            timestamp=nudge.timestamp,
            nudge_type=nudge.nudge_type,
            priority=nudge.priority,
            message=nudge.message,
            source_signal_type=nudge.source_signal_type,
            evidence=nudge.evidence,
            sequence_id=nudge.sequence_id,
        )
        await self.manager.broadcast(ev.to_dict())
