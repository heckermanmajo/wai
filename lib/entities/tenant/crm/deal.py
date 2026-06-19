"""Deal — konkretes Verkaufsvorhaben.

Verknuepft optional Account, Contact und Pipeline/Stage ueber nackte
Integer-IDs. value_cents speichert den Wert in der kleinsten Einheit
(Cent), currency als ISO-4217-Code. status spiegelt Stage-Terminal-Flags
auf Deal-Ebene (open/won/lost) und wird bei deal_advance_stage gesetzt.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("crm.deal")
class Deal(BaseMixin, TenantBase):
    __tablename__ = "crm_deal"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contact_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pipeline_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    value_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    expected_close_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
