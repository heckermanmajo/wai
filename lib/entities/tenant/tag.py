"""Tag — Schlagwort, ueber TagAssignment polymorph an Entities geheftet.

Farbe ist ein HEX-String fuer das UI; Default-Grau wenn nichts gesetzt.
"""
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.tag")
class Tag(BaseMixin, TenantBase):
    __tablename__ = "tag"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#cccccc")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
