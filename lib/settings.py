"""Settings-Resolver — Plan 03 (Vision §27).

Eine einzige API fuer alle "soll X als Default Y oder Z?"-Fragen. Schichten
in V1 echt verfuegbar: Plattform + Tenant. Entity-Type, Entity und Chat
sind als Resolver-Pfad implementiert, werden aber heute noch nicht
gesetzt — Stubs fallen sauber auf die naechsttiefe Schicht durch.

Reihenfolge der Aufloesung:
    chat -> entity -> entity_type -> tenant -> platform -> PLATFORM_DEFAULTS

Caching: pro Request-Lifecycle (ContextVar). resolve(key) zweimal in
derselben Runde kostet keinen Round-Trip. ``settings_cache_reset()`` wird
bei FastAPI-Request-Start gerufen.

Mini-Audit: ``set_value`` schreibt direkt nach logging_db.entity_change
(Plan 04). Setting selbst hat ``__change_log__ = False`` und wird vom
ORM-Hook bewusst ausgespart, damit kein Hen-Ei-Loop entsteht (Hook ruft
resolve -> Hook -> ...).
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any

from sqlalchemy import select

from lib.db import session_for_admin, session_for_tenant
from lib.entities.admin.setting import Setting as AdminSetting
from lib.entities.tenant.setting import Setting as TenantSetting
from lib.logging import get_logger

log = get_logger(__name__)

# Plattform-Defaults — Fallback, wenn weder DB noch ContextVar einen Wert hat.
# Werte koennen pro Plattform/Tenant/Entity/Chat in der DB ueberschrieben werden.
PLATFORM_DEFAULTS: dict[str, Any] = {
    "ai.changes.mode": "direct",  # Plan 04 — alternativ "draft" | "draft_for_critical_fields"
    "agent.sub_chat.max_depth": 5,
    "agent.model.default": "gpt-5.5",
    "audit.change_log.retention_days": 365,
    # Plan 07 — erlaubte Process-Status-Werte. process_mcp validiert dagegen.
    # Tenant/Workflow-Engine §7 koennen das spaeter ueberschreiben.
    "process.status.allowed_values": [
        "neu",
        "in_arbeit",
        "wartet_auf_kunde",
        "wartet_intern",
        "abgeschlossen",
        "abgebrochen",
    ],
    "process.status.closed_values": ["abgeschlossen", "abgebrochen"],
    # Plan 08 — Auto-Event-Whitelist je target_cls. Listener in
    # lib/audit_to_event.py liest dieses Setting und materialisiert pro
    # passendem EntityChange ein BusinessEvent. Pro Tenant via set_value
    # (scope="tenant" oder "entity_type") ueberschreibbar.
    "events.auto_rules.core.process": [
        {
            "field": "status",
            "event_type": "status_changed",
            "title_template": "Status: {old} → {new}",
        },
    ],
}

VALID_SCOPES = ("platform", "tenant", "entity_type", "entity", "chat")

# Per-Request-Cache. Key: ("chat", chat_id, "tenant", tenant, "ec", entity_cls,
# "ei", entity_id, "k", key).
_resolve_cache: ContextVar[dict | None] = ContextVar(
    "wai_settings_cache", default=None
)

# Optionaler Override fuer den naechsten Setting-Change-Eintrag (z.B. wenn
# ein Agent einen sprechenden Summary-Satz mitschickt). In V1 noch ungenutzt.
_setting_change_summary: ContextVar[str | None] = ContextVar(
    "wai_setting_change_summary", default=None
)


def settings_cache_reset() -> None:
    """Per-Request-Cache verwerfen. Gateway-Middleware ruft das auf."""
    _resolve_cache.set({})


def _cache_get(cache_key: tuple) -> tuple[bool, Any]:
    cache = _resolve_cache.get()
    if cache is None:
        return False, None
    if cache_key in cache:
        return True, cache[cache_key]
    return False, None


def _cache_set(cache_key: tuple, value: Any) -> None:
    cache = _resolve_cache.get()
    if cache is None:
        return
    cache[cache_key] = value


def _read_tenant_value(
    tenant: str,
    *,
    scope: str,
    scope_ref: str,
    entity_cls: str,
    entity_id: int,
    key: str,
) -> tuple[bool, Any]:
    with session_for_tenant(tenant) as s:
        row = s.execute(
            select(TenantSetting.value)
            .where(TenantSetting.scope == scope)
            .where(TenantSetting.scope_ref == scope_ref)
            .where(TenantSetting.entity_cls == entity_cls)
            .where(TenantSetting.entity_id == entity_id)
            .where(TenantSetting.key == key)
            .where(TenantSetting.is_deleted.is_(False))
            .limit(1)
        ).first()
    if row is None:
        return False, None
    return True, row[0]


def _read_platform_value(key: str) -> tuple[bool, Any]:
    with session_for_admin() as s:
        row = s.execute(
            select(AdminSetting.value)
            .where(AdminSetting.scope == "platform")
            .where(AdminSetting.key == key)
            .where(AdminSetting.is_deleted.is_(False))
            .limit(1)
        ).first()
    if row is None:
        return False, None
    return True, row[0]


def resolve(
    key: str,
    *,
    tenant: str | None = None,
    entity_cls: str | None = None,
    entity_id: int | None = None,
    chat_id: int | None = None,
) -> Any:
    """Loest einen Setting-Key entlang der Schicht-Hierarchie auf.

    Liefert den ersten Treffer aus chat -> entity -> entity_type -> tenant
    -> platform -> PLATFORM_DEFAULTS. KeyError, wenn ein Key nirgends
    definiert ist (echter Programmierfehler — Key fehlt im Default-Dict).
    """
    cache_key = (
        "k", key,
        "t", tenant or "",
        "ec", entity_cls or "",
        "ei", entity_id or 0,
        "c", chat_id or 0,
    )
    hit, cached = _cache_get(cache_key)
    if hit:
        return cached

    # 1. Chat
    if chat_id is not None and tenant:
        found, val = _read_tenant_value(
            tenant,
            scope="chat", scope_ref=str(chat_id),
            entity_cls="", entity_id=0, key=key,
        )
        if found:
            _cache_set(cache_key, val)
            return val

    # 2. Entity-Instanz
    if entity_cls and entity_id and tenant:
        found, val = _read_tenant_value(
            tenant,
            scope="entity", scope_ref="",
            entity_cls=entity_cls, entity_id=entity_id, key=key,
        )
        if found:
            _cache_set(cache_key, val)
            return val

    # 3. Entity-Typ
    if entity_cls and tenant:
        found, val = _read_tenant_value(
            tenant,
            scope="entity_type", scope_ref=entity_cls,
            entity_cls="", entity_id=0, key=key,
        )
        if found:
            _cache_set(cache_key, val)
            return val

    # 4. Tenant
    if tenant:
        found, val = _read_tenant_value(
            tenant,
            scope="tenant", scope_ref=tenant,
            entity_cls="", entity_id=0, key=key,
        )
        if found:
            _cache_set(cache_key, val)
            return val

    # 5. Plattform-DB
    found, val = _read_platform_value(key)
    if found:
        _cache_set(cache_key, val)
        return val

    # 6. Hardcoded Default
    if key in PLATFORM_DEFAULTS:
        val = PLATFORM_DEFAULTS[key]
        _cache_set(cache_key, val)
        return val

    raise KeyError(
        f"Setting-Key {key!r} nirgends definiert — weder Tenant/Entity/Chat,"
        " noch Plattform-DB, noch PLATFORM_DEFAULTS. Key in PLATFORM_DEFAULTS"
        " ergaenzen oder Tippfehler korrigieren."
    )


# ---------------------------------------------------------------------------
# Setter
# ---------------------------------------------------------------------------


def _validate_setter_args(
    *,
    scope: str,
    scope_ref: str,
    entity_cls: str,
    entity_id: int,
    value: Any,
) -> None:
    if scope not in VALID_SCOPES:
        raise ValueError(
            f"Ungueltiger scope: {scope!r}. Erlaubt: {VALID_SCOPES}"
        )
    if scope == "entity":
        if not entity_cls or entity_id <= 0:
            raise ValueError(
                "scope='entity' braucht entity_cls + entity_id > 0"
            )
    # JSON-Serialisierbarkeit pruefen
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Value nicht JSON-serialisierbar: {exc}") from exc


def set_value(
    key: str,
    value: Any,
    *,
    scope: str,
    scope_ref: str = "",
    entity_cls: str = "",
    entity_id: int = 0,
    tenant: str | None = None,
    set_by: int = 0,
) -> None:
    """Upsert eines Settings + Mini-Audit-Eintrag in logging_db.

    Plattform-Settings landen in admin_db, alles andere in tenant_db
    (``tenant`` muss dann gesetzt sein). Cache wird invalidiert.
    """
    _validate_setter_args(
        scope=scope, scope_ref=scope_ref,
        entity_cls=entity_cls, entity_id=entity_id, value=value,
    )

    if scope == "platform":
        old, change_type, target_id = _upsert_admin(
            scope=scope, scope_ref=scope_ref,
            entity_cls=entity_cls, entity_id=entity_id,
            key=key, value=value, set_by=set_by,
        )
        target_cls = "admin.setting"
    else:
        if not tenant:
            raise ValueError(
                f"Tenant-Slug muss bei scope={scope!r} gesetzt sein."
            )
        old, change_type, target_id = _upsert_tenant(
            tenant=tenant,
            scope=scope, scope_ref=scope_ref,
            entity_cls=entity_cls, entity_id=entity_id,
            key=key, value=value, set_by=set_by,
        )
        target_cls = "core.setting"

    settings_cache_reset()

    _write_setting_change(
        tenant=tenant or "",
        target_cls=target_cls, target_id=target_id,
        change_type=change_type,
        scope=scope, scope_ref=scope_ref,
        entity_cls=entity_cls, entity_id=entity_id,
        key=key, old=old, new=value, set_by=set_by,
    )


def _upsert_admin(
    *,
    scope: str, scope_ref: str,
    entity_cls: str, entity_id: int,
    key: str, value: Any, set_by: int,
) -> tuple[Any, str, int]:
    with session_for_admin() as s:
        row = s.execute(
            select(AdminSetting)
            .where(AdminSetting.scope == scope)
            .where(AdminSetting.scope_ref == scope_ref)
            .where(AdminSetting.entity_cls == entity_cls)
            .where(AdminSetting.entity_id == entity_id)
            .where(AdminSetting.key == key)
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            row = AdminSetting(
                scope=scope, scope_ref=scope_ref,
                entity_cls=entity_cls, entity_id=entity_id,
                key=key, value=value, set_by=set_by,
                is_deleted=False,
            )
            s.add(row)
            s.flush()
            s.commit()
            return None, "create", row.id
        old = row.value
        row.value = value
        row.set_by = set_by
        row.is_deleted = False
        s.commit()
        return old, "update", row.id


def _upsert_tenant(
    *,
    tenant: str,
    scope: str, scope_ref: str,
    entity_cls: str, entity_id: int,
    key: str, value: Any, set_by: int,
) -> tuple[Any, str, int]:
    with session_for_tenant(tenant) as s:
        row = s.execute(
            select(TenantSetting)
            .where(TenantSetting.scope == scope)
            .where(TenantSetting.scope_ref == scope_ref)
            .where(TenantSetting.entity_cls == entity_cls)
            .where(TenantSetting.entity_id == entity_id)
            .where(TenantSetting.key == key)
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            row = TenantSetting(
                scope=scope, scope_ref=scope_ref,
                entity_cls=entity_cls, entity_id=entity_id,
                key=key, value=value, set_by=set_by,
                is_deleted=False,
            )
            s.add(row)
            s.flush()
            s.commit()
            return None, "create", row.id
        old = row.value
        row.value = value
        row.set_by = set_by
        row.is_deleted = False
        s.commit()
        return old, "update", row.id


def _write_setting_change(
    *,
    tenant: str,
    target_cls: str, target_id: int,
    change_type: str,
    scope: str, scope_ref: str,
    entity_cls: str, entity_id: int,
    key: str, old: Any, new: Any, set_by: int,
) -> None:
    """Setting-Mini-Audit nach logging_db.entity_change.

    Wird nur ausgefuehrt, wenn die Tabelle entity_change existiert (sonst
    waere die Plattform abhaengig vom Plan-04-Migration-Stand). Die
    Setting-Mechanik funktioniert auch ohne diesen Eintrag — der Mini-Audit
    ist Best-Effort.
    """
    try:
        from lib.audit import write_setting_change_log  # lazy import
    except Exception:
        return
    summary = _setting_change_summary.get() or None
    _setting_change_summary.set(None)
    try:
        write_setting_change_log(
            tenant_id=tenant,
            target_cls=target_cls, target_id=target_id,
            change_type=change_type,
            scope=scope, scope_ref=scope_ref,
            entity_cls=entity_cls, entity_id=entity_id,
            key=key, old=old, new=new, set_by=set_by,
            summary=summary,
        )
    except Exception:
        # Audit-Failure darf das Setzen nicht versenken.
        log.warning(
            "setting_audit_write_failed key=%s scope=%s tenant=%s",
            key, scope, tenant, exc_info=True,
        )


def set_change_summary(summary: str) -> None:
    """Optional: setzt einen sprechenden Summary fuer den naechsten set_value().

    Wirkt einmalig — nach dem naechsten ``set_value`` wird die Variable
    zurueckgesetzt.
    """
    _setting_change_summary.set(summary or None)
