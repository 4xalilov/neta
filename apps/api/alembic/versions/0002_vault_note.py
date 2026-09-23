"""VaultNote jadvali (docs/10-obsidian-vault.md, roadmap 3.6).

``apps/api/src/engine/models/vault.py`` dagi modelga mos.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk_and_timestamps() -> list[sa.Column]:
    """``id uuid``, ``created_at``, ``updated_at`` — hamma jadvalda bor (docs/02)."""
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "vault_note",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("tags", JSONB(), nullable=False, server_default="[]"),
        sa.Column("links", JSONB(), nullable=False, server_default="[]"),
        sa.Column("frontmatter", JSONB(), nullable=False, server_default="{}"),
        sa.Column("body_excerpt", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("mtime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.CheckConstraint(
            "type IN ('brand', 'sop', 'staff', 'reference', 'plan', 'script', 'report')",
            name="ck_vault_note_type",
        ),
    )
    op.create_index("ix_vault_note_workspace_id", "vault_note", ["workspace_id"])
    op.create_index("ix_vault_note_path", "vault_note", ["path"], unique=True)
    op.execute(
        "CREATE INDEX ix_vault_note_embedding_ivfflat ON vault_note "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vault_note_embedding_ivfflat")
    op.drop_index("ix_vault_note_path", table_name="vault_note")
    op.drop_index("ix_vault_note_workspace_id", table_name="vault_note")
    op.drop_table("vault_note")
