"""Pipeline — Sales-Funnel-Definition.

Eine Pipeline gruppiert Stages in einer geordneten Reihenfolge. Mit
is_default markiert der Mandant die Standard-Pipeline, in die neue Deals
fallen, wenn keine andere angegeben wurde.
"""
from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("crm.pipeline")
class Pipeline(BaseMixin, TenantBase):
    __tablename__ = "crm_pipeline"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
