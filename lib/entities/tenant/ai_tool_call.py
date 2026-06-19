"""AiToolCall — protokollierter Tool-Aufruf zu einer Assistant-Message.

arguments_json und result_text speichern Rohdaten als String; das Frontend
rendert sie. sub_chat_id verweist optional auf einen Sub-Chat (z.B. ein
Spezialisten-Agent), den dieser Tool-Call ausgeloest hat.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("ai.tool_call")
class AiToolCall(BaseMixin, TenantBase):
    __tablename__ = "ai_tool_call"

    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_call_id: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sub_chat_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
