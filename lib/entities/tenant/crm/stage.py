"""Stage — Schritt innerhalb einer Pipeline.

pipeline_id ist eine nackte Integer-Referenz auf Pipeline.id (kein FK).
ordering definiert die Reihenfolge in der Pipeline; is_won/is_lost
markieren Terminal-Stages (Deal abgeschlossen / verloren).
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("crm.stage")
class Stage(BaseMixin, TenantBase):
    __tablename__ = "crm_stage"

    pipeline_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_probability: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_won: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
