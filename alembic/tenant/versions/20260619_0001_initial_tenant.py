"""initial tenant schema

Revision ID: tenant_0001
Revises:
Create Date: 2026-06-19

Erstellt die elf allgemeinen Tabellen pro Mandant in tenant_<slug>:
    project, task, note, comment, tag, tag_assignment, attachment,
    reminder, ai_chat, ai_message, ai_tool_call

Bewusst KEINE Foreign-Key-Constraints — alle Relationen sind nackte
Integer-IDs (siehe lib/mixins.py). Polymorphe Verweise gehen ueber
(target_cls, target_id); target_cls ist der Alias aus lib/polymorphic.py
(z.B. "core.project", "ai.chat").
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tenant_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_columns() -> list[sa.Column]:
    """BaseMixin-Spalten: id, created_at, updated_at, is_deleted."""
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "project",
        *_base_columns(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("owner_user_id", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "task",
        *_base_columns(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignee_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_cls", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("target_id", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "note",
        *_base_columns(),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("author_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("author_display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("target_cls", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("target_id", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "comment",
        *_base_columns(),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("author_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("author_display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("target_cls", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("target_id", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "tag",
        *_base_columns(),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#cccccc"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )

    op.create_table(
        "tag_assignment",
        *_base_columns(),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("target_cls", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "tag_id", "target_cls", "target_id", name="uq_tag_assignment_tag_target"
        ),
    )

    op.create_table(
        "attachment",
        *_base_columns(),
        sa.Column("minio_key", sa.String(length=512), nullable=False),
        sa.Column(
            "mime",
            sa.String(length=128),
            nullable=False,
            server_default="application/octet-stream",
        ),
        sa.Column("filename", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="upload"),
        sa.Column("uploader_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_cls", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("target_id", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "reminder",
        *_base_columns(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_cls", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("target_id", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "ai_chat",
        *_base_columns(),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agent_name", sa.String(length=64), nullable=False, server_default="manager"),
        sa.Column("model", sa.String(length=64), nullable=False, server_default="gpt-5.5"),
        sa.Column("parent_chat_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_tool_call_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "ai_message",
        *_base_columns(),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("tool_call_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("tool_name", sa.String(length=128), nullable=False, server_default=""),
    )

    op.create_table(
        "ai_tool_call",
        *_base_columns(),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("tool_call_id", sa.String(length=128), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("result_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sub_chat_id", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("ai_tool_call")
    op.drop_table("ai_message")
    op.drop_table("ai_chat")
    op.drop_table("reminder")
    op.drop_table("attachment")
    op.drop_table("tag_assignment")
    op.drop_table("tag")
    op.drop_table("comment")
    op.drop_table("note")
    op.drop_table("task")
    op.drop_table("project")
