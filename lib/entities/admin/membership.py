"""TenantMembership — Zuordnung User <-> Tenant.

user_id und tenant_id sind nackte Integer-Referenzen (keine FK-Constraints,
siehe lib/mixins.py). tenant_role: "member" oder "admin" (im jeweiligen
Tenant).
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import AdminBase
from lib.mixins import BaseMixin


class TenantMembership(BaseMixin, AdminBase):
    __tablename__ = "tenant_membership"

    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
