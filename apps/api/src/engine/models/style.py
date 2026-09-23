"""StyleTheme jadvali (docs/03-roadmap.md 2.8, docs/11-motion-library.md "Uslublar").

O'sib boruvchi uslub bilimlar bazasi: har tema (Remotion ``StyleTheme`` JSON'i)
``candidate`` sifatida boshlanadi, sxema+kontrast+render+VisionQA darvozasidan
o'tsa ``approved`` bo'ladi (``engine/styles/gate.py``), aks holda ``rejected`` —
sabablari ``problems``/``judge_json`` da saqlanadi. ``engine/styles/registry.py``
shu jadval bilan ishlaydi.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from engine.db import Base, TimestampMixin, UUIDPkMixin
from engine.models.content import JSON_VARIANT

STYLE_THEME_STATUSES = ("candidate", "approved", "rejected")
STYLE_THEME_SOURCES = ("builtin", "llm", "owner", "import")


class StyleTheme(UUIDPkMixin, TimestampMixin, Base):
    """Bitta uslub (tema) yozuvi — ``theme_json`` Remotion ``StyleTheme`` sxemasiga mos.

    ``workspace_id`` bo'sh bo'lishi mumkin: global (barcha workspace) katalog
    yozuvlari ``NULL`` bilan saqlanadi, faqat bitta ega uchun moslashtirilgan
    tema esa o'sha workspace'ga bog'lanadi.
    """

    __tablename__ = "style_theme"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    family: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="candidate")
    source: Mapped[str] = mapped_column(String(20))
    theme_json: Mapped[dict] = mapped_column(JSON_VARIANT, default=dict)
    inspiration: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    judge_json: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    still_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    problems: Mapped[list] = mapped_column(JSON_VARIANT, default=list)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate', 'approved', 'rejected')", name="ck_style_theme_status"
        ),
        CheckConstraint(
            "source IN ('builtin', 'llm', 'owner', 'import')", name="ck_style_theme_source"
        ),
    )


__all__ = ["STYLE_THEME_SOURCES", "STYLE_THEME_STATUSES", "StyleTheme"]
