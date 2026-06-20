"""semantic layer

Revision ID: tenant_0005
Revises: tenant_0004
Create Date: 2026-06-20

Fuegt die semantische Schicht hinzu: semantic_fassade (1:1-Index pro
indizierter Quell-Entity, content_hash-gebunden) und semantic_snippet
(Markdown-Chunks der Fassade fuer RAG).

embedding ist hier bewusst ein Text-Feld — pgvector wird in einer
spaeteren Migration nachgezogen.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tenant_0005"
down_revision: Union[str, None] = "tenant_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "semantic_fassade",
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
        sa.Column("entity_class", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("entity_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resource_type", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("abstract", sa.Text(), nullable=False, server_default=""),
        sa.Column("url", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_semantic_fassade_entity",
        "semantic_fassade",
        ["entity_class", "entity_id", "is_deleted"],
    )
    op.create_index(
        "ix_semantic_fassade_resource_type",
        "semantic_fassade",
        ["resource_type", "is_deleted"],
    )

    op.create_table(
        "semantic_snippet",
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
        sa.Column("fassade_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("char_len", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        # embedding bleibt vorerst Text — wird in spaeterer Migration auf
        # pgvector umgezogen, sobald die Extension verfuegbar ist.
        sa.Column("embedding", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_semantic_snippet_fassade",
        "semantic_snippet",
        ["fassade_id", "is_deleted"],
    )
    op.create_index(
        "ix_semantic_snippet_content_hash",
        "semantic_snippet",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_semantic_snippet_content_hash", table_name="semantic_snippet")
    op.drop_index("ix_semantic_snippet_fassade", table_name="semantic_snippet")
    op.drop_table("semantic_snippet")
    op.drop_index("ix_semantic_fassade_resource_type", table_name="semantic_fassade")
    op.drop_index("ix_semantic_fassade_entity", table_name="semantic_fassade")
    op.drop_table("semantic_fassade")
