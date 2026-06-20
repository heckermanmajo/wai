"""document table

Revision ID: tenant_0004
Revises: tenant_0003
Create Date: 2026-06-20

Fuegt die document-Tabelle hinzu: eigenstaendige editierbare Long-Form-
Entitaet (Title + Markdown-Content + optionaler polymorpher Anker via
target_cls/target_id). Note bleibt fuer kurze Annotations bestehen.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tenant_0004"
down_revision: Union[str, None] = "tenant_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document",
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
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("format", sa.String(length=16), nullable=False, server_default="markdown"),
        sa.Column("author_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "author_display_name",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
        sa.Column("target_cls", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("target_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_document_target",
        "document",
        ["target_cls", "target_id", "is_deleted"],
    )
    op.create_index(
        "ix_document_author",
        "document",
        ["author_user_id", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_author", table_name="document")
    op.drop_index("ix_document_target", table_name="document")
    op.drop_table("document")
