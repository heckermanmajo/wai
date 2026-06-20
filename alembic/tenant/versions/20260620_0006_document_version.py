"""document_version table

Revision ID: tenant_0006
Revises: tenant_0005
Create Date: 2026-06-20

Fuegt die document_version-Tabelle hinzu: historische Snapshots eines
Document. Jede echte Aenderung am Document erzeugt vor dem Apply einen
Eintrag mit den ALTEN Werten. Enables Versionshistorie und Restore.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tenant_0006"
down_revision: Union[str, None] = "tenant_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_version",
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
        sa.Column("document_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("change_summary", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_document_version_doc_version",
        "document_version",
        ["document_id", "version", "is_deleted"],
    )
    op.create_index(
        "ix_document_version_doc_created",
        "document_version",
        ["document_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_version_doc_created", table_name="document_version")
    op.drop_index("ix_document_version_doc_version", table_name="document_version")
    op.drop_table("document_version")
