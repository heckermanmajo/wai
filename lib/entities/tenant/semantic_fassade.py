"""SemanticFassade — 1:1-Index-Eintrag pro indizierter Quell-Entity.

entity_class ist der bei @register_entity vergebene Alias der Quell-Entity
(z.B. "core.document"); entity_id verweist auf die Zeile in der jeweiligen
Quell-Tabelle. KEINE FK-Constraint — Konvention dieses Projekts.

content_hash bindet die letzte indizierte Version eindeutig: aendert sich
der Hash, werden die Snippets verworfen und neu generiert.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("semantic.fassade")
class SemanticFassade(BaseMixin, TenantBase):
    __tablename__ = "semantic_fassade"

    entity_class: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    abstract: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
