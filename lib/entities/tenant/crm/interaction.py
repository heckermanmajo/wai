"""Interaction — Kontakt-Touchpoint (Call, Mail, WhatsApp, Note, Meeting).

direction unterscheidet eingehend/ausgehend/intern (in/out/internal).
transcript_attachment_id verweist optional auf eine Voice-Transcript-Datei
in core.attachment; attachment_ids ist eine CSV nackter Attachment-IDs
fuer beliebige Anhaenge. Zeitstempel liegt in occurred_at (vom
Aufrufer gesetzt), nicht in created_at.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("crm.interaction")
class Interaction(BaseMixin, TenantBase):
    __tablename__ = "crm_interaction"

    contact_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="note")
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="out")
    summary: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    transcript_attachment_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    attachment_ids: Mapped[str] = mapped_column(
        String(512), nullable=False, default=""
    )
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    author_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
