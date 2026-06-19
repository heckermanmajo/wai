"""chat_artifact + ai_chat.is_shared

Revision ID: tenant_0003
Revises: tenant_0002
Create Date: 2026-06-19

Fuegt die "Mappen"-Tabelle chat_artifact hinzu (M:N-Link von AiChat zu
beliebigen Entities) und das Flag ai_chat.is_shared (geteilte Chats im
Tenant fuer alle User sichtbar).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tenant_0003"
down_revision: Union[str, None] = "tenant_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_artifact",
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
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("artifact_cls", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("relation", sa.String(length=32), nullable=False, server_default="linked"),
    )
    op.create_index(
        "ix_chat_artifact_chat",
        "chat_artifact",
        ["chat_id", "is_deleted"],
    )

    op.add_column(
        "ai_chat",
        sa.Column(
            "is_shared",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_chat", "is_shared")
    op.drop_index("ix_chat_artifact_chat", table_name="chat_artifact")
    op.drop_table("chat_artifact")
