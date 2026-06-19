"""AiProvider — Konfiguration eines LLM-Endpoints.

tenant_id=0 bedeutet plattformweiter Default; tenant_id>0 ueberschreibt
fuer den jeweiligen Mandanten. adapter_type ist z.B. "openai" und
entscheidet, welcher Adapter den Provider anspricht.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import AdminBase
from lib.mixins import BaseMixin


class AiProvider(BaseMixin, AdminBase):
    __tablename__ = "ai_provider"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False, default="openai")
    api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    default_model: Mapped[str] = mapped_column(String(128), nullable=False, default="gpt-5.5")
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
