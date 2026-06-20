"""entity_change table

Revision ID: logging_0003
Revises: logging_0002
Create Date: 2026-06-20

Plan 04 — Append-only Audit-Trail pro Feld-Aenderung. Indexe sind
auf die drei Default-Read-Pattern abgestimmt:
    1. Verlaufs-Tab pro Entity (tenant_id, target_cls, target_id, created_at DESC)
    2. Sprung von Trace-Achse zu allen Changes des Runs (trace_uid)
    3. Globaler Filter "alle AI-Aenderungen letzte Woche" (actor_type, created_at DESC)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "logging_0003"
down_revision: Union[str, None] = "logging_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_columns() -> list[sa.Column]:
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
        "entity_change",
        *_base_columns(),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("target_cls", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(length=16), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False, server_default="system"),
        sa.Column("actor_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agent_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("trace_uid", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("field_diffs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_entity_change_target",
        "entity_change",
        ["tenant_id", "target_cls", "target_id", "created_at"],
    )
    op.create_index("ix_entity_change_trace_uid", "entity_change", ["trace_uid"])
    op.create_index(
        "ix_entity_change_actor_type",
        "entity_change",
        ["actor_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_entity_change_actor_type", table_name="entity_change")
    op.drop_index("ix_entity_change_trace_uid", table_name="entity_change")
    op.drop_index("ix_entity_change_target", table_name="entity_change")
    op.drop_table("entity_change")
