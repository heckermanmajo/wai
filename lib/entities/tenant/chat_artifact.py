"""ChatArtifact — Link zwischen AiChat und beliebigen Entities ("Mappe").

Jede Zeile bedeutet: "diese Entity gehoert in die Mappe des Chats".
Eine Entity kann in beliebig vielen Mappen liegen (M:N), unabhaengig
vom polymorphen target_cls/target_id, das einige Entities zusaetzlich
tragen.

relation kategorisiert die Herkunft:
    uploaded  — vom User hochgeladen (Voice/Image)
    touched   — Tool-Call hat sie gelesen
    created   — Tool-Call hat sie erzeugt
    cloned    — beim Chat-Klon uebernommen
    linked    — manuell verlinkt (Default)
"""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("ai.chat_artifact")
class ChatArtifact(BaseMixin, TenantBase):
    __tablename__ = "chat_artifact"

    chat_id: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_cls: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relation: Mapped[str] = mapped_column(String(32), nullable=False, default="linked")
