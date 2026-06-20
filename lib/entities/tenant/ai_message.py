"""AiMessage — eine Nachricht in einem AiChat.

role: "system" | "user" | "assistant" | "tool". Bei role="tool" werden
tool_call_id und tool_name gefuellt; sonst leer.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("ai.message")
class AiMessage(BaseMixin, TenantBase):
    __tablename__ = "ai_message"
    # Plan 04: Telemetrie, kein Audit-Wert.
    __change_log__ = False

    chat_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_call_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
