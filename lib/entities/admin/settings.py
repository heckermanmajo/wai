"""TenantSettingsEntry — Key/Value-Settings pro Tenant.

Composite-Unique auf (tenant_id, key). Werte sind generische Strings; bei
Bedarf serialisiert der Caller JSON in 'value'.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import AdminBase
from lib.mixins import BaseMixin


class TenantSettingsEntry(BaseMixin, AdminBase):
    __tablename__ = "tenant_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_tenant_settings_tenant_key"),
    )

    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
