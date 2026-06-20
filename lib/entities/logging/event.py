"""Event — eine atomare Beobachtung innerhalb eines Trace.

Append-only. Reihenfolge innerhalb eines Trace ist über (trace_uid, sequence)
deterministisch — sequence ist ein in-memory-Counter im EventEmitter,
nicht aus der DB.

event_type-Vokabular (siehe lib/events.py):
    trace_started, intent_classified, mcp_connected,
    llm_request, llm_response,
    tool_call_started, tool_call_result,
    error, trace_completed

data ist JSONB — pro Event-Typ unterschiedlich strukturiert, bewusst nicht
in eigene Spalten normalisiert (zu volatil in dieser Phase).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import LoggingBase
from lib.mixins import BaseMixin


class Event(BaseMixin, LoggingBase):
    __tablename__ = "event"
    __table_args__ = (
        UniqueConstraint("trace_uid", "sequence", name="uq_event_trace_seq"),
        Index("ix_event_trace_seq", "trace_uid", "sequence"),
    )
    # Plan 04: Logging-Tabelle selbst nicht auditierbar (sonst Hen-Ei).
    __change_log__ = False

    trace_uid: Mapped[str] = mapped_column(String(36), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
