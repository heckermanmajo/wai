"""Account — Unternehmen/Organisation im CRM.

Contacts und Deals verweisen ueber nackte account_id (kein FK). owner_user_id
ist ebenfalls eine nackte Referenz auf UserData.id.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("crm.account")
class Account(BaseMixin, TenantBase):
    __tablename__ = "crm_account"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    website: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
