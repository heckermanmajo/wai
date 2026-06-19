"""initial logging schema

Revision ID: logging_0001
Revises:
Create Date: 2026-06-19

Erstellt die beiden Tabellen in logging_db: trace, event.
Append-only Telemetrie pro Chat-Runde.

Bewusst KEINE Foreign-Key-Constraints — Konvention im wai-Repo
(siehe lib/mixins.py). trace_uid ist UUID-String, gemeinsamer Bindebatzen.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "logging_0001"
down_revision: Union[str, None] = None
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
        "trace",
        *_base_columns(),
        sa.Column("trace_uid", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False, server_default=""),
        sa.Column("intent", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("trace_uid", name="uq_trace_uid"),
    )
    op.create_index("ix_trace_trace_uid", "trace", ["trace_uid"])
    op.create_index("ix_trace_tenant_id", "trace", ["tenant_id"])
    op.create_index("ix_trace_started_at", "trace", ["started_at"])

    op.create_table(
        "event",
        *_base_columns(),
        sa.Column("trace_uid", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("trace_uid", "sequence", name="uq_event_trace_seq"),
    )
    op.create_index("ix_event_trace_seq", "event", ["trace_uid", "sequence"])
    op.create_index("ix_event_event_type", "event", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_event_event_type", table_name="event")
    op.drop_index("ix_event_trace_seq", table_name="event")
    op.drop_table("event")
    op.drop_index("ix_trace_started_at", table_name="trace")
    op.drop_index("ix_trace_tenant_id", table_name="trace")
    op.drop_index("ix_trace_trace_uid", table_name="trace")
    op.drop_table("trace")
