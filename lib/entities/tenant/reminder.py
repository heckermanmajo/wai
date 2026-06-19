"""Reminder — geplante Erinnerung, vom Cron-Worker getriggert.

due_at ist Pflicht (wann soll erinnert werden); triggered_at wird vom
Worker beim Feuern gesetzt. status durchlaeuft pending -> triggered oder
pending -> dismissed.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.reminder")
class Reminder(BaseMixin, TenantBase):
    __tablename__ = "reminder"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    recipient_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
