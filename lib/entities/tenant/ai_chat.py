"""AiChat — Konversation mit einem Agent.

Verschachtelte Chats: parent_chat_id+parent_tool_call_id verweisen auf den
Eltern-Chat bzw. den Tool-Call, der diesen Sub-Chat aufgespannt hat
(z.B. wenn der Manager-Agent einen Spezialisten ueber ein Tool ruft).
depth=0 fuer Top-Level.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("ai.chat")
class AiChat(BaseMixin, TenantBase):
    __tablename__ = "ai_chat"

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, default="manager")
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="gpt-5.5")
    parent_chat_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_tool_call_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
