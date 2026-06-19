"""Klont einen AiChat innerhalb eines Tenants.

Klon-Semantik: "History + Verweise".
    - Neue AiChat-Zeile (title = "Kopie von ...", parent_chat_id = original.id,
      is_shared = False, user_id = aufrufender User).
    - AiMessage-Zeilen werden 1:1 dupliziert; alte->neue message_id wird gemerkt.
    - AiToolCall-Zeilen werden dupliziert, message_id ueber das Mapping
      umgehaengt.
    - ChatArtifact-Zeilen werden mit neuer chat_id dupliziert
      (relation = "cloned"); die referenzierten Entities selbst bleiben
      unangetastet (Shared-Folder-Semantik).

Polymorph-verknuepfte Tasks/Notes/Comments mit target_cls="ai.chat" auf
das Original werden NICHT kopiert; im Klon erscheinen sie ueber die
duplizierten ChatArtifact-Zeilen (sofern Tracking sie dort hinterlegt
hatte).
"""
from __future__ import annotations

from sqlalchemy import select

from lib.db import session_for_tenant
from lib.entities.tenant import AiChat, AiMessage, AiToolCall, ChatArtifact


def clone_chat(source_chat_id: int, tenant_slug: str, user_id: int) -> int:
    """Klont den Chat und liefert die neue chat_id."""
    with session_for_tenant(tenant_slug) as s:
        source = s.get(AiChat, source_chat_id)
        if source is None or source.is_deleted:
            raise ValueError(f"AiChat {source_chat_id} nicht gefunden")

        clone = AiChat(
            title=f"Kopie von {source.title}" if source.title else "Kopie",
            user_id=user_id,
            agent_name=source.agent_name,
            model=source.model,
            # Klon ist eigenstaendiger Top-Level-Chat (parent_chat_id=0), kein Sub-
            # Chat. Die Verbindung zum Original wird ueber die "cloned"-ChatArtifact-
            # Eintraege gehalten, nicht ueber parent_chat_id (das ist Sub-Chats vorbehalten).
            parent_chat_id=0,
            parent_tool_call_id=0,
            depth=0,
            is_shared=False,
        )
        s.add(clone)
        s.flush()
        clone_id = clone.id

        messages = list(
            s.scalars(
                select(AiMessage)
                .where(
                    AiMessage.chat_id == source.id,
                    AiMessage.is_deleted.is_(False),
                )
                .order_by(AiMessage.id)
            )
        )
        old_to_new: dict[int, int] = {}
        for m in messages:
            nm = AiMessage(
                chat_id=clone_id,
                role=m.role,
                content=m.content,
                tool_call_id=m.tool_call_id,
                tool_name=m.tool_name,
            )
            s.add(nm)
            s.flush()
            old_to_new[m.id] = nm.id

        if messages:
            tool_calls = list(
                s.scalars(
                    select(AiToolCall)
                    .where(
                        AiToolCall.message_id.in_(old_to_new.keys()),
                        AiToolCall.is_deleted.is_(False),
                    )
                    .order_by(AiToolCall.id)
                )
            )
            for tc in tool_calls:
                s.add(
                    AiToolCall(
                        message_id=old_to_new[tc.message_id],
                        tool_call_id=tc.tool_call_id,
                        tool_name=tc.tool_name,
                        arguments_json=tc.arguments_json,
                        result_text=tc.result_text,
                        status=tc.status,
                        duration_ms=tc.duration_ms,
                        sub_chat_id=0,
                    )
                )

        artifacts = list(
            s.scalars(
                select(ChatArtifact)
                .where(
                    ChatArtifact.chat_id == source.id,
                    ChatArtifact.is_deleted.is_(False),
                )
            )
        )
        for a in artifacts:
            s.add(
                ChatArtifact(
                    chat_id=clone_id,
                    artifact_cls=a.artifact_cls,
                    artifact_id=a.artifact_id,
                    relation="cloned",
                )
            )

        s.commit()
        return clone_id
