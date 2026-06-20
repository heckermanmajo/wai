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

import difflib
import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import or_, select

from lib.db import session_for_tenant
from lib.entities.tenant import (
    Account,
    ChatArtifact,
    Comment,
    Contact,
    Deal,
    Document,
    DocumentVersion,
    Interaction,
    Lead,
    Note,
    Pipeline,
    Reminder,
    SemanticFassade,
    SemanticSnippet,
    Stage,
    Task,
)
from lib.polymorphic import resolve_target_cls
from lib.semantic_sync import sync_fassade
from lib.logging import get_logger

logger = get_logger(__name__)

mcp = FastMCP("wai-crm", host="0.0.0.0", port=8001)

MCP_VERSION = "0.1.0"


@mcp.tool()
def manifest() -> dict:
    """Plan 05 — Self-Description (Vision §21). kind klassifiziert den MCP."""
    tool_names = [
        "contact_list", "contact_get", "contact_create", "contact_update",
        "account_list", "account_get", "account_create", "account_update",
        "lead_list", "lead_get", "lead_create", "lead_update",
        "deal_list", "deal_get", "deal_create", "deal_update",
        "interaction_log", "pipeline_list",
        "task_create", "note_add", "comment_add", "reminder_create",
        "semantic_search",
    ]
    return {
        "name": "wai-crm",
        "version": MCP_VERSION,
        "kind": "tool",
        "description": "CRM-Operationen fuer Accounts, Contacts, Leads, Deals, Pipelines.",
        "tools": [{"name": n, "kind": "function"} for n in tool_names],
    }


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
# Documents
# ---------------------------------------------------------------------------


@mcp.tool()
def document_list(
    target_cls: str = "",
    target_id: int = 0,
    query: str = "",
    limit: int = 50,
) -> list:
    """Dokumente im Tenant auflisten.

    Optional filter: target_cls/target_id (polymorpher Anker), query
    (LIKE auf Titel). Default sortiert nach updated_at DESC.
    """
    limit = max(1, min(int(limit or 50), 500))
    with session_for_tenant(_slug()) as s:
        stmt = (
            select(Document)
            .where(Document.is_deleted.is_(False))
            .order_by(Document.updated_at.desc())
            .limit(limit)
        )
        if target_cls:
            stmt = stmt.where(Document.target_cls == target_cls)
        if target_id:
            stmt = stmt.where(Document.target_id == int(target_id))
        if query:
            stmt = stmt.where(Document.title.ilike(f"%{query.strip()}%"))
        rows = s.execute(stmt).scalars().all()
        return [
            {
                "id": d.id,
                "title": d.title,
                "version": d.version,
                "author_display_name": d.author_display_name,
                "target_cls": d.target_cls,
                "target_id": d.target_id,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in rows
        ]


@mcp.tool()
def document_get(id: int) -> dict:
    """Ein Dokument inklusive vollem Markdown-Inhalt holen."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(Document, int(id))
        if obj is None or obj.is_deleted:
            return {"error": f"Dokument {id} nicht gefunden"}
        return _to_dict(obj)


@mcp.tool()
def document_create(
    title: str,
    content: str = "",
    target_cls: str = "",
    target_id: int = 0,
    author_display_name: str = "",
    chat_id: int = 0,
) -> dict:
    """Neues Dokument anlegen.

    title ist Pflicht. content ist Markdown. target_cls/target_id
    optional fuer polymorphen Anker (z.B. "crm.deal" + Deal-ID).
    chat_id > 0 verlinkt das neue Dokument als ChatArtifact (relation=created)
    in der Mappe des aktuellen Chats.
    """
    title = (title or "").strip()
    if not title:
        return {"error": "title darf nicht leer sein"}
    with session_for_tenant(_slug()) as s:
        obj = Document(
            title=title,
            content=content or "",
            target_cls=(target_cls or "").strip(),
            target_id=int(target_id or 0),
            author_display_name=author_display_name or "",
            version=1,
        )
        s.add(obj)
        s.flush()
        if chat_id and int(chat_id) > 0:
            s.add(ChatArtifact(
                chat_id=int(chat_id),
                artifact_cls="core.document",
                artifact_id=obj.id,
                relation="created",
            ))
        s.commit()
        s.refresh(obj)
        logger.info(
            "document_create id=%s title=%r chat_id=%s",
            obj.id, obj.title, chat_id,
        )
        return _to_dict(obj)


@mcp.tool()
def document_edit(
    id: int,
    title: str = "",
    content: str = "",
    target_cls: str = "",
    target_id: int = 0,
    chat_id: int = 0,
) -> dict:
    """Dokument editieren. Leere Felder bleiben unveraendert.

    Achtung: Um content explizit zu leeren, einen einzelnen Whitespace
    senden (Konvention dieses Tools — leere Strings = "nicht aendern").
    chat_id > 0 verlinkt das beruehrte Dokument als ChatArtifact
    (relation=touched), falls noch nicht vorhanden.
    """
    with session_for_tenant(_slug()) as s:
        obj = s.get(Document, int(id))
        if obj is None or obj.is_deleted:
            return {"error": f"Dokument {id} nicht gefunden"}
        changed = False
        if title:
            obj.title = title.strip()
            changed = True
        if content:
            obj.content = content
            changed = True
        if target_cls:
            obj.target_cls = target_cls.strip()
            changed = True
        if target_id:
            obj.target_id = int(target_id)
            changed = True
        if changed:
            obj.version += 1
        if chat_id and int(chat_id) > 0:
            existing = s.execute(
                select(ChatArtifact).where(
                    ChatArtifact.chat_id == int(chat_id),
                    ChatArtifact.artifact_cls == "core.document",
                    ChatArtifact.artifact_id == obj.id,
                    ChatArtifact.is_deleted.is_(False),
                )
            ).scalar_one_or_none()
            if existing is None:
                s.add(ChatArtifact(
                    chat_id=int(chat_id),
                    artifact_cls="core.document",
                    artifact_id=obj.id,
                    relation="touched",
                ))
        s.commit()
        s.refresh(obj)
        logger.info(
            "document_edit id=%s changed=%s version=%s chat_id=%s",
            obj.id, changed, obj.version, chat_id,
        )
        return _to_dict(obj)


@mcp.tool()
def document_delete(id: int) -> dict:
    """Dokument soft-loeschen (is_deleted = true)."""
    with session_for_tenant(_slug()) as s:
        obj = s.get(Document, int(id))
        if obj is None or obj.is_deleted:
            return {"error": f"Dokument {id} nicht gefunden"}
        obj.is_deleted = True
        s.commit()
        logger.info("document_delete id=%s", obj.id)
        return {"id": obj.id, "is_deleted": True}


# ---------------------------------------------------------------------------
# Semantic-Layer
# ---------------------------------------------------------------------------


def _semantic_search_like(
    query: str, resource_type: str, limit: int
) -> list:
    """Fallback-Suche per SQL ILIKE — genutzt, wenn Embeddings nicht verfuegbar."""
    term = f"%{(query or '').strip()}%"
    with session_for_tenant(_slug()) as s:
        stmt = (
            select(SemanticSnippet, SemanticFassade)
            .join(
                SemanticFassade,
                SemanticFassade.id == SemanticSnippet.fassade_id,
            )
            .where(SemanticSnippet.is_deleted.is_(False))
            .where(SemanticFassade.is_deleted.is_(False))
            .where(SemanticSnippet.text.ilike(term))
            .order_by(SemanticFassade.updated_at.desc(), SemanticSnippet.idx.asc())
            .limit(limit)
        )
        if resource_type:
            stmt = stmt.where(SemanticFassade.resource_type == resource_type)
        rows = s.execute(stmt).all()
        return [
            {
                "snippet_id": snip.id,
                "fassade_id": fas.id,
                "distance": None,
                "resource_type": fas.resource_type,
                "entity_class": fas.entity_class,
                "entity_id": fas.entity_id,
                "name": fas.name,
                "url": fas.url,
                "snippet_text": snip.text,
                "snippet_idx": snip.idx,
            }
            for snip, fas in rows
        ]


@mcp.tool()
def semantic_search(
    query: str, resource_type: str = "", limit: int = 20
) -> list:
    """Semantische Suche per Cosine-Distance auf pgvector-Embeddings.

    Berechnet das Query-Embedding via OpenAI und ranked Snippets nach
    Cosine-Distance (kleiner = aehnlicher). Liefert pro Treffer Fassade-
    Metadaten (Name, URL, Resource-Typ), Snippet-Text und die Distanz.

    Fallback: bei Embedding-Fehler (kein API-Key, Network) faellt das Tool
    auf LIKE-Suche zurueck.
    """
    limit = max(1, min(int(limit or 20), 200))
    q = (query or "").strip()
    if not q:
        return []
    try:
        from lib.embeddings import embed_texts
        query_vec = embed_texts([q])[0]
    except Exception:
        logger.warning(
            "semantic_search: embedding fehlgeschlagen, fallback LIKE-Suche",
            exc_info=True,
        )
        return _semantic_search_like(q, resource_type, limit)

    with session_for_tenant(_slug()) as s:
        distance = SemanticSnippet.embedding.cosine_distance(query_vec).label(
            "distance"
        )
        stmt = (
            select(
                SemanticSnippet.id,
                SemanticSnippet.fassade_id,
                SemanticSnippet.idx,
                SemanticSnippet.text,
                SemanticFassade.entity_class,
                SemanticFassade.entity_id,
                SemanticFassade.resource_type,
                SemanticFassade.name,
                SemanticFassade.url,
                distance,
            )
            .join(
                SemanticFassade,
                SemanticFassade.id == SemanticSnippet.fassade_id,
            )
            .where(SemanticSnippet.is_deleted.is_(False))
            .where(SemanticFassade.is_deleted.is_(False))
            .where(SemanticSnippet.embedding.is_not(None))
            .order_by("distance")
            .limit(limit)
        )
        if resource_type:
            stmt = stmt.where(SemanticFassade.resource_type == resource_type)
        rows = s.execute(stmt).all()
        return [
            {
                "snippet_id": row.id,
                "fassade_id": row.fassade_id,
                "distance": float(row.distance) if row.distance is not None else None,
                "resource_type": row.resource_type,
                "entity_class": row.entity_class,
                "entity_id": row.entity_id,
                "name": row.name,
                "url": row.url,
                "snippet_text": row.text,
                "snippet_idx": row.idx,
            }
            for row in rows
        ]


@mcp.tool()
def semantic_list_resources(resource_type: str = "", limit: int = 50) -> list:
    """Liste aller Fassaden, optional gefiltert nach resource_type."""
    limit = max(1, min(int(limit or 50), 500))
    with session_for_tenant(_slug()) as s:
        stmt = (
            select(SemanticFassade)
            .where(SemanticFassade.is_deleted.is_(False))
            .order_by(SemanticFassade.updated_at.desc())
            .limit(limit)
        )
        if resource_type:
            stmt = stmt.where(SemanticFassade.resource_type == resource_type)
        rows = s.execute(stmt).scalars().all()
        return [
            {
                "fassade_id": f.id,
                "resource_type": f.resource_type,
                "name": f.name,
                "abstract": f.abstract,
                "url": f.url,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            }
            for f in rows
        ]


@mcp.tool()
def semantic_rebuild(entity_class: str, entity_id: int) -> dict:
    """Fassade + Snippets fuer eine konkrete Resource neu aufbauen.

    entity_class ist der Polymorph-Alias (z.B. "core.document"). Liefert
    die aktualisierte Fassade als dict.
    """
    cls = resolve_target_cls(entity_class)
    if cls is None:
        return {"error": f"unbekannter entity_class-Alias: {entity_class!r}"}
    with session_for_tenant(_slug()) as s:
        resource = s.get(cls, int(entity_id))
        if resource is None or getattr(resource, "is_deleted", False):
            return {
                "error": (
                    f"{entity_class}#{entity_id} nicht gefunden "
                    "oder soft-geloescht"
                )
            }
        fassade = sync_fassade(s, resource, entity_class)
        s.commit()
        s.refresh(fassade)
        logger.info(
            "semantic_rebuild %s/%s -> fassade_id=%s",
            entity_class, entity_id, fassade.id,
        )
        return _to_dict(fassade)


@mcp.tool()
def semantic_embed_missing(limit: int = 200) -> dict:
    """Backfill: Embeddings fuer alle Snippets ohne Vektor nachziehen.

    Sucht Snippets mit ``embedding IS NULL`` und ``is_deleted = false``,
    berechnet Embeddings in Batches von max. 100 und persistiert. Praktisch
    fuer Initial-Backfill direkt nach der pgvector-Migration.
    """
    limit = max(1, min(int(limit or 200), 1000))
    from lib.embeddings import embed_texts
    processed = 0
    with session_for_tenant(_slug()) as s:
        pending = s.execute(
            select(SemanticSnippet)
            .where(SemanticSnippet.is_deleted.is_(False))
            .where(SemanticSnippet.embedding.is_(None))
            .order_by(SemanticSnippet.id.asc())
            .limit(limit)
        ).scalars().all()
        for start in range(0, len(pending), 100):
            batch = pending[start : start + 100]
            vectors = embed_texts([snip.text for snip in batch])
            for snip, vec in zip(batch, vectors):
                snip.embedding = vec
            processed += len(batch)
        s.commit()

        remaining = s.execute(
            select(SemanticSnippet)
            .where(SemanticSnippet.is_deleted.is_(False))
            .where(SemanticSnippet.embedding.is_(None))
        ).scalars().all()
        total_remaining = len(remaining)
    logger.info(
        "semantic_embed_missing processed=%d remaining=%d",
        processed, total_remaining,
    )
    return {"processed": processed, "total_remaining": total_remaining}


# ---------------------------------------------------------------------------
# Document-Versions
# ---------------------------------------------------------------------------


def _doc_content_hash(title: str, content: str) -> str:
    payload = (title or "") + "\0" + (content or "")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@mcp.tool()
def document_list_versions(document_id: int, limit: int = 50) -> list:
    """Versionshistorie eines Documents — neueste zuerst, ohne content."""
    limit = max(1, min(int(limit or 50), 500))
    with session_for_tenant(_slug()) as s:
        rows = s.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == int(document_id))
            .where(DocumentVersion.is_deleted.is_(False))
            .order_by(DocumentVersion.version.desc())
            .limit(limit)
        ).scalars().all()
        return [
            {
                "id": v.id,
                "version": v.version,
                "title": v.title,
                "author_display_name": v.author_display_name,
                "content_hash": v.content_hash,
                "content_length": len(v.content or ""),
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in rows
        ]


@mcp.tool()
def document_get_version(version_id: int) -> dict:
    """Eine DocumentVersion vollstaendig inkl. content laden."""
    with session_for_tenant(_slug()) as s:
        v = s.get(DocumentVersion, int(version_id))
        if v is None or v.is_deleted:
            return {"error": f"DocumentVersion {version_id} nicht gefunden"}
        return _to_dict(v)


@mcp.tool()
def document_restore_version(document_id: int, version_id: int) -> dict:
    """Document auf einen alten Snapshot zuruecksetzen.

    Schreibt vorher einen Snapshot des aktuellen Stands (change_summary
    "Wiederhergestellt von v{version_id}") und inkrementiert die Version.
    """
    with session_for_tenant(_slug()) as s:
        doc = s.get(Document, int(document_id))
        if doc is None or doc.is_deleted:
            return {"error": f"Dokument {document_id} nicht gefunden"}
        v = s.get(DocumentVersion, int(version_id))
        if v is None or v.is_deleted or v.document_id != int(document_id):
            return {"error": f"DocumentVersion {version_id} nicht gefunden"}
        snapshot = DocumentVersion(
            document_id=doc.id,
            version=doc.version,
            title=doc.title,
            content=doc.content,
            format=doc.format,
            author_user_id=0,
            author_display_name=doc.author_display_name or "",
            content_hash=_doc_content_hash(doc.title, doc.content),
            change_summary=f"Wiederhergestellt von v{version_id}",
        )
        s.add(snapshot)
        doc.title = v.title
        doc.content = v.content
        doc.format = v.format
        doc.version += 1
        s.commit()
        s.refresh(doc)
        logger.info(
            "document_restore_version doc=%s -> v%s new_version=%s",
            doc.id, version_id, doc.version,
        )
        return _to_dict(doc)


@mcp.tool()
def document_diff(document_id: int, version_id: int, against: str = "current") -> dict:
    """Unified Diff zwischen DocumentVersion und current bzw. anderer Version."""
    doc_id = int(document_id)
    vid = int(version_id)
    with session_for_tenant(_slug()) as s:
        doc = s.get(Document, doc_id)
        if doc is None or doc.is_deleted:
            return {"error": f"Dokument {document_id} nicht gefunden"}
        v_from = s.get(DocumentVersion, vid)
        if v_from is None or v_from.is_deleted or v_from.document_id != doc_id:
            return {"error": f"DocumentVersion {version_id} nicht gefunden"}
        from_title = v_from.title or ""
        from_content = v_from.content or ""
        from_ts = v_from.created_at.strftime("%Y-%m-%d") if v_from.created_at else "?"
        from_state = (
            from_title, from_content, f"v{v_from.version} vom {from_ts}",
            v_from.id, v_from.version,
        )

        if against == "current" or against is None:
            to_state = (
                doc.title or "", doc.content or "", "aktuell",
                doc.id, doc.version,
            )
        else:
            try:
                aid = int(against)
            except (TypeError, ValueError):
                return {"error": f"ungueltige Version: {against!r}"}
            v_to = s.get(DocumentVersion, aid)
            if v_to is None or v_to.is_deleted or v_to.document_id != doc_id:
                return {"error": f"DocumentVersion {against} nicht gefunden"}
            to_ts = v_to.created_at.strftime("%Y-%m-%d") if v_to.created_at else "?"
            to_state = (
                v_to.title or "", v_to.content or "", f"v{v_to.version} vom {to_ts}",
                v_to.id, v_to.version,
            )

        from_title, from_content, from_label, from_id, from_version = from_state
        to_title, to_content, to_label, to_id, to_version = to_state

        if from_title == to_title:
            title_diff = [{"kind": "equal", "from": from_title, "to": to_title}]
        else:
            title_diff = [{"kind": "replace", "from": from_title, "to": to_title}]

        from_lines = from_content.split("\n")
        to_lines = to_content.split("\n")
        matcher = difflib.SequenceMatcher(a=from_lines, b=to_lines, autojunk=False)
        content_diff = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            content_diff.append({
                "kind": tag,
                "old_start": i1, "old_end": i2,
                "new_start": j1, "new_end": j2,
                "old_text": "\n".join(from_lines[i1:i2]),
                "new_text": "\n".join(to_lines[j1:j2]),
            })

        unified = "\n".join(difflib.unified_diff(
            from_lines, to_lines,
            fromfile=from_label, tofile=to_label,
            lineterm="",
        ))

        return {
            "from": {"id": from_id, "version": from_version, "title": from_title, "label": from_label},
            "to":   {"id": to_id,   "version": to_version,   "title": to_title,   "label": to_label},
            "title_diff": title_diff,
            "content_diff": content_diff,
            "unified": unified,
        }


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    logger.info(
        "Starte wai-crm-mcp auf Port %s via SSE (tenant=%s)", port, _slug()
    )
    mcp.run(transport="sse")
