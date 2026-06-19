"""Lead — Roh-Kontakt vor Qualifizierung.

Bewusst getrennt von Contact: Leads durchlaufen einen eigenen Funnel
(new -> contacted -> qualified -> converted/lost). Bei Konvertierung
wird ein Contact angelegt und converted_contact_id als nackte Bruecke
gesetzt; converted_at markiert den Zeitpunkt.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("crm.lead")
class Lead(BaseMixin, TenantBase):
    __tablename__ = "crm_lead"

    first_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    qualification_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    converted_contact_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
