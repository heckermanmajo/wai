"""Persistenz-Helpers für Agent-Chats.

Aus dem Manager-Agent extrahiert, damit Sub-Agents (sales_support &
Folge-Agents) denselben Pfad benutzen, ohne Code zu duplizieren:

- ``load_history(chat_id, tenant_slug)`` — liest alle nicht-gelöschten
  AiMessages + AiToolCalls eines Chats und gibt sie als OpenAI-style
  Messages-Liste zurück.
- ``persist_exchange(chat_id, tenant_slug, user_message, new_messages)``
  schreibt eine vollständige Runde (User-Brief + Assistant-Replies +
  Tool-Calls + ggf. ChatArtifact) in die Tenant-DB.
- ``CRM_TOOL_ARTIFACT_MAP`` + ``extract_artifact()`` halten das CRM-Tool
  ↔ Artifact-Mapping zentral.

Sync-API (SQLAlchemy ohne async). Aufrufer aus async-Code wickeln in
``asyncio.to_thread`` ein.
"""
from __future__ import annotations

import json

from sqlalchemy import select

from lib.db import session_for_tenant
from lib.entities.tenant import AiMessage, AiToolCall, ChatArtifact


# Tool-Name → (artifact_cls, arg_field_for_id_or_None, relation)
# arg_field=None bedeutet: ID aus dem JSON-Result lesen (Feld "id").
CRM_TOOL_ARTIFACT_MAP: dict[str, tuple[str, str | None, str]] = {
    "contact_get": ("crm.contact", "id", "touched"),
    "contact_upsert": ("crm.contact", None, "created"),
    "account_get": ("crm.account", "id", "touched"),
    "account_upsert": ("crm.account", None, "created"),
    "lead_get": ("crm.lead", "id", "touched"),
    "lead_create": ("crm.lead", None, "created"),
    "lead_convert": ("crm.lead", "lead_id", "touched"),
    "deal_get": ("crm.deal", "id", "touched"),
    "deal_create": ("crm.deal", None, "created"),
    "deal_advance_stage": ("crm.deal", "deal_id", "touched"),
}


def load_history(chat_id: int, tenant_slug: str) -> list[dict]:
    """Laedt alle bisherigen Messages eines Chats als OpenAI-style dicts."""
    with session_for_tenant(tenant_slug) as s:
        rows = list(
            s.scalars(
                select(AiMessage)
                .where(AiMessage.chat_id == chat_id, AiMessage.is_deleted.is_(False))
                .order_by(AiMessage.id)
            )
        )
        tool_call_rows = list(
            s.scalars(
                select(AiToolCall)
                .where(
                    AiToolCall.message_id.in_([r.id for r in rows]) if rows else False,
                    AiToolCall.is_deleted.is_(False),
                )
                .order_by(AiToolCall.id)
            )
        ) if rows else []

    calls_by_msg: dict[int, list[AiToolCall]] = {}
    for tc in tool_call_rows:
        calls_by_msg.setdefault(tc.message_id, []).append(tc)

    history: list[dict] = []
    for m in rows:
        if m.role == "tool":
            history.append({
                "role": "tool",
                "tool_call_id": m.tool_call_id,
                "content": m.content,
            })
        elif m.role == "assistant":
            tcs = calls_by_msg.get(m.id, [])
            if tcs:
                history.append({
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": tc.tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tc.tool_name,
                                "arguments": tc.arguments_json or "{}",
                            },
                        }
                        for tc in tcs
                    ],
                })
            else:
                history.append({"role": "assistant", "content": m.content})
        else:
            history.append({"role": m.role, "content": m.content})
    return history


def extract_artifact(tool_name: str, args: dict, result_text: str) -> tuple[str, int, str] | None:
    """Findet (artifact_cls, artifact_id, relation), wenn der Tool-Call eine
    bekannte CRM-Entity berührt — sonst None."""
    spec = CRM_TOOL_ARTIFACT_MAP.get(tool_name)
    if spec is None:
        return None
    artifact_cls, arg_field, relation = spec
    artifact_id: int | None = None
    if arg_field is not None:
        raw = args.get(arg_field)
        if isinstance(raw, (int, str)) and str(raw).strip().isdigit():
            artifact_id = int(raw)
    if artifact_id is None and result_text:
        try:
            data = json.loads(result_text)
        except (json.JSONDecodeError, ValueError):
            data = None
        if isinstance(data, dict):
            cand = data.get("id")
            if isinstance(cand, int):
                artifact_id = cand
            elif isinstance(cand, str) and cand.isdigit():
                artifact_id = int(cand)
    if artifact_id is None or artifact_id <= 0:
        return None
    return (artifact_cls, artifact_id, relation)


def persist_exchange(
    chat_id: int,
    tenant_slug: str,
    user_message: str,
    new_messages: list[dict],
) -> None:
    """Schreibt User-Message + alle vom Agent erzeugten Messages + ToolCalls in die DB.

    new_messages: alle Eintraege ab der vom Agent erzeugten User-Message
    (system + history werden NICHT mit uebergeben — Caller schneidet ab).
    """
    with session_for_tenant(tenant_slug) as s:
        seen_artifact_keys: set[tuple[str, int]] = set()
        existing_artifacts = s.scalars(
            select(ChatArtifact).where(
                ChatArtifact.chat_id == chat_id,
                ChatArtifact.is_deleted.is_(False),
            )
        )
        for ea in existing_artifacts:
            seen_artifact_keys.add((ea.artifact_cls, ea.artifact_id))

        s.add(AiMessage(chat_id=chat_id, role="user", content=user_message))
        s.flush()

        assistant_msg_id: int | None = None
        pending_tool_calls: dict[str, AiToolCall] = {}

        for entry in new_messages:
            role = entry.get("role")
            if role == "user":
                continue  # bereits oben persistiert
            if role == "assistant":
                content = entry.get("content") or ""
                tcs = entry.get("tool_calls") or []
                am = AiMessage(chat_id=chat_id, role="assistant", content=content)
                s.add(am)
                s.flush()
                assistant_msg_id = am.id
                pending_tool_calls = {}
                for tc in tcs:
                    fn = tc.get("function") or {}
                    tc_row = AiToolCall(
                        message_id=assistant_msg_id,
                        tool_call_id=str(tc.get("id") or ""),
                        tool_name=str(fn.get("name") or ""),
                        arguments_json=str(fn.get("arguments") or "{}"),
                        result_text="",
                        status="pending",
                        duration_ms=0,
                    )
                    s.add(tc_row)
                    pending_tool_calls[tc_row.tool_call_id] = tc_row
                s.flush()
            elif role == "tool":
                tc_id = str(entry.get("tool_call_id") or "")
                content = entry.get("content") or ""
                tc_row = pending_tool_calls.get(tc_id)
                if tc_row is not None:
                    tc_row.result_text = content
                    tc_row.status = "ok"
                s.add(AiMessage(
                    chat_id=chat_id,
                    role="tool",
                    content=content,
                    tool_call_id=tc_id,
                    tool_name=tc_row.tool_name if tc_row else "",
                ))
                if tc_row is not None:
                    try:
                        args = json.loads(tc_row.arguments_json or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    found = extract_artifact(tc_row.tool_name, args, content)
                    if found is not None:
                        cls_, aid, rel = found
                        if (cls_, aid) not in seen_artifact_keys:
                            s.add(ChatArtifact(
                                chat_id=chat_id,
                                artifact_cls=cls_,
                                artifact_id=aid,
                                relation=rel,
                            ))
                            seen_artifact_keys.add((cls_, aid))

        s.commit()
