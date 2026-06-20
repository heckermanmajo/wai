"""process table (tenant) — Plan 07

Revision ID: tenant_0010
Revises: tenant_0009
Create Date: 2026-06-20

Anlassgetriebene Arbeitseinheit (Vision §1). Polymorpher Kunden-Anker
(customer_cls + customer_id), nackte Refs auf project / parent_process /
owner_user / assignee_user (Repo-Konvention: keine FKs).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tenant_0010"
down_revision: Union[str, None] = "tenant_0009"
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
        "process",
        *_base_columns(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="neu"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("kind", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("owner_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assignee_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("project_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("customer_cls", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("customer_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_process_status_open", "process", ["is_deleted", "status"]
    )
    op.create_index(
        "ix_process_project", "process", ["project_id", "is_deleted"]
    )
    op.create_index(
        "ix_process_assignee", "process", ["assignee_user_id", "status"]
    )
    op.create_index(
        "ix_process_customer",
        "process",
        ["customer_cls", "customer_id", "is_deleted"],
    )
    op.create_index("ix_process_parent", "process", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_process_parent", table_name="process")
    op.drop_index("ix_process_customer", table_name="process")
    op.drop_index("ix_process_assignee", table_name="process")
    op.drop_index("ix_process_project", table_name="process")
    op.drop_index("ix_process_status_open", table_name="process")
    op.drop_table("process")
