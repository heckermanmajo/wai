"""Process — anlassgetriebene Arbeitseinheit eines Mandanten.

Plan 07. Semantisch klar getrennt von Project: kleiner, kurzlebiger,
oft kundengetrieben ("Reklamation 4711", "TUEV-Abnahme Produkt Y").
Optional unter ein Projekt einhaengbar (project_id), optional an einen
Kunden polymorph (customer_cls + customer_id, default leer = freistehend),
optional unter einen Eltern-Vorgang (parent_id).

Polymorphes Anhaengen von Notes/Comments/Tasks/AiChat/... an einen Process
funktioniert ueber deren target_cls="core.process" + target_id=<process.id>.

Anker (customer_cls, customer_id) folgt der Konvention aus lib.polymorphic:
beide leer (="", 0) heisst "kein Kunde", sobald einer gesetzt ist muessen
beide konsistent und der Alias registriert sein. Heute typischerweise
"crm.account"; spaeter auch z.B. "crm.contact" oder "crm.lead" moeglich.

# explorer_scope: "fachlich" — sobald der Marker-Mechanismus existiert
# (eigener Mini-Plan, siehe Plan 07 Offene Frage 7).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.process")
class Process(BaseMixin, TenantBase):
    __tablename__ = "process"

    RESOURCE_SYSTEM_EXPLANATION: str = (
        "Ein Process ist eine kurzlebige, anlassgetriebene Arbeitseinheit "
        "(Kundenmeldung, Reklamation, Abnahme, ...). Beschreibung ist Markdown "
        "und der primaere Bedeutungstraeger fuer den semantischen Index."
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Status ist Freitext; Validator gegen settings.process.status.allowed_values
    # sitzt im process_mcp (set_status / update_process). Workflow-Engine §7
    # erweitert das spaeter um echte Lifecycle-Regeln.
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="neu")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")

    # Typ-Tag, Vorbereitung fuer Workflow-Bindung §7 — in V1 nur Freitext.
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assignee_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Polymorpher Kunden-Anker, default leer. validate_target() laesst (="",0) zu.
    customer_cls: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ------------------------------------------------------------------
    # Resource-Adapter fuer semantic_sync (Fassade + Snippets)
    # ------------------------------------------------------------------

    def get_resource_type(self) -> str:
        return "process"

    def get_resource_name(self) -> str:
        name = (self.name or "").strip()
        return name or f"Process #{self.id}"

    def get_resource_short(self) -> str:
        desc = (self.description or "").strip()
        if desc:
            return desc[:200]
        return f"{self.kind or 'vorgang'} · status={self.status}"

    def get_resource_markdown(self) -> str:
        head = self.name or f"Process #{self.id}"
        kind = (self.kind or "").strip()
        kind_line = f"\n\n_Typ: {kind}_" if kind else ""
        status_line = f"\n\n_Status: {self.status}_"
        body = (self.description or "").strip()
        body_block = f"\n\n{body}" if body else ""
        return f"# {head}{kind_line}{status_line}{body_block}"

    def get_resource_url(self) -> str:
        return f"/processes/{self.id}"
