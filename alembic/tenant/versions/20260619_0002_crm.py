"""crm tenant schema

Revision ID: tenant_0002
Revises: tenant_0001
Create Date: 2026-06-19

Erstellt die sieben CRM-Tabellen pro Mandant in tenant_<slug>:
    crm_account, crm_contact, crm_lead, crm_pipeline, crm_stage,
    crm_deal, crm_interaction

Bewusst KEINE Foreign-Key-Constraints — alle Relationen sind nackte
Integer-IDs (siehe lib/mixins.py). Polymorphe Verweise gehen weiterhin
ueber (target_cls, target_id) in core.note / core.comment / core.task /
core.attachment / core.reminder / core.tag_assignment.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tenant_0002"
down_revision: Union[str, None] = "tenant_0001"
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
        "crm_account",
        *_base_columns(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("website", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_user_id", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "crm_contact",
        *_base_columns(),
        sa.Column("first_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("account_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("role_title", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("channels", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("owner_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "lifecycle_stage",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
    )

    op.create_table(
        "crm_lead",
        *_base_columns(),
        sa.Column("first_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("company_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column(
            "qualification_score", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "converted_contact_id", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "crm_pipeline",
        *_base_columns(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )

    op.create_table(
        "crm_stage",
        *_base_columns(),
        sa.Column("pipeline_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ordering", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "win_probability", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("is_won", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_lost", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "crm_deal",
        *_base_columns(),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contact_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pipeline_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("value_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("expected_close_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("owner_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )

    op.create_table(
        "crm_interaction",
        *_base_columns(),
        sa.Column("contact_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("account_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="note"),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="out"),
        sa.Column("summary", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "transcript_attachment_id",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "attachment_ids", sa.String(length=512), nullable=False, server_default=""
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author_user_id", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("crm_interaction")
    op.drop_table("crm_deal")
    op.drop_table("crm_stage")
    op.drop_table("crm_pipeline")
    op.drop_table("crm_lead")
    op.drop_table("crm_contact")
    op.drop_table("crm_account")
