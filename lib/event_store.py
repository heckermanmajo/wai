"""Persistenz für Traces und Events in logging_db.

Alle Funktionen sind sync (SQLAlchemy ohne asyncio). Aufrufer aus
async-Code wickeln sie in asyncio.to_thread, damit der Event-Loop nicht
blockiert. Für Demo-Last reicht das problemlos.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, select

from lib.db import session_for_logging
from lib.entities.logging import Event as EventRow
from lib.entities.logging import Trace as TraceRow
from lib.events import Event


def create_trace(trace_uid: str, tenant_id: str, user_message: str, started_at: datetime) -> None:
    with session_for_logging() as s:
        row = TraceRow(
            trace_uid=trace_uid,
            tenant_id=tenant_id,
            user_message=user_message,
            started_at=started_at,
            status="running",
        )
        s.add(row)
        s.commit()


def persist_event(event: Event) -> None:
    with session_for_logging() as s:
        row = EventRow(
            trace_uid=event.trace_uid,
            sequence=event.sequence,
            timestamp=event.timestamp,
            event_type=event.event_type,
            data=event.data,
        )
        s.add(row)
        s.commit()


def finalize_trace(
    trace_uid: str,
    *,
    response: str,
    intent: str,
    status: str,
    finished_at: datetime,
    duration_ms: int,
    event_count: int,
    tool_call_count: int,
    error_message: str = "",
) -> None:
    with session_for_logging() as s:
        row = s.execute(select(TraceRow).where(TraceRow.trace_uid == trace_uid)).scalar_one_or_none()
        if row is None:
            return
        row.response = response
        row.intent = intent
        row.status = status
        row.finished_at = finished_at
        row.duration_ms = duration_ms
        row.event_count = event_count
        row.tool_call_count = tool_call_count
        row.error_message = error_message
        s.commit()


def list_traces(
    *,
    limit: int = 100,
    offset: int = 0,
    tenant_id: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    stmt = select(TraceRow).order_by(desc(TraceRow.started_at)).limit(limit).offset(offset)
    if tenant_id:
        stmt = stmt.where(TraceRow.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(TraceRow.status == status)
    if since:
        stmt = stmt.where(TraceRow.started_at >= since)
    with session_for_logging() as s:
        rows = s.execute(stmt).scalars().all()
        return [_trace_to_dict(r) for r in rows]


def get_trace_with_events(trace_uid: str) -> dict[str, Any] | None:
    with session_for_logging() as s:
        trace = s.execute(select(TraceRow).where(TraceRow.trace_uid == trace_uid)).scalar_one_or_none()
        if trace is None:
            return None
        events = (
            s.execute(
                select(EventRow)
                .where(EventRow.trace_uid == trace_uid)
                .order_by(EventRow.sequence)
            )
            .scalars()
            .all()
        )
        return {
            "trace": _trace_to_dict(trace),
            "events": [_event_to_dict(e) for e in events],
        }


def _trace_to_dict(r: TraceRow) -> dict[str, Any]:
    return {
        "trace_uid": r.trace_uid,
        "tenant_id": r.tenant_id,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "duration_ms": r.duration_ms,
        "user_message": r.user_message,
        "response": r.response,
        "intent": r.intent,
        "status": r.status,
        "event_count": r.event_count,
        "tool_call_count": r.tool_call_count,
        "error_message": r.error_message,
    }


def _event_to_dict(e: EventRow) -> dict[str, Any]:
    return {
        "sequence": e.sequence,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "event_type": e.event_type,
        "data": e.data,
    }
