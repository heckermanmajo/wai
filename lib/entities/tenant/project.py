"""Project — fachliches Projekt eines Mandanten.

Tasks, Notes, Comments, Attachments koennen polymorph auf ein Project
verweisen ueber (target_cls="core.project", target_id=<project.id>).
owner_user_id ist eine nackte Referenz auf UserData.id (keine FK).
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.project")
class Project(BaseMixin, TenantBase):
    __tablename__ = "project"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
