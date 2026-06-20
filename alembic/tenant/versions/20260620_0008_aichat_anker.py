"""ai_chat polymorpher Anker

Revision ID: tenant_0008
Revises: tenant_0007
Create Date: 2026-06-20

Fuegt ai_chat die Spalten target_cls + target_id hinzu — polymorpher Anker
auf eine beliebige Resource (Vorgang, View, Document, ...), analog zu
Document/Note/Task. Leerer Anker (``target_cls=""``, ``target_id=0``) =
unverankert. Zusaetzlich Composite-Index ix_ai_chat_target fuer Lookups.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tenant_0008"
down_revision: Union[str, None] = "tenant_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_chat",
        sa.Column("target_cls", sa.String(64), nullable=False, server_default=""),
    )
    op.add_column(
        "ai_chat",
        sa.Column("target_id", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_ai_chat_target", "ai_chat", ["target_cls", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_chat_target", table_name="ai_chat")
    op.drop_column("ai_chat", "target_id")
    op.drop_column("ai_chat", "target_cls")
