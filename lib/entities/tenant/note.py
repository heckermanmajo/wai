"""Note — freie Notiz, polymorph an beliebige Entity haengbar.

author_display_name ist denormalisiert: Anzeige bleibt stabil, selbst wenn
der User spaeter umbenannt oder geloescht wird.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.note")
class Note(BaseMixin, TenantBase):
    __tablename__ = "note"

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    author_display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
