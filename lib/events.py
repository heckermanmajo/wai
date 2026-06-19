"""EventEmitter — strukturierte Telemetrie für eine Chat-Runde.

Der Agent emittiert während der Ausführung Events in eine asyncio.Queue.
Der SSE-Handler im Gateway liest aus dieser Queue, streamt jedes Event
sofort an den Client UND persistiert es in logging_db.

Schema eines Events:
    trace_uid    UUID4-String, identifiziert die Runde
    sequence     monoton wachsend pro Trace (in-memory Counter)
    timestamp    UTC, gesetzt im Moment des emit()
    event_type   eines aus EVENT_TYPES
    data         dict, event-typ-spezifisch (siehe EVENT_TYPES)

Verwendung:
    emitter = EventEmitter(trace_uid, tenant_id, user_message)
    emitter.emit("intent_classified", intent="lead_management", duration_ms=120)
    ...
    async for ev in emitter.stream():
        send_to_client(ev)
    emitter.close()  # beendet die stream-Schleife sauber
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator


EVENT_TYPES = {
    "trace_started",       # {tenant_id, user_message, history_len}
    "intent_classified",   # {intent, model, duration_ms}
    "mcp_connected",       # {url, tool_names: [str]}
    "llm_request",         # {model, messages_count, has_tools, round}
    "llm_response",        # {model, duration_ms, has_tool_calls, content_preview}
    "tool_call_started",   # {tool_name, call_id, args}
    "tool_call_result",    # {tool_name, call_id, duration_ms, result_preview, is_error}
    "error",               # {error_type, message}
    "trace_completed",     # {response, total_duration_ms, status}
}


def new_trace_uid() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Event:
    trace_uid: str
    sequence: int
    timestamp: datetime
    event_type: str
    data: dict = field(default_factory=dict)

    def to_jsonable(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class EventEmitter:
    """Pro Chat-Runde eine Instanz. Async-safe (single producer, single consumer)."""

    def __init__(self, trace_uid: str, tenant_id: str, user_message: str) -> None:
        self.trace_uid = trace_uid
        self.tenant_id = tenant_id
        self.user_message = user_message
        self._seq = 0
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self._closed = False

    def emit(self, event_type: str, **data) -> Event:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unbekannter event_type: {event_type!r}")
        if self._closed:
            raise RuntimeError("Emitter ist bereits geschlossen")
        self._seq += 1
        ev = Event(
            trace_uid=self.trace_uid,
            sequence=self._seq,
            timestamp=now_utc(),
            event_type=event_type,
            data=data,
        )
        self._queue.put_nowait(ev)
        return ev

    async def stream(self) -> AsyncIterator[Event]:
        while True:
            ev = await self._queue.get()
            if ev is None:
                return
            yield ev

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put_nowait(None)

    @property
    def event_count(self) -> int:
        return self._seq
