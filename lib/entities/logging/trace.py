"""Trace — eine logische Konversations-Runde (1 User-Message → 1 Antwort).

Jeder Trace bündelt die Events einer Chat-Anfrage zu einem auswertbaren Ganzen.
trace_uid ist UUID4 und das Verlinkungs-Token, das auch nach außen geht (URL,
SSE-Stream). Die Integer-id ist nur intern für SQL-Joins/Sort-Stabilität.

Status:
    "running" — Agent läuft noch
    "ok"      — Antwort sauber zurückgegeben
    "error"   — Exception oder MCP-unreachable
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import LoggingBase
from lib.mixins import BaseMixin


class Trace(BaseMixin, LoggingBase):
    __tablename__ = "trace"
    __table_args__ = (UniqueConstraint("trace_uid", name="uq_trace_uid"),)
    # Plan 04: Logging-Tabelle, kein Audit.
    __change_log__ = False

    trace_uid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    intent: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
