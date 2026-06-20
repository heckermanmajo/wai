"""Setting — generischer Key/Value-Eintrag der Setting-Hierarchie (Tenant-Seite).

Plan 03 — Settings-Hierarchie MVP, Vision-Ref §27.

Selbe Struktur wie lib/entities/admin/setting.py, aber an TenantBase gebunden.
Hier landen scope in {"tenant", "entity_type", "entity", "chat"}. Plattform-
Settings leben separat in admin_db.

Polymorpher Alias "core.setting", damit der Mini-Audit-Pfad in lib/settings.py
einen sauberen target_cls schreiben kann.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.setting")
class Setting(BaseMixin, TenantBase):
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
