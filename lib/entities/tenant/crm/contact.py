"""Contact — Ansprechpartner im CRM.

account_id ist eine nackte Integer-Referenz auf Account.id (kein FK).
channels ist eine CSV-Liste der bevorzugten Kontaktwege
("whatsapp,mail,phone"). lifecycle_stage beschreibt den Status im
Kunden-Lifecycle (z.B. "active", "lost", "vip").
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("crm.contact")
class Contact(BaseMixin, TenantBase):
    __tablename__ = "crm_contact"

    first_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role_title: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    channels: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifecycle_stage: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active"
    )
