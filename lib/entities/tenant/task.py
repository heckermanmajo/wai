"""Task — Aufgabe, polymorph an beliebige Entity haengbar.

target_cls/target_id verweisen optional auf ein Parent-Objekt (Project,
Deal, Contact, ...). assignee_user_id ist eine nackte UserData.id.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.task")
class Task(BaseMixin, TenantBase):
    __tablename__ = "task"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assignee_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
