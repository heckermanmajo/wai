"""UserData — Plattform-Account.

Username ist global eindeutig. platform_role steuert die Rechte
ueber alle Tenants hinweg ("none"/"support"/"admin"); pro Tenant gibt
es zusaetzlich eine TenantMembership mit tenant_role.
"""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import AdminBase
from lib.mixins import BaseMixin


class UserData(BaseMixin, AdminBase):
    __tablename__ = "user_data"
    __table_args__ = (UniqueConstraint("username", name="uq_user_data_username"),)

    username: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    platform_role: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
