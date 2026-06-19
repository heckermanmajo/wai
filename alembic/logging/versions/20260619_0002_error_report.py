"""error_report table

Revision ID: logging_0002
Revises: logging_0001
Create Date: 2026-06-19

Erstellt error_report in logging_db — append-only Fehler-Reports vom
Frontend (Dev-Mode). Felder: tenant_id, session_id, url, status_code,
error_type, message, stack, user_agent, comment, context (JSONB).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "logging_0002"
down_revision: Union[str, None] = "logging_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "error_report",
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
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("session_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_type", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("stack", sa.Text(), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text(), nullable=False, server_default=""),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_error_report_tenant_id", "error_report", ["tenant_id"])
    op.create_index("ix_error_report_session_id", "error_report", ["session_id"])
    op.create_index(
        "ix_error_report_created_at", "error_report", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_error_report_created_at", table_name="error_report")
    op.drop_index("ix_error_report_session_id", table_name="error_report")
    op.drop_index("ix_error_report_tenant_id", table_name="error_report")
    op.drop_table("error_report")
