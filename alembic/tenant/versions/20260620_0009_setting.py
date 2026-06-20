"""setting table (tenant)

Revision ID: tenant_0009
Revises: tenant_0008
Create Date: 2026-06-20

Plan 03 — Settings-Hierarchie MVP. In tenant_db landen scope in
{tenant, entity_type, entity, chat}. Plattform-Settings leben separat
in admin_db.

scope_ref-Konvention:
- scope=tenant       : scope_ref=<tenant-slug>
- scope=entity_type  : scope_ref=<entity-alias> (z.B. "core.task")
- scope=entity       : entity_cls=<alias>, entity_id=<id>; scope_ref=""
- scope=chat         : scope_ref=<chat_id als String>
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "tenant_0009"
down_revision: Union[str, None] = "tenant_0008"
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
