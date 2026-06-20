"""setting table (admin)

Revision ID: admin_0002
Revises: admin_0001
Create Date: 2026-06-20

Plan 03 — Settings-Hierarchie MVP. In admin_db landen nur die scope="platform"
Eintraege; tenant-/entity-/chat-Settings leben in tenant_db (eigene Migration).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "admin_0002"
down_revision: Union[str, None] = "admin_0001"
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
        "setting",
        *_base_columns(),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("scope_ref", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("entity_cls", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("entity_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("set_by", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "scope", "scope_ref", "entity_cls", "entity_id", "key",
            name="uq_setting_scope_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("setting")
