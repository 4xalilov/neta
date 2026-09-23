"""OwnerMemory jadvali (docs/03-roadmap.md 5.10, ega ↔ Jarvis ovozli suhbat xotirasi).

``apps/api/src/engine/models/owner.py`` dagi modelga mos.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_memory",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("intent_json", JSONB(), nullable=True),
        sa.CheckConstraint("role IN ('user', 'jarvis')", name="ck_owner_memory_role"),
    )
    op.create_index("ix_owner_memory_workspace_id", "owner_memory", ["workspace_id"])
    op.create_index(
        "ix_owner_memory_chat_created", "owner_memory", ["chat_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_owner_memory_chat_created", table_name="owner_memory")
    op.drop_index("ix_owner_memory_workspace_id", table_name="owner_memory")
    op.drop_table("owner_memory")
