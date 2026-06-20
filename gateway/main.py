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
    GET  /<slug>/chats/{id}/artifacts → Mappen-Inhalt
    GET  /<slug>/entity/{cls}/{id} → CRM-Detail per MCP
    POST /<slug>/ingest/voice      → Audio + Attachment + ChatArtifact
    POST /<slug>/ingest/image      → Bild + Attachment + ChatArtifact
"""
import asyncio
import json
import os
import time
import traceback

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
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
    authenticate_global,
    create_pending_pick_token,
    create_session_token,
    list_dev_users,
    read_pending_pick_token,
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
from lib.events import EventEmitter, new_trace_uid, now_utc
from lib.logging import setup_logging, get_logger
from lib.storage import (
    bucket_for_tenant,
    build_object_key,
    ensure_bucket,
    presigned_get_url,
    upload_bytes,
)
from lib.polymorphic import validate_target
from lib.tenant_context import set_tenant, set_trace_uid
from lib.transcribe import transcribe
from agents.manager.agent import chat as manager_chat
from gateway.ui_chat import render_chat
from gateway.ui_login import render_login, render_tenant_picker
from gateway.ui_traces import TRACES_HTML
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

app = FastAPI(title="wai gateway", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/login", response_class=HTMLResponse)
def login_page_global(err: str = "", login: str = "") -> str:
    try:
        users = list_dev_users()
    except Exception as exc:  # noqa: BLE001 — Login darf bei DB-Fluff nicht crashen
        log.warning("list_dev_users failed: %s", exc)
        users = []
    return render_login(error=err, dev_users=users, prefill=login)


def _set_session_and_redirect(user_id: int, tenant_slug: str) -> Response:
    token = create_session_token(user_id, tenant_slug)
    resp = RedirectResponse(url=f"/{tenant_slug}/", status_code=303)
    resp.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return resp


@app.post("/login")
async def login_submit_global(
    login: str = Form(...),
    password: str = Form(...),
) -> Response:
    result = authenticate_global(login.strip(), password)
    if result is None:
        return RedirectResponse(url="/login?err=Login%20fehlgeschlagen", status_code=303)
    if not result.tenants:
        return RedirectResponse(
            url="/login?err=Keine%20aktiven%20Tenants%20fuer%20diesen%20Account",
            status_code=303,
        )
    if len(result.tenants) == 1:
        slug, _ = result.tenants[0]
        log.info("login.ok user=%s id=%d tenant=%s (auto)", result.username, result.user_id, slug)
        return _set_session_and_redirect(result.user_id, slug)
    log.info("login.picker user=%s id=%d tenants=%d", result.username, result.user_id, len(result.tenants))
    token = create_pending_pick_token(result.user_id)
    return HTMLResponse(render_tenant_picker(pending_token=token, tenants=result.tenants))


@app.post("/login/pick")
async def login_pick_tenant(
    token: str = Form(...),
    tenant_slug: str = Form(...),
) -> Response:
    from lib.auth import _load_user_context

    user_id = read_pending_pick_token(token)
    if user_id is None:
        return RedirectResponse(url="/login?err=Sitzung%20abgelaufen", status_code=303)
    ctx = _load_user_context(user_id, tenant_slug)
    if ctx is None:
        return RedirectResponse(url="/login?err=Ungueltiger%20Tenant", status_code=303)
    log.info("login.pick user=%s tenant=%s", ctx.username, tenant_slug)
    return _set_session_and_redirect(ctx.user_id, ctx.tenant_slug)


@app.get("/traces", response_class=HTMLResponse)
def traces_ui() -> str:
    return TRACES_HTML


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
# Entity-Lookup (CRM-Detail per MCP)
# ─────────────────────────────────────────────────────────────────────────────


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
