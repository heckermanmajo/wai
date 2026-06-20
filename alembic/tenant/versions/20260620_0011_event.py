"""event table (tenant) — Plan 08

Revision ID: tenant_0011
Revises: tenant_0010
Create Date: 2026-06-20

Fachliches Event am Vorgang (Vision §2). Polymorpher Anker
(target_cls + target_id), trace_uid-Bruecke zu logging_db.trace,
source/source_ref fuer Auto-Erzeuger-Idempotenz.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "tenant_0011"
down_revision: Union[str, None] = "tenant_0010"
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
        "event",
        *_base_columns(),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_cls", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column(
            "actor_type", sa.String(length=16), nullable=False, server_default="system"
        ),
        sa.Column("actor_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agent_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("trace_uid", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(length=255), nullable=False, server_default=""),
        sa.Column(
            "data",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # Timeline-Query: "letzte N Events zu target X" — meistgenutzt.
    op.create_index(
        "ix_event_timeline",
        "event",
        ["is_deleted", "target_cls", "target_id", sa.text("happened_at DESC")],
    )
    # Bruecke Debug-View -> fachliches Event.
    op.create_index("ix_event_trace_uid", "event", ["trace_uid"])
    # Statistik-/Filter-Queries.
    op.create_index("ix_event_type_happened", "event", ["event_type", "happened_at"])
    # Idempotenz-Check fuer Auto-Events.
    op.create_index("ix_event_source_ref", "event", ["source", "source_ref"])


def downgrade() -> None:
    op.drop_index("ix_event_source_ref", table_name="event")
    op.drop_index("ix_event_type_happened", table_name="event")
    op.drop_index("ix_event_trace_uid", table_name="event")
    op.drop_index("ix_event_timeline", table_name="event")
    op.drop_table("event")
