"""Fachliches Event am Vorgang — Plan 08.

Kuratierte Bedeutungs-Timeline ("Statuswechsel", "Anruf am 12.6.", "Mail
rausgegangen", "Termin"), klar getrennt vom universellen Change-Log
(Feld-Diffs) und von der Telemetrie-Tabelle ``logging_db.event`` (eine
Zeile pro Chat-Runde, Vision §16).

Polymorpher Anker auf beliebige Entities (Vision §2), primaer an Process
(Plan 07). ``__change_log__ = False`` — Events sind selbst Audit-artig,
Audit-ueber-Audit waere Rauschen (Plan 08 Offene Frage 8).

Class-Name ``BusinessEvent`` wegen Namens-Kollision mit
``lib.entities.logging.event.Event`` (Telemetrie). Tabelle heisst
``event`` wie in VISION §2 festgelegt; Polymorph-Alias ``core.event``.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lib.base import TenantBase
from lib.mixins import BaseMixin
from lib.polymorphic import register_entity


@register_entity("core.event")
class BusinessEvent(BaseMixin, TenantBase):
    __tablename__ = "event"
    # Plan 08 Offene Frage 8: Events sind selbst Audit-artig, kein
    # Change-Log fuer sie. Manuelle Korrektur passiert ueber soft-delete
    # + neues Event, das genuegt als Audit-Spur.
    __change_log__ = False

    RESOURCE_SYSTEM_EXPLANATION: str = (
        "Ein fachliches Event ist ein kuratierter Eintrag in der "
        "Bedeutungs-Timeline einer Entity (Statuswechsel, Anruf, Mail, "
        "Termin). Title + Body sind die primaeren Bedeutungstraeger fuer "
        "den semantischen Index."
    )

    # Zeitpunkt des Geschehens (!= created_at). Bei Auto-Events == created_at,
    # bei manuellen kann der User es rueckdatieren.
    happened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Freitext-String, V1-Konvention dokumentiert in business_events.py.
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Polymorpher Anker — Pflicht (Plan 08 Offene Frage 4).
    target_cls: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Aktor: aus tenant_context. "system" bei reinen Auto-Trigger ohne
    # menschlichen/AI-Bezug; aktuell V1 nicht aktiv genutzt — Auto-Listener
    # uebernimmt actor des verursachenden Change-Log-Eintrags.
    actor_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="system"
    )
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agent_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )

    # Bruecke zu logging_db.trace — leer bei rein-menschlichem Event ohne
    # Chat-Kontext.
    trace_uid: Mapped[str] = mapped_column(
        String(36), nullable=False, default=""
    )

    # "manual" | "auto_change_log" | "auto_workflow" | ... (§20 spaeter
    # "mail_ingest", "calendar"). source_ref ist Idempotenz-Anker fuer den
    # Auto-Erzeuger — z.B. "entity_change:<id>".
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual"
    )
    source_ref: Mapped[str] = mapped_column(
        String(255), nullable=False, default=""
    )

    # Typ-spezifisches Detail-Bag. V1 KEINE Validierung — kuratiert lassen.
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # ------------------------------------------------------------------
    # Resource-Adapter fuer semantic_sync
    # ------------------------------------------------------------------

    def get_resource_type(self) -> str:
        return "event"

    def get_resource_name(self) -> str:
        title = (self.title or "").strip()
        if title:
            return title
        return f"{self.event_type or 'event'} #{self.id}"

    def get_resource_short(self) -> str:
        body = (self.body or "").strip()
        if body:
            return body[:200]
        return f"{self.event_type} @ {self.target_cls}#{self.target_id}"

    def get_resource_markdown(self) -> str:
        head = self.title or self.event_type or f"Event #{self.id}"
        body = (self.body or "").strip()
        body_block = f"\n\n{body}" if body else ""
        anker = f"{self.target_cls}#{self.target_id}"
        meta = f"\n\n_Typ: {self.event_type} · {anker}_"
        return f"# {head}{meta}{body_block}"

    def get_resource_url(self) -> str:
        return f"/events/{self.id}"
