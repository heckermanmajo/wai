"""initial admin schema

Revision ID: admin_0001
Revises:
Create Date: 2026-06-19

Erstellt die fuenf Tabellen in admin_db:
    tenant, user_data, tenant_membership, tenant_settings, ai_provider

Bewusst KEINE Foreign-Key-Constraints — alle Relationen sind nackte
Integer-IDs (siehe lib/mixins.py).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "admin_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_columns() -> list[sa.Column]:
    """BaseMixin-Spalten: id, created_at, updated_at, is_deleted."""
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
        "tenant",
        *_base_columns(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("brand_color", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("logo_path", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("favicon_path", sa.String(length=512), nullable=False, server_default=""),
        sa.UniqueConstraint("slug", name="uq_tenant_slug"),
    )

    op.create_table(
        "user_data",
        *_base_columns(),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("password_hash", sa.Text(), nullable=False, server_default=""),
        sa.Column("platform_role", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.UniqueConstraint("username", name="uq_user_data_username"),
    )

    op.create_table(
        "tenant_membership",
        *_base_columns(),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("tenant_role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "tenant_settings",
        *_base_columns(),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("tenant_id", "key", name="uq_tenant_settings_tenant_key"),
    )

    op.create_table(
        "ai_provider",
        *_base_columns(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("adapter_type", sa.String(length=64), nullable=False, server_default="openai"),
        sa.Column("api_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("base_url", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("default_model", sa.String(length=128), nullable=False, server_default="gpt-5.5"),
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_table("ai_provider")
    op.drop_table("tenant_settings")
    op.drop_table("tenant_membership")
    op.drop_table("user_data")
    op.drop_table("tenant")
