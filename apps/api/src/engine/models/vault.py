"""Vault indeksi (docs/10-obsidian-vault.md, roadmap 3.6).

Har bir ``vault/**`` Markdown fayli uchun bitta qator: frontmatter, teglar,
``[[wikilink]]`` larning aniqlangan yo'llari va embedding (qidiruv +
Writer/Jarvis prompt xotirasi uchun, docs/10 "Indekslash" bo'limi).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from engine.db import Base, TimestampMixin, UUIDPkMixin
from engine.models.content import JSON_VARIANT, vector_column

VAULT_NOTE_TYPES = ("brand", "sop", "staff", "reference", "plan", "script", "report")


class VaultNote(UUIDPkMixin, TimestampMixin, Base):
    """Bitta vault fayli indeksi (``path`` — ``vault/`` ildiziga nisbatan)."""

    __tablename__ = "vault_note"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=True, index=True
    )
    path: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    tags: Mapped[list] = mapped_column(JSON_VARIANT, default=list)
    links: Mapped[list] = mapped_column(JSON_VARIANT, default=list)
    frontmatter: Mapped[dict] = mapped_column(JSON_VARIANT, default=dict)
    body_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    mtime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(vector_column(768), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('brand', 'sop', 'staff', 'reference', 'plan', 'script', 'report')",
            name="ck_vault_note_type",
        ),
        Index(
            "ix_vault_note_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
            info={"postgres_only": True},
        ),
    )
