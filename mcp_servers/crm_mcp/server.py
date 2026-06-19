"""CRM-MCP — FastMCP-SSE-Server fuer die CRM-Entitaeten eines Mandanten.

Jedes Tool oeffnet eine eigene Session via session_for_tenant(slug) gegen
tenant_<slug>. Der Slug kommt aus der env WAI_TENANT_SLUG_DEFAULT
(Default "demo"). Die Tools liefern dicts/lists zurueck — datetimes werden
zu ISO-Strings serialisiert, damit der JSON-Transport des MCP-Layers
sauber durchlaeuft.

Bewusst keine Foreign-Key-Checks: alle Verknuepfungen sind nackte
Integer-IDs (Account.id, Contact.id, Pipeline.id, Stage.id, ...). Polymorphe
Notes/Comments/Tasks/Reminders hier verweisen auf CRM-Targets via
(target_cls="crm.contact" o.ae., target_id=<id>).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import or_, select

from lib.db import session_for_tenant
from lib.entities.tenant import (
    Account,
    Comment,
    Contact,
    Deal,
    Interaction,
    Lead,
    Note,
    Pipeline,
    Reminder,
    Stage,
    Task,
)
from lib.logging import get_logger

logger = get_logger(__name__)

mcp = FastMCP("wai-crm", host="0.0.0.0", port=8001)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug() -> str:
    return os.environ.get("WAI_TENANT_SLUG_DEFAULT", "demo")


def _to_dict(obj: Any) -> dict:
    """SQLAlchemy-ORM-Objekt -> plain dict (datetimes als ISO-String)."""
    out: dict = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        out[col.name] = val
    return out


def _parse_dt(raw: str) -> datetime | None:
    """ISO-String -> aware datetime (UTC, falls naiv). Leer -> None."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        logger.warning("ungueltiges datetime-format: %r", raw)
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@mcp.tool()
def contact_search(query: str, limit: int = 20) -> list:
    """LIKE-Suche ueber first_name, last_name und email."""
    term = f"%{(query or '').strip()}%"
    limit = max(1, min(int(limit or 20), 200))
    with session_for_tenant(_slug()) as s:
        rows = s.execute(
            select(Contact)
            .where(Contact.is_deleted.is_(False))
            .where(
                or_(
                    Contact.first_name.ilike(term),
                    Contact.last_name.ilike(term),
                    Contact.email.ilike(term),
                )
            )
            .limit(limit)
        ).scalars().all()
        return [_to_dict(r) for r in rows]


@mcp.tool()
def contact_get(id: int) -> dict:
    """Einzelnen Contact per id holen."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(Contact, int(id))
        if obj is None or obj.is_deleted:
            return {"error": f"contact id={id} nicht gefunden"}
        return _to_dict(obj)


@mcp.tool()
def contact_upsert(
    last_name: str,
    first_name: str = "",
    email: str = "",
    phone: str = "",
    account_id: int = 0,
) -> dict:
    """Anlegen oder Update per email (falls vorhanden) bzw. last_name+first_name."""
    with session_for_tenant(_slug()) as s:
        obj: Contact | None = None
        if email:
            obj = s.execute(
                select(Contact)
                .where(Contact.email == email)
                .where(Contact.is_deleted.is_(False))
                .limit(1)
            ).scalar_one_or_none()
        if obj is None and last_name:
            obj = s.execute(
                select(Contact)
                .where(Contact.last_name == last_name)
                .where(Contact.first_name == (first_name or ""))
                .where(Contact.is_deleted.is_(False))
                .limit(1)
            ).scalar_one_or_none()
        if obj is None:
            obj = Contact(
                first_name=first_name or "",
                last_name=last_name,
                email=email or "",
                phone=phone or "",
                account_id=int(account_id or 0),
            )
            s.add(obj)
        else:
            if first_name:
                obj.first_name = first_name
            if email:
                obj.email = email
            if phone:
                obj.phone = phone
            if account_id:
                obj.account_id = int(account_id)
        s.commit()
        s.refresh(obj)
        logger.info("contact_upsert id=%s last_name=%s", obj.id, obj.last_name)
        return _to_dict(obj)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


@mcp.tool()
def account_get(id: int) -> dict:
    """Account per id."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(Account, int(id))
        if obj is None or obj.is_deleted:
            return {"error": f"account id={id} nicht gefunden"}
        return _to_dict(obj)


@mcp.tool()
def account_upsert(
    name: str, industry: str = "", email: str = "", phone: str = ""
) -> dict:
    """Anlegen oder Update per name."""
    with session_for_tenant(_slug()) as s:
        obj = s.execute(
            select(Account)
            .where(Account.name == name)
            .where(Account.is_deleted.is_(False))
            .limit(1)
        ).scalar_one_or_none()
        if obj is None:
            obj = Account(
                name=name,
                industry=industry or "",
                email=email or "",
                phone=phone or "",
            )
            s.add(obj)
        else:
            if industry:
                obj.industry = industry
            if email:
                obj.email = email
            if phone:
                obj.phone = phone
        s.commit()
        s.refresh(obj)
        logger.info("account_upsert id=%s name=%s", obj.id, obj.name)
        return _to_dict(obj)


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------


@mcp.tool()
def lead_create(
    last_name: str,
    first_name: str = "",
    email: str = "",
    phone: str = "",
    company_name: str = "",
    source: str = "",
    notes: str = "",
) -> dict:
    """Neuen Lead anlegen (status='new')."""
    with session_for_tenant(_slug()) as s:
        obj = Lead(
            first_name=first_name or "",
            last_name=last_name,
            email=email or "",
            phone=phone or "",
            company_name=company_name or "",
            source=source or "",
            notes=notes or "",
            status="new",
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        logger.info("lead_create id=%s last_name=%s", obj.id, obj.last_name)
        return _to_dict(obj)


@mcp.tool()
def lead_get(id: int) -> dict:
    """Einzelnen Lead per id holen."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(Lead, int(id))
        if obj is None or obj.is_deleted:
            return {"error": f"lead id={id} nicht gefunden"}
        return _to_dict(obj)


@mcp.tool()
def lead_convert(lead_id: int) -> dict:
    """Konvertiert Lead in Contact; setzt converted_contact_id, converted_at, status."""
    with session_for_tenant(_slug()) as s:
        lead = s.get(Lead, int(lead_id))
        if lead is None or lead.is_deleted:
            return {"error": f"lead id={lead_id} nicht gefunden"}
        if lead.converted_contact_id:
            return {"contact_id": lead.converted_contact_id, "already_converted": True}
        contact = Contact(
            first_name=lead.first_name or "",
            last_name=lead.last_name,
            email=lead.email or "",
            phone=lead.phone or "",
            notes=lead.notes or "",
            owner_user_id=lead.owner_user_id or 0,
        )
        s.add(contact)
        s.flush()
        lead.converted_contact_id = contact.id
        lead.converted_at = datetime.now(timezone.utc)
        lead.status = "converted"
        s.commit()
        s.refresh(contact)
        logger.info(
            "lead_convert lead_id=%s -> contact_id=%s", lead.id, contact.id
        )
        return {"contact_id": contact.id, "contact": _to_dict(contact)}


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------


@mcp.tool()
def deal_create(
    title: str,
    account_id: int = 0,
    contact_id: int = 0,
    value_cents: int = 0,
    stage_id: int = 0,
) -> dict:
    """Neuen Deal anlegen. pipeline_id wird aus stage_id abgeleitet, falls moeglich."""
    with session_for_tenant(_slug()) as s:
        pipeline_id = 0
        if stage_id:
            stage = s.get(Stage, int(stage_id))
            if stage is not None and not stage.is_deleted:
                pipeline_id = stage.pipeline_id
        obj = Deal(
            title=title,
            account_id=int(account_id or 0),
            contact_id=int(contact_id or 0),
            value_cents=int(value_cents or 0),
            stage_id=int(stage_id or 0),
            pipeline_id=pipeline_id,
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        logger.info("deal_create id=%s title=%s", obj.id, obj.title)
        return _to_dict(obj)


@mcp.tool()
def deal_get(id: int) -> dict:
    """Einzelnen Deal per id holen."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(Deal, int(id))
        if obj is None or obj.is_deleted:
            return {"error": f"deal id={id} nicht gefunden"}
        return _to_dict(obj)


@mcp.tool()
def deal_advance_stage(deal_id: int, stage_id: int) -> dict:
    """Setzt Deal auf neue Stage; spiegelt is_won/is_lost auf deal.status."""
    with session_for_tenant(_slug()) as s:
        deal = s.get(Deal, int(deal_id))
        if deal is None or deal.is_deleted:
            return {"error": f"deal id={deal_id} nicht gefunden"}
        stage = s.get(Stage, int(stage_id))
        if stage is None or stage.is_deleted:
            return {"error": f"stage id={stage_id} nicht gefunden"}
        deal.stage_id = stage.id
        deal.pipeline_id = stage.pipeline_id
        if stage.is_won:
            deal.status = "won"
            deal.closed_at = datetime.now(timezone.utc)
        elif stage.is_lost:
            deal.status = "lost"
            deal.closed_at = datetime.now(timezone.utc)
        else:
            deal.status = "open"
            deal.closed_at = None
        s.commit()
        s.refresh(deal)
        logger.info(
            "deal_advance_stage deal_id=%s -> stage_id=%s status=%s",
            deal.id,
            stage.id,
            deal.status,
        )
        return _to_dict(deal)


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------


@mcp.tool()
def interaction_log(
    channel: str,
    direction: str,
    summary: str,
    contact_id: int = 0,
    account_id: int = 0,
    body: str = "",
    attachment_ids: str = "",
) -> dict:
    """Touchpoint dokumentieren (Call/Mail/WhatsApp/Note/Meeting)."""
    with session_for_tenant(_slug()) as s:
        obj = Interaction(
            channel=channel or "note",
            direction=direction or "out",
            summary=summary or "",
            body=body or "",
            contact_id=int(contact_id or 0),
            account_id=int(account_id or 0),
            attachment_ids=attachment_ids or "",
            occurred_at=datetime.now(timezone.utc),
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        logger.info(
            "interaction_log id=%s channel=%s contact_id=%s",
            obj.id,
            obj.channel,
            obj.contact_id,
        )
        return _to_dict(obj)


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------


@mcp.tool()
def pipeline_list() -> list:
    """Alle Pipelines mit ihren Stages (sortiert nach Stage.ordering)."""
    with session_for_tenant(_slug()) as s:
        pipelines = s.execute(
            select(Pipeline).where(Pipeline.is_deleted.is_(False))
        ).scalars().all()
        result: list[dict] = []
        for p in pipelines:
            stages = s.execute(
                select(Stage)
                .where(Stage.pipeline_id == p.id)
                .where(Stage.is_deleted.is_(False))
                .order_by(Stage.ordering.asc(), Stage.id.asc())
            ).scalars().all()
            result.append(
                {
                    "pipeline": _to_dict(p),
                    "stages": [_to_dict(st) for st in stages],
                }
            )
        return result


# ---------------------------------------------------------------------------
# Querverweise (polymorph): Task / Note / Comment / Reminder
# ---------------------------------------------------------------------------


@mcp.tool()
def task_create(
    title: str,
    target_cls: str = "",
    target_id: int = 0,
    due_at: str = "",
    assignee_user_id: int = 0,
) -> dict:
    """Aufgabe anlegen, optional an beliebiges Target gehaengt."""
    with session_for_tenant(_slug()) as s:
        obj = Task(
            title=title,
            target_cls=target_cls or "",
            target_id=int(target_id or 0),
            due_at=_parse_dt(due_at),
            assignee_user_id=int(assignee_user_id or 0),
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        logger.info("task_create id=%s title=%s", obj.id, obj.title)
        return _to_dict(obj)


@mcp.tool()
def note_add(target_cls: str, target_id: int, title: str, body: str) -> dict:
    """Notiz an ein Target (z.B. crm.contact/crm.deal) haengen."""
    with session_for_tenant(_slug()) as s:
        obj = Note(
            title=title or "",
            body=body or "",
            target_cls=target_cls or "",
            target_id=int(target_id or 0),
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        logger.info(
            "note_add id=%s target=%s/%s", obj.id, obj.target_cls, obj.target_id
        )
        return _to_dict(obj)


@mcp.tool()
def comment_add(
    target_cls: str, target_id: int, body: str, author_display_name: str = ""
) -> dict:
    """Kommentar an ein Target haengen (author_display_name denormalisiert)."""
    with session_for_tenant(_slug()) as s:
        obj = Comment(
            body=body or "",
            target_cls=target_cls or "",
            target_id=int(target_id or 0),
            author_display_name=author_display_name or "",
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        logger.info(
            "comment_add id=%s target=%s/%s", obj.id, obj.target_cls, obj.target_id
        )
        return _to_dict(obj)


@mcp.tool()
def reminder_create(
    title: str,
    due_at: str,
    target_cls: str = "",
    target_id: int = 0,
    recipient_user_id: int = 0,
) -> dict:
    """Erinnerung anlegen (due_at als ISO-String Pflicht)."""
    dt = _parse_dt(due_at)
    if dt is None:
        return {"error": f"due_at fehlt oder ungueltig: {due_at!r}"}
    with session_for_tenant(_slug()) as s:
        obj = Reminder(
            title=title,
            due_at=dt,
            target_cls=target_cls or "",
            target_id=int(target_id or 0),
            recipient_user_id=int(recipient_user_id or 0),
        )
        s.add(obj)
        s.commit()
        s.refresh(obj)
        logger.info("reminder_create id=%s title=%s due_at=%s", obj.id, obj.title, dt)
        return _to_dict(obj)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    logger.info(
        "Starte wai-crm-mcp auf Port %s via SSE (tenant=%s)", port, _slug()
    )
    mcp.run(transport="sse")
