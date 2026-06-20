"""Document — eigenstaendige editierbare Long-Form-Entitaet pro Tenant.

Abgrenzung zu Note: Note ist ein kurzer Annotations-Snippet, der polymorph
an einer anderen Entity (Contact, Deal, Chat, ...) klebt. Document hat
einen eigenen Lebenszyklus, einen Titel, laenglichen Markdown-Inhalt und
einen optionalen polymorphen Anker (target_cls / target_id) — z.B. um
ein Konzept-Dokument einem Projekt oder Deal zuzuordnen.

author_display_name ist denormalisiert wie bei Note: Anzeige bleibt
stabil, auch wenn der User spaeter umbenannt / geloescht wird.

Format ist immer Markdown. Wir koennen spaeter eine semantische
Snippet-/Fassade-Schicht obendrueber legen (Agency-Pattern), ohne das
Schema brechen zu muessen.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.document")
class Document(BaseMixin, TenantBase):
    __tablename__ = "document"

    RESOURCE_SYSTEM_EXPLANATION: str = (
        "Ein Document ist ein eigenstaendiges Markdown-Dokument im Tenant. "
        "Es traegt Titel und laenglichen Markdown-Content, hat einen eigenen "
        "Lebenszyklus und kann optional polymorph an eine andere Entity "
        "(Projekt, Deal, Contact) gehaengt sein."
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="markdown")
    author_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    author_display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def get_resource_type(self) -> str:
        return "document"

    def get_resource_name(self) -> str:
        return (self.title or "").strip() or f"Document #{self.id}"

    def get_resource_short(self) -> str:
        return (self.content or "").strip()[:200]

    def get_resource_markdown(self) -> str:
        return f"# {self.title}\n\n{self.content or ''}"

    def get_resource_url(self) -> str:
        return f"/documents/{self.id}"
