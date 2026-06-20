"""Note — freie Notiz, polymorph an beliebige Entity haengbar.

author_display_name ist denormalisiert: Anzeige bleibt stabil, selbst wenn
der User spaeter umbenannt oder geloescht wird.
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.note")
class Note(BaseMixin, TenantBase):
    __tablename__ = "note"

    RESOURCE_SYSTEM_EXPLANATION: str = (
        "Eine Note ist eine kurze freie Annotation, die polymorph an einer "
        "anderen Entity (Contact, Deal, Chat, ...) haengt. Body ist freitext "
        "Markdown."
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    author_display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def get_resource_type(self) -> str:
        return "note"

    def get_resource_name(self) -> str:
        title = (self.title or "").strip()
        if title:
            return title
        body = (self.body or "").strip()
        if body:
            return body.splitlines()[0][:80]
        return f"Note #{self.id}"

    def get_resource_short(self) -> str:
        return (self.body or "").strip()[:200]

    def get_resource_markdown(self) -> str:
        title = (self.title or "").strip()
        body = self.body or ""
        if title:
            return f"# {title}\n\n{body}"
        return body

    def get_resource_url(self) -> str:
        return f"/notes/{self.id}"
