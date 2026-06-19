"""Tenant — ein Mandant der Plattform.

Jede Tenant-Row korrespondiert mit einer physischen DB tenant_<slug>.
Der Slug ist ASCII [a-z0-9_]+ und UNIQUE; siehe lib.slugify.

Branding-Felder (brand_color, logo_path, favicon_path) werden vom Gateway
fuer das Chat-UI verwendet. logo_path/favicon_path sind MinIO-Keys.
"""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import AdminBase
from lib.mixins import BaseMixin


class Tenant(BaseMixin, AdminBase):
    __tablename__ = "tenant"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenant_slug"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    brand_color: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    logo_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    favicon_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
