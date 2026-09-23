"""Ega bilan suhbat xotirasi (roadmap 5.10, ``engine.jarvis.owner_memory``).

Har ega gapi (``role="user"``) va Jarvis javobi (``role="jarvis"``) bitta qator. Oxirgi N
almashuv niyat promptiga beriladi — "uni ertaga qil", "o'sha lidga yoz", "yana bir marta"
kabi havolalarni hal qilish uchun. ``intent_json`` — tahlil qilingan niyat (user) yoki
bajarilgan natija (jarvis: ``action_ids``, ``lead_ids``, faol ``workspace_id`` ...).
"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from engine.db import Base, TimestampMixin, UUIDPkMixin
from engine.models.crm import JSON_VARIANT


class OwnerMemory(UUIDPkMixin, TimestampMixin, Base):
    """Ega ↔ Jarvis suhbat qatori (``owner_memory``)."""

    __tablename__ = "owner_memory"

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=True, index=True
    )
    chat_id: Mapped[int] = mapped_column(BigInteger)
    role: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text, default="")
    intent_json: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'jarvis')", name="ck_owner_memory_role"),
        Index("ix_owner_memory_chat_created", "chat_id", "created_at"),
    )
