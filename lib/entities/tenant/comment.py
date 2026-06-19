"""Comment — Kommentar, polymorph an beliebige Entity haengbar.

Wie Note: author_display_name ist denormalisiert. Comments unterscheiden
sich von Notes semantisch (Diskussion vs. dokumentierte Beobachtung).
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.comment")
class Comment(BaseMixin, TenantBase):
    __tablename__ = "comment"

    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    author_display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
