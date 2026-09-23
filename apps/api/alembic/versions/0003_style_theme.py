"""StyleTheme jadvali (docs/03-roadmap.md 2.8, roadmap "Uslub bilimlar bazasi").

``apps/api/src/engine/models/style.py`` dagi modelga mos.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
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
        "style_theme",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("family", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="candidate"),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("theme_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("inspiration", sa.Text(), nullable=True),
        sa.Column("judge_score", sa.Integer(), nullable=True),
        sa.Column("judge_json", JSONB(), nullable=True),
        sa.Column("still_uri", sa.String(1000), nullable=True),
        sa.Column("problems", JSONB(), nullable=False, server_default="[]"),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('candidate', 'approved', 'rejected')", name="ck_style_theme_status"
        ),
        sa.CheckConstraint(
            "source IN ('builtin', 'llm', 'owner', 'import')", name="ck_style_theme_source"
        ),
    )
    op.create_index("ix_style_theme_workspace_id", "style_theme", ["workspace_id"])
    op.create_index("ix_style_theme_name", "style_theme", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_style_theme_name", table_name="style_theme")
    op.drop_index("ix_style_theme_workspace_id", table_name="style_theme")
    op.drop_table("style_theme")
