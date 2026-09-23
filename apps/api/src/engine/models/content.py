"""Content Engine jadvallari (docs/02-data-model.md, "Content Engine" bo'limi).

Bundan tashqari roadmap 0.3 talabiga ko'ra ``render_job`` jadvali ham shu yerda
(Remotion render navbatidagi vazifalar).
"""

from __future__ import annotations

import enum
import uuid
from datetime import date as date_
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from engine.db import Base, TimestampMixin, UUIDPkMixin

# JSON: postgresda JSONB, boshqa dialektlarda (masalan sqlite) oddiy JSON.
JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


def vector_column(dim: int):
    """Embedding ustuni: postgresda pgvector, sqlite testlarida JSON fallback."""
    return Vector(dim).with_variant(JSON(), "sqlite")


class AssetKind(enum.StrEnum):
    AUDIO = "audio"
    IMAGE = "image"
    DEPTH = "depth"
    VIDEO = "video"


class TasteMemoryKind(enum.StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NOTE = "note"


class RenderJobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Workspace(UUIDPkMixin, TimestampMixin, Base):
    """Bitta ega = bitta workspace (docs/02, kirish qismi)."""

    __tablename__ = "workspace"

    name: Mapped[str] = mapped_column(String(200))
    owner_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ig_business_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")


class BrandProfile(UUIDPkMixin, TimestampMixin, Base):
    """Ton, taqiqlangan so'zlar, CTA, siz/sen, ranglar — JSON."""

    __tablename__ = "brand_profile"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[dict] = mapped_column("json", JSON_VARIANT, default=dict)


class IgAudit(UUIDPkMixin, TimestampMixin, Base):
    """Instagram auditi natijasi: kuchli/zaif, post ritmi, hook turlari."""

    __tablename__ = "ig_audit"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[dict] = mapped_column("json", JSON_VARIANT, default=dict)


class ReferenceVideo(UUIDPkMixin, TimestampMixin, Base):
    """Referens videolar: transkript + struktura + embedding (xotira qatlam 3)."""

    __tablename__ = "reference_video"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    source_url: Mapped[str] = mapped_column(String(1000))
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    structure_json: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(vector_column(768), nullable=True)


class TasteMemory(UUIDPkMixin, TimestampMixin, Base):
    """Xotira qatlam 2: har tasdiq/rad "nega" izohi bilan, pgvector."""

    __tablename__ = "taste_memory"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[TasteMemoryKind] = mapped_column(
        String(20), default=TasteMemoryKind.NOTE
    )
    text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(vector_column(768), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('approved', 'rejected', 'note')", name="ck_taste_memory_kind"
        ),
        Index(
            "ix_taste_memory_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
            info={"postgres_only": True},
        ),
    )


class ContentPlan(UUIDPkMixin, TimestampMixin, Base):
    """7 kunlik AIDA reja."""

    __tablename__ = "content_plan"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    week_start: Mapped[date_] = mapped_column(Date)
    aida_json: Mapped[dict] = mapped_column(JSON_VARIANT, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft")


class Script(UUIDPkMixin, TimestampMixin, Base):
    """Kunlik ssenariy: hook variantlari, matn, TTS matni, subtitr, ball."""

    __tablename__ = "script"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_plan.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[int] = mapped_column(Integer)
    hook_variants: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    tts_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtitle_json: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="draft")


class CriticReview(UUIDPkMixin, TimestampMixin, Base):
    """Kritik agent bahosi. workspace_id yo'q — script orqali topiladi."""

    __tablename__ = "critic_review"

    script_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("script.id", ondelete="CASCADE"), index=True
    )
    critic: Mapped[str] = mapped_column(String(50))
    score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)


class Asset(UUIDPkMixin, TimestampMixin, Base):
    """Audio/rasm/depth/video aktivi. workspace_id yo'q — script orqali topiladi."""

    __tablename__ = "asset"

    script_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("script.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[AssetKind] = mapped_column(String(20))
    uri: Mapped[str] = mapped_column(String(1000))
    meta: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('audio', 'image', 'depth', 'video')", name="ck_asset_kind"
        ),
    )


class Post(UUIDPkMixin, TimestampMixin, Base):
    """Instagramda e'lon qilingan post. workspace_id yo'q — script orqali topiladi."""

    __tablename__ = "post"

    script_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("script.id", ondelete="CASCADE"), index=True
    )
    ig_media_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    variant: Mapped[str | None] = mapped_column(String(50), nullable=True)


class PostMetrics(UUIDPkMixin, TimestampMixin, Base):
    """48 soatlik analitika. workspace_id yo'q — post orqali topiladi."""

    __tablename__ = "post_metrics"

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("post.id", ondelete="CASCADE"), index=True
    )
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watch_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CostLog(UUIDPkMixin, TimestampMixin, Base):
    """Har LLM/TTS/FLUX chaqirig'i (cost_tracker orqali yoziladi)."""

    __tablename__ = "cost_log"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    node: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    usd: Mapped[float] = mapped_column(Float, default=0.0)


class RenderJob(UUIDPkMixin, TimestampMixin, Base):
    """Remotion render navbatidagi vazifa (roadmap 0.3)."""

    __tablename__ = "render_job"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("script.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[RenderJobStatus] = mapped_column(
        String(20), default=RenderJobStatus.QUEUED
    )
    props: Mapped[dict] = mapped_column(JSON_VARIANT, default=dict)
    video_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')", name="ck_render_job_status"
        ),
    )
