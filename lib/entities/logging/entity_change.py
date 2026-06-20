"""EntityChange — Audit-Trail-Eintrag pro logischem Save (Plan 04).

Append-only Tabelle in logging_db. Pro `BaseMixin`-Row, die in einem
Session-Flush dirty wird, schreibt der ORM-Hook in ``lib/audit.py`` genau
einen Eintrag — die Feld-Diffs der einzelnen Spalten landen als Liste
in ``field_diffs``.

Schema-Felder:
    tenant_id    — Tenant-Slug, "" bei admin-DB-Entities
    target_cls   — Polymorph-Alias der Klasse (z.B. "core.task") oder
                   die admin/logging-Variante (z.B. "admin.setting")
    target_id    — ID der geaenderten Row
    change_type  — "create" | "update" | "delete" | "soft_delete"
    actor_type   — "human" | "ai" | "system"
    actor_id     — User-ID oder Agent-ID, 0 bei system
    agent_name   — leer bei human/system
    trace_uid    — leer bei Calls ohne Chat-Kontext
    field_diffs  — JSONB-Liste [{field, old, new}] oder mit
                   {"truncated": true, "old_len": .., "new_len": ..}
    summary      — kurzer Satz, deterministisch oder von Agent gesetzt
"""
from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import LoggingBase
from lib.mixins import BaseMixin


class EntityChange(BaseMixin, LoggingBase):
    __tablename__ = "entity_change"
    __table_args__ = (
        Index(
            "ix_entity_change_target",
            "tenant_id", "target_cls", "target_id", "created_at",
        ),
        Index("ix_entity_change_trace_uid", "trace_uid"),
        Index("ix_entity_change_actor_type", "actor_type", "created_at"),
    )
    # Audit-Tabelle selbst opt-out (sonst Hen-Ei: Hook schreibt -> Hook triggert).
    __change_log__ = False

    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    trace_uid: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    field_diffs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
