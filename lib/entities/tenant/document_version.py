"""DocumentVersion — historischer Snapshot eines Document.

Jede echte Aenderung am Document (Titel oder Content veraendert) erzeugt
vor dem Apply einen DocumentVersion-Eintrag mit den ALTEN Werten. So
laesst sich die Historie revisionssicher rekonstruieren und ein Restore
auf eine alte Version anstossen.

author_user_id / author_display_name in der Snapshot-Zeile zeigen auf
den User, der die naechste Version anstoesst (= wer den PUT ausloest);
content_hash ist ein SHA256 ueber title + content (NUL-getrennt) der
ALTEN Werte und dient als billiger Dedupe-Check.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.document_version")
class DocumentVersion(BaseMixin, TenantBase):
    __tablename__ = "document_version"

    document_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="markdown")
    author_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    author_display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
