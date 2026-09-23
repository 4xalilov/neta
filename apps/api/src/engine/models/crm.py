"""CRM + Jarvis jadvallari (docs/02-data-model.md, "CRM + Jarvis" bo'limi).

Bundan tashqari roadmap 0.3 talabiga ko'ra ``crm_link`` jadvali ham shu yerda
(Chatwoot contact <-> Twenty person <-> ichki lead bog'lovchisi).
"""

from __future__ import annotations

import enum
import uuid
from datetime import date as date_
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from engine.db import Base, TimestampMixin, UUIDPkMixin

JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class LeadSource(enum.StrEnum):
    IG_DM = "ig_dm"
    IG_COMMENT = "ig_comment"
    LEAD_FORM = "lead_form"
    SITE = "site"
    PHONE = "phone"


class LeadStage(enum.StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    MEETING = "meeting"
    DEAL = "deal"
    LOST = "lost"


class JarvisActionLevel(enum.StrEnum):
    AUTONOMOUS = "autonomous"
    REQUIRES_APPROVAL = "requires_approval"


class Campaign(UUIDPkMixin, TimestampMixin, Base):
    """Reklama kampaniyasi (bitta post asosida bo'lishi mumkin)."""

    __tablename__ = "campaign"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("post.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    spend_usd: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Lead(UUIDPkMixin, TimestampMixin, Base):
    """Lid: manba, aloqa, ball, harorat, bosqich, kim zimmasida."""

    __tablename__ = "lead"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaign.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[LeadSource] = mapped_column(String(20))
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ig_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stage: Mapped[LeadStage] = mapped_column(String(20), default=LeadStage.NEW)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL"), nullable=True, index=True
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('ig_dm', 'ig_comment', 'lead_form', 'site', 'phone')",
            name="ck_lead_source",
        ),
        CheckConstraint(
            "stage IN ('new', 'contacted', 'meeting', 'deal', 'lost')",
            name="ck_lead_stage",
        ),
        # docs/02 "Muhim indekslar": lead(workspace_id, stage)
        Index("ix_lead_workspace_stage", "workspace_id", "stage"),
    )


class ContactEvent(UUIDPkMixin, TimestampMixin, Base):
    """Lid bilan aloqa (DM/qo'ng'iroq/komment). workspace_id yo'q — lead orqali."""

    __tablename__ = "contact_event"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lead.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class Deal(UUIDPkMixin, TimestampMixin, Base):
    """Bitim. workspace_id yo'q — lead orqali topiladi."""

    __tablename__ = "deal"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lead.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")


class Staff(UUIDPkMixin, TimestampMixin, Base):
    """Xodim: rol, odatlar (staff_memory)."""

    __tablename__ = "staff"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    tg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    habits: Mapped[dict | None] = mapped_column("json", JSON_VARIANT, nullable=True)


class Task(UUIDPkMixin, TimestampMixin, Base):
    """Xodimga berilgan vazifa: muddat, eslatma, eskalatsiya."""

    __tablename__ = "task"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lead.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # docs/02 "Muhim indekslar": task(due_at) where status='open'
        Index(
            "ix_task_due_at_open",
            "due_at",
            postgresql_where=text("status = 'open'"),
        ),
    )


class CallLog(UUIDPkMixin, TimestampMixin, Base):
    """Telefon/ovoz qo'ng'irog'i yozuvi (LiveKit, bosqich 6)."""

    __tablename__ = "call_log"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lead.id", ondelete="SET NULL"), nullable=True, index=True
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL"), nullable=True, index=True
    )
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recording_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)


class JarvisAction(UUIDPkMixin, TimestampMixin, Base):
    """Jarvis harakati: level=autonomous avtomatik, requires_approval interrupt()."""

    __tablename__ = "jarvis_action"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(50))
    level: Mapped[JarvisActionLevel] = mapped_column(String(20))
    payload: Mapped[dict | None] = mapped_column(JSON_VARIANT, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "level IN ('autonomous', 'requires_approval')", name="ck_jarvis_action_level"
        ),
    )


class DailyReport(UUIDPkMixin, TimestampMixin, Base):
    """Kunlik hisobot (matn + ovozli, Telegramga yuboriladi)."""

    __tablename__ = "daily_report"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date_] = mapped_column(Date)
    data: Mapped[dict] = mapped_column("json", JSON_VARIANT, default=dict)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CrmLink(UUIDPkMixin, TimestampMixin, Base):
    """Chatwoot contact <-> Twenty person <-> ichki lead bog'lovchisi (roadmap 0.3)."""

    __tablename__ = "crm_link"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), index=True
    )
    chatwoot_contact_id: Mapped[str] = mapped_column(String(100))
    twenty_person_id: Mapped[str] = mapped_column(String(100))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lead.id", ondelete="SET NULL"), nullable=True, index=True
    )
