"""Task.note ustuni — bot "Kechikadi" izohi va "Bajarildi" eslatmasi uchun
(``POST /v1/tasks/{task_id}/status``, ``apps/api/src/engine/models/crm.py`` dagi modelga mos).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("task", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("task", "note")
