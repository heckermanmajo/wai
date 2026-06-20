"""Sync-Logik fuer die semantische Schicht.

Eine Quell-Entity (Document/Note/Task/...) wird in eine ``SemanticFassade`` +
N ``SemanticSnippet`` ueberfuehrt. content_hash bindet die letzte indizierte
Version; aendert er sich, werden die alten Snippets soft-geloescht und neue
geschrieben.

Auto-Sync laeuft outbox-basiert: ``after_insert``/``after_update`` der
indizierten Entities tragen ``(alias, id)`` in ``session.info``. Beim
``after_commit`` der Session wird die Outbox in einer NEUEN Session
abgearbeitet — wir koennen nicht in der gerade committeten Session
weiter-flushen.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from lib.db import session_for_tenant
from lib.logging import get_logger
from lib.polymorphic import alias_for, resolve_target_cls
from lib.semantic import compute_content_hash
from lib.tenant_context import require_tenant

# Entity-Klassen werden lazy importiert, um Zirkularitaeten mit
# lib/entities/tenant/__init__.py zu vermeiden (das Paket-init laedt
# am Ende `register_sync_listeners` aus diesem Modul).


def _entities():
    from lib.entities.tenant.semantic_fassade import SemanticFassade
    from lib.entities.tenant.semantic_snippet import SemanticSnippet
    return SemanticFassade, SemanticSnippet

logger = get_logger(__name__)

_OUTBOX_KEY = "semantic_resync"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def chunk_markdown(text: str, max_chars: int = 1200) -> list[str]:
    """Naiver Chunker nach Absatz-Grenzen (\\n\\n).

    Absaetze, die laenger als max_chars sind, werden hart in max_chars-Stuecke
    geschnitten. Leere Chunks werden verworfen.
    """
    if not text:
        return []
    chunks: list[str] = []
    buf = ""
    for para in text.split("\n\n"):
        para = para.strip("\n")
        if not para:
            continue
        if len(para) > max_chars:
            # buf vorher rausschreiben
            if buf:
                chunks.append(buf.strip())
                buf = ""
            for i in range(0, len(para), max_chars):
                piece = para[i : i + max_chars].strip()
                if piece:
                    chunks.append(piece)
            continue
        candidate = (buf + "\n\n" + para) if buf else para
        if len(candidate) > max_chars:
            if buf:
                chunks.append(buf.strip())
            buf = para
        else:
            buf = candidate
    if buf.strip():
        chunks.append(buf.strip())
    return [c for c in chunks if c]


def estimate_tokens(text: str) -> int:
    """Sehr grobe Token-Schaetzung; reicht fuer Budget-Aussagen vor Embedding."""
    return len(text) // 4


# ---------------------------------------------------------------------------
# Core sync
# ---------------------------------------------------------------------------


def sync_fassade(session: Session, resource, alias: str | None = None) -> "SemanticFassade":
    """Synchronisiert Fassade + Snippets fuer eine Resource.

    ``alias`` ist der Polymorph-Alias der Resource-Klasse (z.B. ``"core.document"``).
    Wird nichts uebergeben, wird er ueber ``alias_for(type(resource))`` aufgeloest.
    Session-Flush bleibt dem Caller ueberlassen.
    """
    if alias is None:
        alias = alias_for(type(resource))
    if not alias:
        raise RuntimeError(
            f"Keine Polymorph-Alias-Registrierung fuer {type(resource).__name__} — "
            "@register_entity(...) fehlt?"
        )

    SemanticFassade, _ = _entities()

    name = resource.get_resource_name()
    markdown = resource.get_resource_markdown() or ""
    short = resource.get_resource_short() or ""
    url = resource.get_resource_url()
    resource_type = resource.get_resource_type()
    new_hash = compute_content_hash(name, markdown)
    now = datetime.now(timezone.utc)

    fassade = session.execute(
        select(SemanticFassade)
        .where(SemanticFassade.entity_class == alias)
        .where(SemanticFassade.entity_id == int(resource.id))
        .where(SemanticFassade.is_deleted.is_(False))
        .limit(1)
    ).scalar_one_or_none()

    if fassade is None:
        fassade = SemanticFassade(
            entity_class=alias,
            entity_id=int(resource.id),
            resource_type=resource_type,
            name=name,
            abstract=short,
            url=url,
            content_hash=new_hash,
            source_updated_at=now,
        )
        session.add(fassade)
        session.flush()
        _rebuild_snippets(session, fassade, markdown, new_hash)
        logger.info(
            "semantic.fassade angelegt fuer %s id=%s -> fassade_id=%s",
            alias, resource.id, fassade.id,
        )
        return fassade

    if fassade.content_hash == new_hash:
        fassade.source_updated_at = now
        # Metadata (URL/Name) hat sich evtl. nicht-hash-relevant geaendert
        # — Hash deckt name+markdown ab; URL ist unabhaengig und sollte mit.
        if fassade.url != url:
            fassade.url = url
        if fassade.resource_type != resource_type:
            fassade.resource_type = resource_type
        return fassade

    fassade.resource_type = resource_type
    fassade.name = name
    fassade.abstract = short
    fassade.url = url
    fassade.content_hash = new_hash
    fassade.source_updated_at = now
    _rebuild_snippets(session, fassade, markdown, new_hash)
    logger.info(
        "semantic.fassade rebuild fuer %s id=%s fassade_id=%s",
        alias, resource.id, fassade.id,
    )
    return fassade


def _rebuild_snippets(
    session: Session,
    fassade: "SemanticFassade",
    markdown: str,
    content_hash: str,
) -> None:
    """Alte Snippets soft-loeschen, Markdown neu chunken, Embeddings berechnen.

    Embedding-Failure (kein API-Key, Rate-Limit, Network) ist nicht fatal —
    die Snippets werden mit ``embedding=None`` persistiert und koennen spaeter
    via ``semantic_embed_missing`` nachgezogen werden.
    """
    _, SemanticSnippet = _entities()
    existing = session.execute(
        select(SemanticSnippet)
        .where(SemanticSnippet.fassade_id == fassade.id)
        .where(SemanticSnippet.is_deleted.is_(False))
    ).scalars().all()
    for snip in existing:
        snip.is_deleted = True

    chunks = chunk_markdown(markdown)
    new_snippets: list = []
    for idx, text in enumerate(chunks):
        snip = SemanticSnippet(
            fassade_id=fassade.id,
            idx=idx,
            text=text,
            char_len=len(text),
            token_estimate=estimate_tokens(text),
            embedding=None,
            content_hash=content_hash,
        )
        session.add(snip)
        new_snippets.append(snip)

    if not new_snippets:
        return

    session.flush()
    try:
        from lib.embeddings import embed_texts  # lazy: kein Crash bei fehlendem Key beim Modul-Laden
        vectors = embed_texts([s.text for s in new_snippets])
        for snip, vec in zip(new_snippets, vectors):
            snip.embedding = vec
    except Exception:
        logger.warning(
            "semantic embeddings nicht berechnet (n=%d) — Snippets bleiben ohne Vektor",
            len(new_snippets),
            exc_info=True,
        )
        for snip in new_snippets:
            snip.embedding = None


# ---------------------------------------------------------------------------
# Outbox / Event-Listener
# ---------------------------------------------------------------------------


def _queue_resync(session: Session, alias: str, entity_id: int) -> None:
    bag: set[tuple[str, int]] = session.info.setdefault(_OUTBOX_KEY, set())
    bag.add((alias, int(entity_id)))


def _drain_outbox(session: Session) -> None:
    """Nach erfolgreichem Commit: alle gequeueden Entities re-syncen.

    Wir oeffnen eine NEUE Session pro drain — die gerade committete Session
    soll nicht weiter beschrieben werden (after_commit ist nach dem Flush).
    """
    bag: set[tuple[str, int]] | None = session.info.pop(_OUTBOX_KEY, None)
    if not bag:
        return
    try:
        slug = require_tenant()
    except RuntimeError:
        logger.info(
            "semantic outbox skip — kein Tenant-Kontext (n=%d)", len(bag)
        )
        return

    SemanticFassade, SemanticSnippet = _entities()
    try:
        with session_for_tenant(slug) as fresh:
            for alias, entity_id in bag:
                cls = resolve_target_cls(alias)
                if cls is None:
                    logger.warning(
                        "semantic outbox: alias %r nicht registriert", alias
                    )
                    continue
                resource = fresh.get(cls, entity_id)
                if resource is None:
                    logger.info(
                        "semantic outbox: %s id=%s nicht (mehr) vorhanden",
                        alias, entity_id,
                    )
                    continue
                if getattr(resource, "is_deleted", False):
                    # Fassade fuer geloeschte Resource ebenfalls soft-loeschen
                    fassade = fresh.execute(
                        select(SemanticFassade)
                        .where(SemanticFassade.entity_class == alias)
                        .where(SemanticFassade.entity_id == int(entity_id))
                        .where(SemanticFassade.is_deleted.is_(False))
                        .limit(1)
                    ).scalar_one_or_none()
                    if fassade is not None:
                        fassade.is_deleted = True
                        snippets = fresh.execute(
                            select(SemanticSnippet)
                            .where(SemanticSnippet.fassade_id == fassade.id)
                            .where(SemanticSnippet.is_deleted.is_(False))
                        ).scalars().all()
                        for snip in snippets:
                            snip.is_deleted = True
                    continue
                try:
                    sync_fassade(fresh, resource, alias)
                except Exception:
                    logger.exception(
                        "semantic outbox: sync_fassade fehlgeschlagen "
                        "alias=%s id=%s", alias, entity_id,
                    )
            fresh.commit()
    except Exception:
        logger.exception("semantic outbox: drain fehlgeschlagen (n=%d)", len(bag))


def _make_after_write(alias: str):
    def _listener(mapper, connection, target) -> None:
        try:
            sess = Session.object_session(target)
            if sess is None:
                return
            _queue_resync(sess, alias, target.id)
        except Exception:
            logger.exception("semantic listener fehler (alias=%s)", alias)
    return _listener


def _after_commit(session: Session) -> None:
    _drain_outbox(session)


_listeners_registered = False


def register_sync_listeners() -> None:
    """Registriert after_insert/after_update auf Document/Note/Task und
    after_commit auf der Session-Klasse. Idempotent."""
    global _listeners_registered
    if _listeners_registered:
        return

    # Importe hier drin, um Zirkel zu vermeiden (semantic_sync wird vom
    # Entities-Paket am Ende des __init__ aufgerufen).
    from lib.entities.tenant.document import Document
    from lib.entities.tenant.note import Note
    from lib.entities.tenant.task import Task

    pairs: Iterable[tuple[type, str]] = (
        (Document, "core.document"),
        (Note, "core.note"),
        (Task, "core.task"),
    )
    for cls, alias in pairs:
        listener = _make_after_write(alias)
        event.listen(cls, "after_insert", listener)
        event.listen(cls, "after_update", listener)

    event.listen(Session, "after_commit", _after_commit)
    _listeners_registered = True
    logger.info("semantic sync listeners registriert")
