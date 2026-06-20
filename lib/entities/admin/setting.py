"""Setting — generischer Key/Value-Eintrag der Setting-Hierarchie.

Plan 03 — Settings-Hierarchie MVP, Vision-Ref §27.

Diese Tabelle lebt in zwei DBs:
- admin_db: nur scope="platform"-Eintraege (plattformweit, mandantenuebergreifend).
- tenant_db: scope in {"tenant", "entity_type", "entity", "chat"} (siehe
  lib/entities/tenant/setting.py — selbe Struktur, andere Base).

Aufloesungs-Reihenfolge im Resolver (lib/settings.py):
    chat -> entity -> entity_type -> tenant -> platform -> PLATFORM_DEFAULTS

Unique-Constraint (scope, scope_ref, entity_cls, entity_id, key) — ein
Setting pro Schicht-Position. Bei nicht-entity-Scopes ist entity_cls=""
und entity_id=0; Plan 03 sieht das so vor.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import AdminBase
from lib.mixins import BaseMixin


class Setting(BaseMixin, AdminBase):
    __tablename__ = "setting"
    __table_args__ = (
        UniqueConstraint(
            "scope", "scope_ref", "entity_cls", "entity_id", "key",
            name="uq_setting_scope_key",
        ),
    )
    # Plan 04 Opt-Out: Setting hat eigenen Mini-Audit-Pfad in lib/settings.py.
    __change_log__ = False

    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_ref: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    entity_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    set_by: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
