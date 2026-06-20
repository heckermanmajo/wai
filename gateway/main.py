"""wai Gateway — FastAPI entry.

Alle inhaltlichen Routen liegen unter `/<tenant-slug>/...` und sind via
Session-Cookie (siehe lib/auth.py) auth-geschuetzt. Globale Service-
Routen (Health, Trace-Browser, Error-Reporting) bleiben ohne Slug.

Globale Routen:
    GET  /                         → Redirect auf /login
    GET  /login                    → globaler Login (Username/Email + Passwort)
    POST /login                    → Auth -> Auto-Redirect oder Tenant-Picker
    POST /login/pick               → Tenant-Picker absenden (signed token)
    GET  /health                   → Liveness
    GET  /demo/info                → Mock-Tools/Kunden/Beispiele
    POST /errors/report            → Browser-Fehlerreports
    GET  /traces                   → Trace-Browser
    GET  /api/traces[/{uid}]       → Trace-JSON

Tenant-Routen (alle auth-geschuetzt):
    GET  /<slug>/login             → 308-Redirect auf /login (Legacy)
    POST /<slug>/login             → 307-Redirect auf /login (Legacy)
    GET  /<slug>/logout            → Cookie loeschen, Redirect /login
    GET  /<slug>/                  → Chat-UI
    GET  /<slug>/chats             → eigene + geteilte Chats (JSON)
    POST /<slug>/chats             → neuer Chat
    GET  /<slug>/chats/{id}        → Chat-Detail (Messages)
    POST /<slug>/chats/{id}/messages  → User-Message + SSE-Stream
    POST /<slug>/chats/{id}/clone  → Chat klonen
    POST /<slug>/chats/{id}/share  → is_shared togglen
    DELETE /<slug>/chats/{id}      → Soft-Delete (Archiv)
    GET  /<slug>/chats/{id}/artifacts → Mappen-Inhalt
    GET  /<slug>/entity/{cls}/{id} → CRM-Detail per MCP
    POST /<slug>/ingest/voice      → Audio + Attachment + ChatArtifact
    POST /<slug>/ingest/image      → Bild + Attachment + ChatArtifact
"""
import asyncio
import difflib
import hashlib
import json
import os
import time
import traceback

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from mcp import ClientSession
from mcp.client.sse import sse_client
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_, select

from lib.auth import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
    UserContext,
    _ctx_from_cookie_only,
    authenticate_global,
    create_pending_pick_token,
    create_session_token,
    list_dev_users,
    read_pending_pick_token,
    require_debug_user,
    require_user,
)
from lib.chat_clone import clone_chat
from lib.db import session_for_logging, session_for_tenant
from lib.entities.logging import ErrorReport
from lib.entities.tenant import (
    AiChat,
    AiMessage,
    AiToolCall,
    Attachment,
    ChatArtifact,
    Comment,
    Document,
    DocumentVersion,
    Note,
    Task,
)
from lib.event_store import (
    create_trace,
    finalize_trace,
    get_trace_with_events,
    list_traces,
    persist_event,
)
from lib.events import VOLATILE_EVENT_TYPES, EventEmitter, new_trace_uid, now_utc
from lib.logging import setup_logging, get_logger
from lib.storage import (
    bucket_for_tenant,
    build_object_key,
    ensure_bucket,
    presigned_get_url,
    upload_bytes,
)
from lib.polymorphic import validate_target
from lib.audit import install_change_log_hooks, list_entity_changes
from lib.audit_to_event import install_event_hooks
from lib.settings import settings_cache_reset
from lib.tenant_context import set_tenant, set_trace_uid
from lib.transcribe import transcribe
from agents.manager.agent import chat as manager_chat
from gateway.ui_chat import render_chat
from gateway.ui_login import render_login, render_tenant_picker
from mcp_servers.mock_mcp.data import BEISPIEL_PROMPTS, KUNDEN_DB, TOOLS

MCP_CRM_URL = os.environ.get("MCP_CRM_URL", "http://crm_mcp:8001/sse")
ENTITY_TOOLS: dict[str, str] = {
    "contact": "contact_get",
    "account": "account_get",
    "lead": "lead_get",
    "deal": "deal_get",
}

setup_logging()
log = get_logger(__name__)

# Plan 04 — Change-Log-Hooks bei Modul-Import installieren. Idempotent.
install_change_log_hooks()
# Plan 08 — Auto-Event-Listener REIHENFOLGE-KRITISCH: muss nach
# install_change_log_hooks() laufen, damit unser after_commit-Hook nach
# audit._after_commit feuert und den committed-Snapshot findet.
install_event_hooks()

app = FastAPI(title="wai gateway", version="0.2.0")

# Explizite Origins, weil "*" + allow_credentials=True von Browsern abgelehnt wird.
# CORS_ALLOWED_ORIGINS kann zusaetzliche Hosts via Komma einbringen (z.B. Produktion).
_default_cors = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8500,http://127.0.0.1:8500"
_cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", _default_cors).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _settings_cache_per_request(request: Request, call_next):
    """Plan 03 — Per-Request-Cache des Settings-Resolver leeren."""
    settings_cache_reset()
    return await call_next(request)


# ─────────────────────────────────────────────────────────────────────────────
# Globale Exception-Handler + Error-Report
# ─────────────────────────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    tb = traceback.format_exc()
    log.error("unhandled_exception path=%s error=%s\n%s", request.url.path, exc, tb)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": tb,
                "path": str(request.url.path),
                "method": request.method,
            }
        },
    )


class ErrorReportRequest(BaseModel):
    comment: str = ""
    url: str = ""
    status_code: int = 0
    error_type: str = ""
    message: str = ""
    stack: str = ""
    user_agent: str = ""
    session_id: str = ""
    tenant_id: str = ""
    context: dict = Field(default_factory=dict)


@app.post("/errors/report")
def errors_report(req: ErrorReportRequest) -> dict:
    with session_for_logging() as s:
        row = ErrorReport(
            tenant_id=req.tenant_id or "",
            session_id=req.session_id or "",
            url=req.url or "",
            status_code=int(req.status_code or 0),
            error_type=req.error_type or "",
            message=req.message or "",
            stack=req.stack or "",
            user_agent=req.user_agent or "",
            comment=req.comment or "",
            context=req.context or {},
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return {"id": row.id, "created_at": row.created_at.isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
# Globale Service-Routen
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo/info")
def demo_info() -> dict:
    kunden = [
        {
            "name": name.title(),
            "projekt": d["projekt"],
            "status": d["status"],
            "rechnung_offen": d["rechnung_offen"],
            "notizen": d["notizen"],
        }
        for name, d in KUNDEN_DB.items()
    ]
    return {"tools": TOOLS, "kunden": kunden, "beispiele": BEISPIEL_PROMPTS}


@app.get("/")
def landing() -> Response:
    return RedirectResponse(url="/login", status_code=303)


def _set_session_cookie(response: Response, user_id: int, tenant_slug: str) -> None:
    """Schreibt das wai_session-Cookie auf die Response.

    Cross-Port (Next.js dev :3000 → Backend :8500) braucht samesite=lax und secure=False;
    in Produktion (gleiche Origin) sollte samesite=lax + secure=True via Env-Override gesetzt werden.
    """
    token = create_session_token(user_id, tenant_slug)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
    )


class LoginRequest(BaseModel):
    login: str
    password: str


class LoginPickRequest(BaseModel):
    token: str
    tenant_slug: str


@app.get("/me")
def me_endpoint(request: Request) -> dict:
    """Liest die aktuelle Session aus dem Cookie.

    Next.js [slug]/layout.tsx ruft das vor jedem Tenant-Routing — billiger Auth-Check
    ohne Slug-Bindung an die URL, weil der Cookie selbst den aktiven Tenant kennt.
    """
    ctx = _ctx_from_cookie_only(request)
    if ctx is None:
        raise HTTPException(status_code=401, detail="nicht eingeloggt")
    return {
        "user_id": ctx.user_id,
        "username": ctx.username,
        "display_name": ctx.display_name,
        "tenant_slug": ctx.tenant_slug,
        "tenant_id": ctx.tenant_id,
        "tenant_role": ctx.tenant_role,
    }


@app.get("/api/dev-users")
def api_dev_users() -> dict:
    """Liste aktiver Dev-User + Tenants — nur fuer die Dev-Login-Hilfe im Next.js-Frontend."""
    try:
        users = list_dev_users()
    except Exception as exc:  # noqa: BLE001 — Login darf bei DB-Fluff nicht crashen
        log.warning("list_dev_users failed: %s", exc)
        users = []
    return {"users": users}


@app.get("/login", response_class=HTMLResponse)
def login_page_global(err: str = "", login: str = "") -> str:
    """Legacy HTML-Form (wird in Phase E entfernt). Next.js rendert die Login-UI selbst."""
    try:
        users = list_dev_users()
    except Exception as exc:  # noqa: BLE001
        log.warning("list_dev_users failed: %s", exc)
        users = []
    return render_login(error=err, dev_users=users, prefill=login)


@app.post("/login")
async def login_submit_global(req: LoginRequest, response: Response) -> dict:
    result = authenticate_global(req.login.strip(), req.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Login fehlgeschlagen")
    if not result.tenants:
        raise HTTPException(status_code=403, detail="Keine aktiven Tenants fuer diesen Account")
    if len(result.tenants) == 1:
        slug, name = result.tenants[0]
        log.info("login.ok user=%s id=%d tenant=%s (auto)", result.username, result.user_id, slug)
        _set_session_cookie(response, result.user_id, slug)
        return {
            "status": "ok",
            "tenant_slug": slug,
            "tenant_name": name,
            "user": {
                "user_id": result.user_id,
                "username": result.username,
                "display_name": result.display_name,
            },
        }
    log.info("login.picker user=%s id=%d tenants=%d", result.username, result.user_id, len(result.tenants))
    pending = create_pending_pick_token(result.user_id)
    return {
        "status": "pick",
        "pending_token": pending,
        "tenants": [{"slug": slug, "name": name} for slug, name in result.tenants],
        "user": {
            "user_id": result.user_id,
            "username": result.username,
            "display_name": result.display_name,
        },
    }


@app.post("/login/pick")
async def login_pick_tenant(req: LoginPickRequest, response: Response) -> dict:
    from lib.auth import _load_user_context

    user_id = read_pending_pick_token(req.token)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Sitzung abgelaufen, bitte neu einloggen")
    ctx = _load_user_context(user_id, req.tenant_slug)
    if ctx is None:
        raise HTTPException(status_code=403, detail="Ungueltiger Tenant fuer diesen User")
    log.info("login.pick user=%s tenant=%s", ctx.username, req.tenant_slug)
    _set_session_cookie(response, ctx.user_id, ctx.tenant_slug)
    return {
        "status": "ok",
        "tenant_slug": ctx.tenant_slug,
        "user": {
            "user_id": ctx.user_id,
            "username": ctx.username,
            "display_name": ctx.display_name,
        },
    }


@app.get("/traces")
def traces_ui_legacy_redirect() -> Response:
    """Plan 06 — Legacy-SSR-View entfernt, Redirect auf den Next-Debug-Tab."""
    return RedirectResponse(url="/debug/traces", status_code=308)


@app.get("/api/traces")
def api_list_traces(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tenant_id: str | None = Query(None),
    status: str | None = Query(None),
) -> dict:
    rows = list_traces(limit=limit, offset=offset, tenant_id=tenant_id, status=status)
    return {"traces": rows, "limit": limit, "offset": offset, "count": len(rows)}


@app.get("/api/traces/{trace_uid}")
def api_get_trace(trace_uid: str) -> dict:
    payload = get_trace_with_events(trace_uid)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_uid} nicht gefunden")
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# Plan 06 — Debug-View API (Auth: platform_role in {"admin", "supporter"})
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/api/debug/me")
def debug_me(debug=Depends(require_debug_user)) -> dict:
    return {
        "user_id": debug.user_id,
        "username": debug.username,
        "display_name": debug.display_name,
        "platform_role": debug.platform_role,
        "memberships": debug.memberships,
    }


def _tenant_scope_filter(debug, requested_tenant: str | None) -> str | None:
    """Plan 06 — Plattform-Admin sieht alles, Supporter nur seine Memberships.

    Liefert den effektiven tenant_id-Filter fuer list_traces oder None
    fuer "alle Tenants" (nur admin).
    """
    if debug.platform_role == "admin":
        return requested_tenant
    # Supporter: nur Tenants seiner Memberships, optional explizit gefiltert.
    allowed = set(debug.memberships)
    if requested_tenant:
        if requested_tenant not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Tenant {requested_tenant!r} nicht in deinen Memberships",
            )
        return requested_tenant
    if not allowed:
        raise HTTPException(status_code=403, detail="Keine Tenant-Memberships")
    if len(allowed) == 1:
        return next(iter(allowed))
    # mehrere Memberships → kein Tenant-Filter angeben heisst "alle eigenen"
    # — wir filtern dafuer post-hoc. list_traces hat keinen Multi-Tenant-Filter
    # in V1; wir fragen die Liste ohne Filter ab und sieben hier.
    return None


@app.get("/api/debug/traces")
def debug_list_traces(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tenant_id: str | None = Query(None),
    status: str | None = Query(None),
    intent: str | None = Query(None),
    min_duration: int | None = Query(None, ge=0),
    max_duration: int | None = Query(None, ge=0),
    debug=Depends(require_debug_user),
) -> dict:
    """Plan 06 Tab 2 — Trace-Liste mit Filtern, Auth-gefiltert pro Tenant."""
    effective_tenant = _tenant_scope_filter(debug, tenant_id)
    rows = list_traces(
        limit=limit, offset=offset,
        tenant_id=effective_tenant, status=status,
    )
    if debug.platform_role != "admin" and effective_tenant is None:
        allowed = set(debug.memberships)
        rows = [r for r in rows if r.get("tenant_id") in allowed]
    if intent:
        rows = [r for r in rows if r.get("intent") == intent]
    if min_duration is not None:
        rows = [r for r in rows if int(r.get("duration_ms") or 0) >= min_duration]
    if max_duration is not None:
        rows = [r for r in rows if int(r.get("duration_ms") or 0) <= max_duration]
    return {"traces": rows, "limit": limit, "offset": offset, "count": len(rows)}


@app.get("/api/debug/traces/{trace_uid}")
def debug_get_trace(
    trace_uid: str, debug=Depends(require_debug_user),
) -> dict:
    payload = get_trace_with_events(trace_uid)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_uid} nicht gefunden")
    if debug.platform_role != "admin":
        tenant = payload.get("trace", {}).get("tenant_id", "")
        if tenant not in set(debug.memberships):
            raise HTTPException(status_code=403, detail="Trace nicht in deinen Tenants")
    return payload


@app.get("/api/debug/mcps")
async def debug_list_mcps(debug=Depends(require_debug_user)) -> dict:
    """Plan 06 Tab 3 — alle MCPs + Sub-Agents via lib/agent.list_all_capabilities."""
    from lib.agent import MCP_ENDPOINTS, list_all_capabilities  # lazy import

    caps = await list_all_capabilities()
    items: list[dict] = []
    for name, url in MCP_ENDPOINTS:
        manifest = caps.get(name, {})
        items.append({
            "name": name,
            "url": url,
            "status": manifest.get("status", "unknown"),
            "kind": manifest.get("kind", "unknown"),
            "description": manifest.get("description", ""),
            "version": manifest.get("version", ""),
            "tools": manifest.get("tools", []),
            "error": manifest.get("error", ""),
        })
    return {"mcps": items, "count": len(items)}


@app.get("/api/debug/mcps/{name}")
async def debug_get_mcp(
    name: str, debug=Depends(require_debug_user),
) -> dict:
    from lib.agent import MCP_ENDPOINTS, list_all_capabilities  # lazy import

    caps = await list_all_capabilities()
    if name not in caps:
        raise HTTPException(status_code=404, detail=f"MCP {name!r} unbekannt")
    url = ""
    for n, u in MCP_ENDPOINTS:
        if n == name:
            url = u
            break
    manifest = caps[name]
    return {
        "name": name,
        "url": url,
        "status": manifest.get("status", "unknown"),
        "kind": manifest.get("kind", "unknown"),
        "description": manifest.get("description", ""),
        "version": manifest.get("version", ""),
        "tools": manifest.get("tools", []),
        "error": manifest.get("error", ""),
    }


@app.get("/api/debug/mcps/{name}/calls")
def debug_mcp_calls(
    name: str,
    limit: int = Query(50, ge=1, le=200),
    debug=Depends(require_debug_user),
) -> dict:
    """Letzte Tool-/Sub-Agent-Calls eines MCP aus logging_db.event."""
    from lib.entities.logging import Event as EventRow
    from sqlalchemy import desc, or_, select

    allowed_tenants = (
        None if debug.platform_role == "admin" else set(debug.memberships)
    )
    rows_out: list[dict] = []
    with session_for_logging() as s:
        stmt = (
            select(EventRow)
            .where(
                or_(
                    EventRow.event_type == "tool_call_started",
                    EventRow.event_type == "sub_agent_started",
                )
            )
            .order_by(desc(EventRow.timestamp))
            .limit(limit * 4)  # post-filter Buffer
        )
        events = s.execute(stmt).scalars().all()
        for e in events:
            data = e.data or {}
            tool_name = data.get("tool_name") or data.get("role") or ""
            # Heuristik: ein Call gehoert zu name, wenn name == tool_name ODER
            # tool_name dem Manifest des MCP zugeordnet ist. In V1 reicht der
            # Namens-Match — Manifest-Match folgt in V2.
            matches = tool_name == name or tool_name.startswith(f"{name}_")
            if not matches:
                continue
            row_tenant = ""
            # tenant_id nur via trace_uid bestimmbar — V1: leer lassen.
            if allowed_tenants is not None and row_tenant and row_tenant not in allowed_tenants:
                continue
            rows_out.append({
                "sequence": e.sequence,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "event_type": e.event_type,
                "trace_uid": e.trace_uid,
                "data": data,
            })
            if len(rows_out) >= limit:
                break
    return {"calls": rows_out, "count": len(rows_out)}


@app.get("/api/debug/stream")
async def debug_stream(debug=Depends(require_debug_user)):
    """Plan 06 Tab 1 — Live-Strom aller Events.

    V1-Stub: liefert einen offen-haltenden SSE-Stream + Heartbeat alle 15s.
    Der globale EventBroker-Multiplexer (Sub-Iteration 2) folgt — sobald
    er da ist, werden hier alle persistierten Events pro Tenant-Scope
    durchgepusht.
    """
    from starlette.responses import StreamingResponse  # lazy
    import asyncio
    import json as _json

    allowed = (
        None if debug.platform_role == "admin" else set(debug.memberships)
    )

    async def gen():
        yield (
            "event: ready\n"
            f"data: {_json.dumps({'scope': 'all' if allowed is None else sorted(allowed)})}\n\n"
        )
        try:
            while True:
                await asyncio.sleep(15)
                yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(gen(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────────────────────
# Auth-Routen (Login / Logout)
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/{slug}/login")
def login_page_legacy(slug: str) -> Response:
    # Slug-spezifischer Login ist abgeschafft — Auflösung passiert global
    # ueber Username/Email + TenantMembership. Slug wird ignoriert.
    return RedirectResponse(url="/login", status_code=308)


@app.post("/{slug}/login")
async def login_submit_legacy(slug: str) -> Response:
    return RedirectResponse(url="/login", status_code=307)


@app.get("/{slug}/logout")
def logout(slug: str) -> Response:
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Chat-UI (HTML)
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/{slug}/", response_class=HTMLResponse)
def chat_ui(slug: str, request: Request) -> Response:
    # require_user_redirect waere sauberer, aber Depends koennen wir hier
    # nicht haendisch einsetzen — wir machen den Check inline.
    from lib.auth import _ctx_from_request  # noqa: PLC0415

    ctx = _ctx_from_request(request, slug)
    if ctx is None:
        return RedirectResponse(url="/login", status_code=303)
    set_tenant(slug)
    return HTMLResponse(render_chat(slug, ctx.username, ctx.display_name))


# ─────────────────────────────────────────────────────────────────────────────
# Chats (Liste / Detail / Neu / Klonen / Share)
# ─────────────────────────────────────────────────────────────────────────────


class NewChatRequest(BaseModel):
    title: str = ""
    target_cls: str = ""
    target_id: int = 0


class ShareRequest(BaseModel):
    shared: bool


class UpdateChatRequest(BaseModel):
    title: str | None = None


@app.get("/{slug}/chats")
def list_chats(slug: str, ctx: UserContext = Depends(require_user)) -> dict:
    with session_for_tenant(slug) as s:
        rows = list(
            s.scalars(
                select(AiChat)
                .where(
                    AiChat.is_deleted.is_(False),
                    AiChat.parent_chat_id == 0,
                    or_(AiChat.user_id == ctx.user_id, AiChat.is_shared.is_(True)),
                )
                .order_by(desc(AiChat.updated_at))
            )
        )
        return {
            "chats": [
                {
                    "id": c.id,
                    "title": c.title or f"Chat #{c.id}",
                    "agent_name": c.agent_name,
                    "model": c.model,
                    "is_shared": bool(c.is_shared),
                    "is_mine": c.user_id == ctx.user_id,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in rows
            ]
        }


@app.post("/{slug}/chats")
def create_chat(slug: str, req: NewChatRequest, ctx: UserContext = Depends(require_user)) -> dict:
    title = (req.title or "").strip()
    if not title:
        title = f"Neuer Chat {time.strftime('%Y-%m-%d %H:%M')}"
    target_cls = (req.target_cls or "").strip()
    target_id = req.target_id or 0
    try:
        validate_target(target_cls, target_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    with session_for_tenant(slug) as s:
        chat = AiChat(
            title=title,
            user_id=ctx.user_id,
            agent_name="manager",
            model="gpt-5.5",
            target_cls=target_cls,
            target_id=target_id,
        )
        s.add(chat)
        s.commit()
        s.refresh(chat)
        return {"id": chat.id, "title": chat.title}


def _load_chat_or_403(slug: str, chat_id: int, ctx: UserContext) -> AiChat:
    with session_for_tenant(slug) as s:
        chat = s.get(AiChat, chat_id)
        if chat is None or chat.is_deleted:
            raise HTTPException(status_code=404, detail=f"Chat {chat_id} nicht gefunden")
        if not (chat.is_shared or chat.user_id == ctx.user_id):
            raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Chat")
        return chat


@app.get("/{slug}/chats/{chat_id}")
def get_chat(slug: str, chat_id: int, ctx: UserContext = Depends(require_user)) -> dict:
    chat = _load_chat_or_403(slug, chat_id, ctx)
    with session_for_tenant(slug) as s:
        messages = list(
            s.scalars(
                select(AiMessage)
                .where(AiMessage.chat_id == chat_id, AiMessage.is_deleted.is_(False))
                .order_by(AiMessage.id)
            )
        )
        tool_calls = list(
            s.scalars(
                select(AiToolCall)
                .where(
                    AiToolCall.message_id.in_([m.id for m in messages]) if messages else False,
                    AiToolCall.is_deleted.is_(False),
                )
                .order_by(AiToolCall.id)
            )
        ) if messages else []

    tc_by_msg: dict[int, list] = {}
    for tc in tool_calls:
        tc_by_msg.setdefault(tc.message_id, []).append({
            "tool_call_id": tc.tool_call_id,
            "tool_name": tc.tool_name,
            "arguments_json": tc.arguments_json,
            "result_text": tc.result_text,
            "status": tc.status,
            "duration_ms": tc.duration_ms,
        })

    return {
        "id": chat.id,
        "title": chat.title,
        "user_id": chat.user_id,
        "is_shared": bool(chat.is_shared),
        "is_mine": chat.user_id == ctx.user_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "tool_call_id": m.tool_call_id,
                "tool_name": m.tool_name,
                "tool_calls": tc_by_msg.get(m.id, []),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@app.patch("/{slug}/chats/{chat_id}")
def update_chat(
    slug: str,
    chat_id: int,
    req: UpdateChatRequest,
    ctx: UserContext = Depends(require_user),
) -> dict:
    """Partial update — derzeit nur title. Nur der Besitzer darf umbenennen."""
    with session_for_tenant(slug) as s:
        chat = s.get(AiChat, chat_id)
        if chat is None or chat.is_deleted:
            raise HTTPException(status_code=404, detail="Chat nicht gefunden")
        if chat.user_id != ctx.user_id:
            raise HTTPException(status_code=403, detail="Nur der Besitzer darf umbenennen")
        if req.title is not None:
            new_title = req.title.strip()
            if not new_title:
                raise HTTPException(status_code=422, detail="Titel darf nicht leer sein")
            chat.title = new_title[:200]
        s.commit()
        return {"id": chat.id, "title": chat.title}


@app.post("/{slug}/chats/{chat_id}/share")
def share_chat(
    slug: str,
    chat_id: int,
    req: ShareRequest,
    ctx: UserContext = Depends(require_user),
) -> dict:
    with session_for_tenant(slug) as s:
        chat = s.get(AiChat, chat_id)
        if chat is None or chat.is_deleted:
            raise HTTPException(status_code=404, detail="Chat nicht gefunden")
        if chat.user_id != ctx.user_id:
            raise HTTPException(status_code=403, detail="Nur der Besitzer darf teilen")
        chat.is_shared = bool(req.shared)
        s.commit()
        return {"id": chat.id, "is_shared": bool(chat.is_shared)}


@app.post("/{slug}/chats/{chat_id}/clone")
def clone_chat_endpoint(
    slug: str,
    chat_id: int,
    ctx: UserContext = Depends(require_user),
) -> dict:
    _load_chat_or_403(slug, chat_id, ctx)
    try:
        new_id = clone_chat(chat_id, slug, ctx.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"id": new_id, "source_id": chat_id}


@app.delete("/{slug}/chats/{chat_id}")
def delete_chat(
    slug: str,
    chat_id: int,
    ctx: UserContext = Depends(require_user),
) -> dict:
    """Soft-Delete: setzt is_deleted=True (Chat verschwindet aus der Liste, bleibt
    in der DB als Archiv). Nur der Besitzer darf loeschen.
    """
    with session_for_tenant(slug) as s:
        chat = s.get(AiChat, chat_id)
        if chat is None or chat.is_deleted:
            raise HTTPException(status_code=404, detail="Chat nicht gefunden")
        if chat.user_id != ctx.user_id:
            raise HTTPException(status_code=403, detail="Nur der Besitzer darf loeschen")
        chat.is_deleted = True
        s.commit()
        return {"id": chat_id, "is_deleted": True}


# ─────────────────────────────────────────────────────────────────────────────
# Chat-Messaging (SSE-Stream)
# ─────────────────────────────────────────────────────────────────────────────


class ChatMessageRequest(BaseModel):
    message: str


def _sse_format(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _run_chat_streaming(slug: str, chat_id: int, user_id: int, user_message: str):
    trace_uid = new_trace_uid()
    set_trace_uid(trace_uid)
    started_at = now_utc()
    started_mono = time.monotonic()
    emitter = EventEmitter(trace_uid, slug, user_message)

    yield _sse_format("trace", {
        "trace_uid": trace_uid,
        "tenant_id": slug,
        "chat_id": chat_id,
        "started_at": started_at.isoformat(),
    })

    await asyncio.to_thread(create_trace, trace_uid, slug, user_message, started_at)

    agent_task = asyncio.create_task(
        manager_chat(
            chat_id=chat_id,
            user_message=user_message,
            tenant_slug=slug,
            user_id=user_id,
            emitter=emitter,
        )
    )

    async def _close_when_done() -> None:
        try:
            await agent_task
        finally:
            emitter.close()

    closer_task = asyncio.create_task(_close_when_done())

    error_message = ""
    status = "ok"
    tool_call_count = 0

    try:
        async for ev in emitter.stream():
            if ev.event_type not in VOLATILE_EVENT_TYPES:
                asyncio.create_task(asyncio.to_thread(persist_event, ev))
            if ev.event_type == "tool_call_started":
                tool_call_count += 1
            yield _sse_format("event", ev.to_jsonable())
    except Exception as exc:
        status = "error"
        error_message = repr(exc)
        log.exception("sse_stream_failed trace=%s", trace_uid)

    await closer_task

    result: dict | None = None
    try:
        result = agent_task.result()
    except Exception as exc:
        status = "error"
        error_message = error_message or repr(exc)
        log.exception("agent_failed trace=%s", trace_uid)

    duration_ms = int((time.monotonic() - started_mono) * 1000)
    response_text = (result or {}).get("response", "") if result else ""
    intent = (result or {}).get("intent", "") if result else ""
    tool_calls = (result or {}).get("tool_calls", []) if result else []

    finished_at = now_utc()
    await asyncio.to_thread(
        finalize_trace,
        trace_uid,
        response=response_text,
        intent=intent,
        status=status,
        finished_at=finished_at,
        duration_ms=duration_ms,
        event_count=emitter.event_count,
        tool_call_count=tool_call_count,
        error_message=error_message,
    )

    yield _sse_format(
        "done",
        {
            "trace_uid": trace_uid,
            "status": status,
            "response": response_text,
            "intent": intent,
            "tool_calls": tool_calls,
            "duration_ms": duration_ms,
            "error_message": error_message,
            "chat_id": chat_id,
        },
    )


@app.post("/{slug}/chats/{chat_id}/messages")
async def post_message(
    slug: str,
    chat_id: int,
    req: ChatMessageRequest,
    ctx: UserContext = Depends(require_user),
):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=422, detail="message darf nicht leer sein")
    _load_chat_or_403(slug, chat_id, ctx)
    log.info(
        "POST /%s/chats/%d/messages user_id=%d msg=%r",
        slug, chat_id, ctx.user_id, req.message,
    )
    return StreamingResponse(
        _run_chat_streaming(slug, chat_id, ctx.user_id, req.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Mappe (Artifacts pro Chat)
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/{slug}/chats/{chat_id}/artifacts")
def chat_artifacts(slug: str, chat_id: int, ctx: UserContext = Depends(require_user)) -> dict:
    _load_chat_or_403(slug, chat_id, ctx)
    with session_for_tenant(slug) as s:
        links = list(
            s.scalars(
                select(ChatArtifact)
                .where(
                    ChatArtifact.chat_id == chat_id,
                    ChatArtifact.is_deleted.is_(False),
                )
                .order_by(ChatArtifact.id)
            )
        )

        attachment_links = [l for l in links if l.artifact_cls == "core.attachment"]
        document_links = [l for l in links if l.artifact_cls == "core.document"]
        crm_links = [l for l in links if l.artifact_cls.startswith("crm.")]

        files: list[dict] = []
        if attachment_links:
            ids = [l.artifact_id for l in attachment_links]
            atts = {a.id: a for a in s.scalars(select(Attachment).where(Attachment.id.in_(ids)))}
            for l in attachment_links:
                a = atts.get(l.artifact_id)
                if a is None:
                    continue
                files.append({
                    "id": a.id,
                    "filename": a.filename,
                    "mime": a.mime,
                    "size_bytes": a.size_bytes,
                    "source": a.source,
                    "minio_key": a.minio_key,
                    "relation": l.relation,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                })

        crm_entities = [
            {
                "artifact_cls": l.artifact_cls,
                "artifact_id": l.artifact_id,
                "relation": l.relation,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in crm_links
        ]

        documents: list[dict] = []
        if document_links:
            ids = [l.artifact_id for l in document_links]
            docs = {d.id: d for d in s.scalars(select(Document).where(Document.id.in_(ids)))}
            for l in document_links:
                d = docs.get(l.artifact_id)
                if d is None or d.is_deleted:
                    continue
                documents.append({
                    "id": d.id,
                    "title": d.title or f"Dokument #{d.id}",
                    "version": d.version,
                    "author_display_name": d.author_display_name,
                    "relation": l.relation,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                })

        tasks = list(s.scalars(
            select(Task).where(
                Task.target_cls == "ai.chat",
                Task.target_id == chat_id,
                Task.is_deleted.is_(False),
            ).order_by(desc(Task.created_at))
        ))
        notes = list(s.scalars(
            select(Note).where(
                Note.target_cls == "ai.chat",
                Note.target_id == chat_id,
                Note.is_deleted.is_(False),
            ).order_by(desc(Note.created_at))
        ))
        comments = list(s.scalars(
            select(Comment).where(
                Comment.target_cls == "ai.chat",
                Comment.target_id == chat_id,
                Comment.is_deleted.is_(False),
            ).order_by(desc(Comment.created_at))
        ))

        messages = list(s.scalars(
            select(AiMessage)
            .where(AiMessage.chat_id == chat_id, AiMessage.is_deleted.is_(False))
        ))
        tool_calls = list(s.scalars(
            select(AiToolCall)
            .where(
                AiToolCall.message_id.in_([m.id for m in messages]) if messages else False,
                AiToolCall.is_deleted.is_(False),
            )
            .order_by(AiToolCall.id)
        )) if messages else []

        return {
            "files": files,
            "documents": documents,
            "crm_entities": crm_entities,
            "tasks_notes_comments": {
                "tasks": [{"id": t.id, "title": t.title, "status": t.status} for t in tasks],
                "notes": [{"id": n.id, "title": n.title, "body": n.body} for n in notes],
                "comments": [{"id": c.id, "body": c.body} for c in comments],
            },
            "tool_calls": [
                {
                    "id": tc.id,
                    "tool_name": tc.tool_name,
                    "arguments_json": tc.arguments_json,
                    "result_text": tc.result_text,
                    "status": tc.status,
                    "duration_ms": tc.duration_ms,
                    "created_at": tc.created_at.isoformat() if tc.created_at else None,
                }
                for tc in tool_calls
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Documents (CRUD)
# ─────────────────────────────────────────────────────────────────────────────


class DocumentCreateRequest(BaseModel):
    title: str = ""
    content: str = ""
    target_cls: str = ""
    target_id: int = 0


class DocumentUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    target_cls: str | None = None
    target_id: int | None = None


def _document_to_dict(doc: Document) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "format": doc.format,
        "author_user_id": doc.author_user_id,
        "author_display_name": doc.author_display_name,
        "target_cls": doc.target_cls,
        "target_id": doc.target_id,
        "version": doc.version,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def _compute_doc_content_hash(title: str, content: str) -> str:
    # SHA256 ueber title + NUL + content — billiger Dedupe-Check
    payload = (title or "") + "\0" + (content or "")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _document_version_to_dict(v: DocumentVersion, include_content: bool = True) -> dict:
    out = {
        "id": v.id,
        "document_id": v.document_id,
        "version": v.version,
        "title": v.title,
        "format": v.format,
        "author_user_id": v.author_user_id,
        "author_display_name": v.author_display_name,
        "content_hash": v.content_hash,
        "content_length": len(v.content or ""),
        "change_summary": v.change_summary,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }
    if include_content:
        out["content"] = v.content
    return out


@app.get("/{slug}/documents")
def list_documents(
    slug: str,
    ctx: UserContext = Depends(require_user),
    target_cls: str = Query(""),
    target_id: int = Query(0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        stmt = (
            select(Document)
            .where(Document.is_deleted.is_(False))
            .order_by(desc(Document.updated_at))
            .limit(limit)
        )
        if target_cls:
            stmt = stmt.where(Document.target_cls == target_cls)
        if target_id:
            stmt = stmt.where(Document.target_id == target_id)
        rows = list(s.scalars(stmt))
        return {
            "documents": [
                {
                    "id": d.id,
                    "title": d.title or f"Dokument #{d.id}",
                    "author_user_id": d.author_user_id,
                    "author_display_name": d.author_display_name,
                    "target_cls": d.target_cls,
                    "target_id": d.target_id,
                    "version": d.version,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                }
                for d in rows
            ]
        }


@app.post("/{slug}/documents")
def create_document(
    slug: str,
    req: DocumentCreateRequest,
    ctx: UserContext = Depends(require_user),
) -> dict:
    set_tenant(slug)
    title = (req.title or "").strip() or f"Neues Dokument {time.strftime('%Y-%m-%d %H:%M')}"
    with session_for_tenant(slug) as s:
        doc = Document(
            title=title,
            content=req.content or "",
            author_user_id=ctx.user_id,
            author_display_name=ctx.display_name or ctx.username or "",
            target_cls=(req.target_cls or "").strip(),
            target_id=int(req.target_id or 0),
            version=1,
        )
        s.add(doc)
        s.commit()
        s.refresh(doc)
        log.info(
            "POST /%s/documents id=%d title=%r user_id=%d",
            slug, doc.id, doc.title, ctx.user_id,
        )
        return _document_to_dict(doc)


@app.get("/{slug}/documents/{doc_id}")
def get_document(
    slug: str,
    doc_id: int,
    ctx: UserContext = Depends(require_user),
) -> dict:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        doc = s.get(Document, doc_id)
        if doc is None or doc.is_deleted:
            raise HTTPException(status_code=404, detail=f"Dokument {doc_id} nicht gefunden")
        return _document_to_dict(doc)


@app.put("/{slug}/documents/{doc_id}")
def update_document(
    slug: str,
    doc_id: int,
    req: DocumentUpdateRequest,
    ctx: UserContext = Depends(require_user),
) -> dict:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        doc = s.get(Document, doc_id)
        if doc is None or doc.is_deleted:
            raise HTTPException(status_code=404, detail=f"Dokument {doc_id} nicht gefunden")
        # Diff vorab bestimmen — Snapshot nur bei echter Aenderung
        new_title = doc.title if req.title is None else req.title.strip()
        new_content = doc.content if req.content is None else req.content
        new_target_cls = doc.target_cls if req.target_cls is None else req.target_cls
        new_target_id = doc.target_id if req.target_id is None else int(req.target_id)
        changed = (
            new_title != doc.title
            or new_content != doc.content
            or new_target_cls != doc.target_cls
            or new_target_id != doc.target_id
        )
        if changed:
            # Snapshot der ALTEN Werte schreiben — author = Trigger-User
            snapshot = DocumentVersion(
                document_id=doc.id,
                version=doc.version,
                title=doc.title,
                content=doc.content,
                format=doc.format,
                author_user_id=ctx.user_id,
                author_display_name=ctx.display_name or ctx.username or "",
                content_hash=_compute_doc_content_hash(doc.title, doc.content),
                change_summary="",
            )
            s.add(snapshot)
            doc.title = new_title
            doc.content = new_content
            doc.target_cls = new_target_cls
            doc.target_id = new_target_id
            doc.version += 1
            doc.author_user_id = ctx.user_id
            doc.author_display_name = ctx.display_name or ctx.username or ""
        s.commit()
        s.refresh(doc)
        log.info(
            "PUT /%s/documents/%d version=%d changed=%s",
            slug, doc.id, doc.version, changed,
        )
        return _document_to_dict(doc)


@app.delete("/{slug}/documents/{doc_id}")
def delete_document(
    slug: str,
    doc_id: int,
    ctx: UserContext = Depends(require_user),
) -> dict:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        doc = s.get(Document, doc_id)
        if doc is None or doc.is_deleted:
            raise HTTPException(status_code=404, detail=f"Dokument {doc_id} nicht gefunden")
        doc.is_deleted = True
        s.commit()
        log.info("DELETE /%s/documents/%d", slug, doc_id)
        return {"id": doc.id, "is_deleted": True}


@app.get("/{slug}/documents/{doc_id}/versions")
def list_document_versions(
    slug: str,
    doc_id: int,
    ctx: UserContext = Depends(require_user),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        doc = s.get(Document, doc_id)
        if doc is None or doc.is_deleted:
            raise HTTPException(status_code=404, detail=f"Dokument {doc_id} nicht gefunden")
        rows = list(
            s.scalars(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == doc_id)
                .where(DocumentVersion.is_deleted.is_(False))
                .order_by(desc(DocumentVersion.version))
                .limit(limit)
            )
        )
        return {
            "versions": [
                {
                    "id": v.id,
                    "version": v.version,
                    "title": v.title,
                    "author_user_id": v.author_user_id,
                    "author_display_name": v.author_display_name,
                    "content_hash": v.content_hash,
                    "content_length": len(v.content or ""),
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in rows
            ]
        }


@app.get("/{slug}/documents/{doc_id}/versions/{version_id}")
def get_document_version(
    slug: str,
    doc_id: int,
    version_id: int,
    ctx: UserContext = Depends(require_user),
) -> dict:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        v = s.get(DocumentVersion, version_id)
        if v is None or v.is_deleted or v.document_id != doc_id:
            raise HTTPException(
                status_code=404,
                detail=f"DocumentVersion {version_id} nicht gefunden",
            )
        return _document_version_to_dict(v, include_content=True)


@app.post("/{slug}/documents/{doc_id}/versions/{version_id}/restore")
def restore_document_version(
    slug: str,
    doc_id: int,
    version_id: int,
    ctx: UserContext = Depends(require_user),
) -> dict:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        doc = s.get(Document, doc_id)
        if doc is None or doc.is_deleted:
            raise HTTPException(status_code=404, detail=f"Dokument {doc_id} nicht gefunden")
        v = s.get(DocumentVersion, version_id)
        if v is None or v.is_deleted or v.document_id != doc_id:
            raise HTTPException(
                status_code=404,
                detail=f"DocumentVersion {version_id} nicht gefunden",
            )
        # Snapshot des aktuellen Stands vor Restore
        snapshot = DocumentVersion(
            document_id=doc.id,
            version=doc.version,
            title=doc.title,
            content=doc.content,
            format=doc.format,
            author_user_id=ctx.user_id,
            author_display_name=ctx.display_name or ctx.username or "",
            content_hash=_compute_doc_content_hash(doc.title, doc.content),
            change_summary=f"Wiederhergestellt von v{version_id}",
        )
        s.add(snapshot)
        doc.title = v.title
        doc.content = v.content
        doc.format = v.format
        doc.version += 1
        doc.author_user_id = ctx.user_id
        doc.author_display_name = ctx.display_name or ctx.username or ""
        s.commit()
        s.refresh(doc)
        log.info(
            "POST /%s/documents/%d/versions/%d/restore new_version=%d",
            slug, doc.id, version_id, doc.version,
        )
        return _document_to_dict(doc)


# Diff zwischen DocumentVersionen --------------------------------------------


def _load_doc_state(
    s, doc_id: int, version_or_current
) -> tuple[str, str, str, int, int]:
    """Liefert (title, content, label, ref_id, version) fuer Diff-Endpunkt.

    `version_or_current` ist entweder "current" (-> aktueller Document-Stand)
    oder eine DocumentVersion-ID (int oder int-castbarer String).
    """
    if version_or_current == "current" or version_or_current is None:
        doc = s.get(Document, doc_id)
        if doc is None or doc.is_deleted:
            raise HTTPException(status_code=404, detail=f"Dokument {doc_id} nicht gefunden")
        return (doc.title or "", doc.content or "", "aktuell", doc.id, doc.version)
    try:
        vid = int(version_or_current)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"ungueltige Version: {version_or_current!r}")
    v = s.get(DocumentVersion, vid)
    if v is None or v.is_deleted or v.document_id != doc_id:
        raise HTTPException(status_code=404, detail=f"DocumentVersion {vid} nicht gefunden")
    ts = v.created_at.strftime("%Y-%m-%d") if v.created_at else "?"
    return (v.title or "", v.content or "", f"v{v.version} vom {ts}", v.id, v.version)


def _build_doc_diff(
    from_title: str, from_content: str, from_label: str, from_id: int, from_version: int,
    to_title: str, to_content: str, to_label: str, to_id: int, to_version: int,
) -> dict:
    # Title-Diff: simpel - entweder equal oder replace
    if from_title == to_title:
        title_diff = [{"kind": "equal", "from": from_title, "to": to_title}]
    else:
        title_diff = [{"kind": "replace", "from": from_title, "to": to_title}]

    # Content-Diff: zeilenweise mit SequenceMatcher
    from_lines = from_content.split("\n")
    to_lines = to_content.split("\n")
    matcher = difflib.SequenceMatcher(a=from_lines, b=to_lines, autojunk=False)
    content_diff = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        content_diff.append({
            "kind": tag,
            "old_start": i1,
            "old_end": i2,
            "new_start": j1,
            "new_end": j2,
            "old_text": "\n".join(from_lines[i1:i2]),
            "new_text": "\n".join(to_lines[j1:j2]),
        })

    unified = "\n".join(
        difflib.unified_diff(
            from_lines, to_lines,
            fromfile=from_label, tofile=to_label,
            lineterm="",
        )
    )

    return {
        "from": {"id": from_id, "version": from_version, "title": from_title, "label": from_label},
        "to":   {"id": to_id,   "version": to_version,   "title": to_title,   "label": to_label},
        "title_diff": title_diff,
        "content_diff": content_diff,
        "unified": unified,
    }


@app.get("/{slug}/documents/{doc_id}/versions/{version_id}/diff")
def diff_document_version(
    slug: str,
    doc_id: int,
    version_id: int,
    ctx: UserContext = Depends(require_user),
    against: str = Query("current"),
) -> dict:
    set_tenant(slug)
    with session_for_tenant(slug) as s:
        doc = s.get(Document, doc_id)
        if doc is None or doc.is_deleted:
            raise HTTPException(status_code=404, detail=f"Dokument {doc_id} nicht gefunden")
        from_state = _load_doc_state(s, doc_id, version_id)
        to_state = _load_doc_state(s, doc_id, against)
        return _build_doc_diff(*from_state, *to_state)


# ─────────────────────────────────────────────────────────────────────────────
# Aktionen (Action-Suggestions + Run)
# ─────────────────────────────────────────────────────────────────────────────


class RunActionRequest(BaseModel):
    action_key: str
    cls: str = ""
    id: int = 0
    chat_id: int = 0


def _serialize_action(a) -> dict:
    return {
        "key": a.key,
        "label": a.label,
        "description": a.description,
        "icon": a.icon,
        "category": a.category,
        "resource_types": a.resource_types,
        "execution_kind": a.execution.kind,
        "needs_confirmation": a.needs_confirmation,
        "is_destructive": a.is_destructive,
        "refine_score": a.refine_score,
        "refine_reason": a.refine_reason,
    }


def _load_polymorphic_resource(session, alias: str, entity_id: int):
    from lib.polymorphic import resolve_target_cls

    cls = resolve_target_cls(alias)
    if cls is None:
        return None
    obj = session.get(cls, entity_id)
    if obj is None or getattr(obj, "is_deleted", False):
        return None
    return obj


@app.get("/{slug}/actions")
def list_actions_endpoint(
    slug: str,
    ctx: UserContext = Depends(require_user),
    cls: str = Query(""),
    id: int = Query(0),
    refine: bool = Query(False),
    limit: int = Query(8, ge=1, le=30),
) -> dict:
    """Aktions-Vorschlaege fuer eine Resource oder global.

    cls leer  -> globale Aktionen
    cls + id  -> statische Aktionen fuer den Resource-Type, optional via LLM
                 kontextspezifisch ge-ranked (refine=true).
    """
    from lib.actions import list_actions_for_resource, list_global_actions
    from lib.actions_refine import refine_actions

    set_tenant(slug)
    resource_type = cls.strip()
    if not resource_type:
        candidates = list_global_actions()
        return {
            "resource": None,
            "actions": [_serialize_action(a) for a in candidates[:limit]],
        }

    candidates = list_actions_for_resource(resource_type)
    resource_meta: dict = {"cls": resource_type, "id": id}

    if id and refine and candidates:
        with session_for_tenant(slug) as s:
            obj = _load_polymorphic_resource(s, resource_type, id)
            if obj is None:
                raise HTTPException(status_code=404, detail=f"{resource_type} #{id} nicht gefunden")
            name = getattr(obj, "title", None) or getattr(obj, "name", None) or f"#{id}"
            short = ""
            if hasattr(obj, "get_resource_short"):
                try:
                    short = obj.get_resource_short() or ""
                except Exception:  # noqa: BLE001
                    short = ""
            resource_meta["name"] = name
            resource_meta["short"] = short
        candidates = refine_actions(
            resource_type=resource_type,
            resource_name=name,
            resource_short=short,
            candidates=candidates,
            top_n=limit,
        )
    elif id:
        with session_for_tenant(slug) as s:
            obj = _load_polymorphic_resource(s, resource_type, id)
            if obj is None:
                raise HTTPException(status_code=404, detail=f"{resource_type} #{id} nicht gefunden")
            resource_meta["name"] = (
                getattr(obj, "title", None) or getattr(obj, "name", None) or f"#{id}"
            )

    return {
        "resource": resource_meta,
        "actions": [_serialize_action(a) for a in candidates[:limit]],
    }


@app.post("/{slug}/actions/run")
async def run_action_endpoint(
    slug: str,
    req: RunActionRequest,
    ctx: UserContext = Depends(require_user),
) -> dict:
    """Fuehrt eine Aktion aus.

    chat_task -> erstellt (falls noetig) einen neuen AiChat, persistiert die
                 substituierte User-Message und liefert chat_id zurueck. Das
                 UI navigiert dann zum Chat und startet die SSE-Verbindung
                 ueber den bestehenden /chats/{id}/messages-Endpunkt.
    tool_call -> ruft direkt das MCP-Tool gegen crm_mcp auf und liefert das
                 Result.
    """
    from lib.actions import (
        build_resource_context,
        get_action,
        render_template,
        substitute_args,
    )

    action = get_action(req.action_key)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action {req.action_key!r} unbekannt")

    set_tenant(slug)

    # Resource-Context (optional)
    context: dict = {}
    resource_label = ""
    if req.cls and req.id:
        with session_for_tenant(slug) as s:
            obj = _load_polymorphic_resource(s, req.cls, req.id)
            if obj is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"{req.cls} #{req.id} nicht gefunden",
                )
            context = build_resource_context(obj, req.cls)
            resource_label = (
                getattr(obj, "title", None) or getattr(obj, "name", None) or f"#{req.id}"
            )

    if action.execution.kind == "chat_task":
        prompt = render_template(action.execution.prompt_template, context).strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Action-Prompt ist leer")
        with session_for_tenant(slug) as s:
            chat_id = req.chat_id
            if chat_id and chat_id > 0:
                chat = s.get(AiChat, chat_id)
                if chat is None or chat.is_deleted:
                    raise HTTPException(status_code=404, detail=f"Chat {chat_id} nicht gefunden")
                if not (chat.is_shared or chat.user_id == ctx.user_id):
                    raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Chat")
            else:
                title = f"{action.label}"
                if resource_label:
                    title = f"{action.label}: {resource_label}"
                chat = AiChat(
                    title=title,
                    user_id=ctx.user_id,
                    agent_name="manager",
                    model="gpt-5.5",
                )
                s.add(chat)
                s.flush()
                chat_id = chat.id
                if req.cls and req.id:
                    s.add(ChatArtifact(
                        chat_id=chat_id,
                        artifact_cls=req.cls,
                        artifact_id=req.id,
                        relation="linked",
                    ))
            s.commit()
            log.info(
                "POST /%s/actions/run action=%s cls=%s id=%d chat_id=%d kind=chat_task",
                slug, action.key, req.cls, req.id, chat_id,
            )
            return {
                "kind": "chat_task",
                "chat_id": chat_id,
                "prompt": prompt,
                "action": _serialize_action(action),
            }

    if action.execution.kind == "tool_call":
        tool_args = substitute_args(action.execution.args, context)
        for k, v in list(tool_args.items()):
            if isinstance(v, str) and v.isdigit():
                tool_args[k] = int(v)
        try:
            async with sse_client(url=MCP_CRM_URL) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    result = await session.call_tool(action.execution.tool_name, tool_args)
                    raw = " ".join(c.text for c in result.content if hasattr(c, "text"))
        except (ConnectionRefusedError, OSError) as exc:
            log.warning("crm_mcp_unreachable url=%s error=%s", MCP_CRM_URL, exc)
            raise HTTPException(status_code=503, detail="CRM-Server nicht erreichbar")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw}
        log.info(
            "POST /%s/actions/run action=%s tool=%s args=%s",
            slug, action.key, action.execution.tool_name, tool_args,
        )
        return {
            "kind": "tool_call",
            "tool": action.execution.tool_name,
            "args": tool_args,
            "result": data,
            "action": _serialize_action(action),
        }

    raise HTTPException(status_code=400, detail=f"Unbekannter execution kind: {action.execution.kind}")


# ─────────────────────────────────────────────────────────────────────────────
# Entity-Lookup (CRM-Detail per MCP)
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/{slug}/entity/{cls}/{entity_id}/changes")
def entity_changes(
    slug: str,
    cls: str,
    entity_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: UserContext = Depends(require_user),
) -> dict:
    """Plan 04 — Verlaufs-Tab des Entity-Overlays: append-only Audit-Eintraege."""
    set_tenant(slug)
    rows = list_entity_changes(
        tenant_id=slug, target_cls=cls, target_id=entity_id,
        limit=limit, offset=offset,
    )
    return {"changes": rows, "limit": limit, "offset": offset, "count": len(rows)}


@app.get("/{slug}/entity/{cls}/{entity_id}")
async def entity_get(
    slug: str,
    cls: str,
    entity_id: int,
    ctx: UserContext = Depends(require_user),
) -> dict:
    tool_name = ENTITY_TOOLS.get(cls)
    if not tool_name:
        raise HTTPException(status_code=404, detail=f"unbekannte Entität: {cls}")
    try:
        async with sse_client(url=MCP_CRM_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, {"id": int(entity_id)})
                raw = " ".join(c.text for c in result.content if hasattr(c, "text"))
    except (ConnectionRefusedError, OSError) as exc:
        log.warning("crm_mcp_unreachable url=%s error=%s", MCP_CRM_URL, exc)
        raise HTTPException(status_code=503, detail="CRM-Server nicht erreichbar")
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {"raw": raw}
    return {"cls": cls, "id": entity_id, "data": data}


# ─────────────────────────────────────────────────────────────────────────────
# Voice / Image Ingest
# ─────────────────────────────────────────────────────────────────────────────


def _ext_from(filename: str, mime: str, fallback: str) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower().strip()
        if ext and ext.isalnum() and len(ext) <= 8:
            return ext
    if mime and "/" in mime:
        sub = mime.split("/", 1)[1].split(";", 1)[0].strip().lower()
        if sub and sub.isalnum():
            return sub
    return fallback


def _persist_attachment(
    tenant_slug: str,
    chat_id: int,
    user_id: int,
    minio_key: str,
    mime: str,
    filename: str,
    size: int,
    sha256: str,
    source: str,
) -> int:
    with session_for_tenant(tenant_slug) as s:
        att = Attachment(
            minio_key=minio_key,
            mime=mime,
            filename=filename,
            size_bytes=size,
            sha256=sha256,
            source=source,
            uploader_user_id=user_id,
            target_cls="ai.chat" if chat_id > 0 else "",
            target_id=chat_id if chat_id > 0 else 0,
        )
        s.add(att)
        s.flush()
        attachment_id = att.id
        if chat_id > 0:
            s.add(ChatArtifact(
                chat_id=chat_id,
                artifact_cls="core.attachment",
                artifact_id=attachment_id,
                relation="uploaded",
            ))
        s.commit()
        return attachment_id


@app.post("/{slug}/ingest/voice")
async def ingest_voice(
    slug: str,
    file: UploadFile = File(...),
    chat_id: int = Query(0),
    ctx: UserContext = Depends(require_user),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="leere Audio-Datei")
    mime = file.content_type or "audio/webm"
    transcript = transcribe(data, mime=mime, language="de")

    bucket = ensure_bucket(bucket_for_tenant(slug))
    ext = _ext_from(file.filename or "", mime, "webm")
    key = build_object_key("voice", ext)
    meta = upload_bytes(bucket, key, data, mime)

    attachment_id = _persist_attachment(
        slug, chat_id, ctx.user_id, key, mime, file.filename or "",
        meta["size"], meta["sha256"], "voice",
    )

    log.info(
        "POST /%s/ingest/voice chat_id=%d bytes=%d transcript_len=%d",
        slug, chat_id, meta["size"], len(transcript.get("text", "")),
    )

    payload = {
        "attachment_id": attachment_id,
        "minio_key": key,
        "transcript": transcript.get("text", ""),
        "model": transcript.get("model"),
        "duration_seconds": transcript.get("duration_seconds"),
    }
    if "error" in transcript:
        payload["transcribe_error"] = transcript["error"]
    return payload


@app.post("/{slug}/ingest/image")
async def ingest_image(
    slug: str,
    file: UploadFile = File(...),
    chat_id: int = Query(0),
    ctx: UserContext = Depends(require_user),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="leere Bild-Datei")
    mime = file.content_type or "image/png"

    bucket = ensure_bucket(bucket_for_tenant(slug))
    ext = _ext_from(file.filename or "", mime, "png")
    key = build_object_key("image", ext)
    meta = upload_bytes(bucket, key, data, mime)

    attachment_id = _persist_attachment(
        slug, chat_id, ctx.user_id, key, mime, file.filename or "",
        meta["size"], meta["sha256"], "image",
    )

    url = presigned_get_url(bucket, key, ttl_seconds=3600)
    log.info(
        "POST /%s/ingest/image chat_id=%d bytes=%d mime=%s",
        slug, chat_id, meta["size"], mime,
    )
    return {
        "attachment_id": attachment_id,
        "minio_key": key,
        "mime": mime,
        "size_bytes": meta["size"],
        "presigned_url": url,
    }
