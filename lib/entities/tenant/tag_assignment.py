"""TagAssignment — Verknuepfung Tag <-> beliebige Entity.

Reine M:N-Bruecke; bewusst nicht polymorph adressierbar (kein
@register_entity). UNIQUE (tag_id, target_cls, target_id) verhindert
Doppelzuweisungen.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin


class TagAssignment(BaseMixin, TenantBase):
    __tablename__ = "tag_assignment"
    __table_args__ = (
        UniqueConstraint(
            "tag_id", "target_cls", "target_id", name="uq_tag_assignment_tag_target"
        ),
    )

    tag_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
