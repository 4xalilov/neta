"""Boshlang'ich sxema: Content Engine + CRM/Jarvis (docs/02-data-model.md).

Qo'lda yozilgan (autogenerate emas — bu muhitda Postgres yo'q). Har bir
jadval ``apps/api/src/engine/models/content.py`` va ``crm.py`` dagi
modellarga mos keladi.

Revision ID: 0001
Revises:
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
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
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ---------------------------------------------------------------- Content Engine
    op.create_table(
        "workspace",
        *_pk_and_timestamps(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("owner_tg_id", sa.Integer(), nullable=True),
        sa.Column("ig_business_id", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Tashkent"),
    )

    op.create_table(
        "brand_profile",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("json", JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_brand_profile_workspace_id", "brand_profile", ["workspace_id"])

    op.create_table(
        "ig_audit",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("json", JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_ig_audit_workspace_id", "ig_audit", ["workspace_id"])

    op.create_table(
        "reference_video",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("structure_json", JSONB(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
    )
    op.create_index("ix_reference_video_workspace_id", "reference_video", ["workspace_id"])

    op.create_table(
        "taste_memory",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.CheckConstraint(
            "kind IN ('approved', 'rejected', 'note')", name="ck_taste_memory_kind"
        ),
    )
    op.create_index("ix_taste_memory_workspace_id", "taste_memory", ["workspace_id"])
    op.execute(
        "CREATE INDEX ix_taste_memory_embedding_ivfflat ON taste_memory "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "content_plan",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("aida_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
    )
    op.create_index("ix_content_plan_workspace_id", "content_plan", ["workspace_id"])

    op.create_table(
        "script",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            UUID(as_uuid=True),
            sa.ForeignKey("content_plan.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("hook_variants", JSONB(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("cta", sa.Text(), nullable=True),
        sa.Column("tts_text", sa.Text(), nullable=True),
        sa.Column("subtitle_json", JSONB(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("iteration", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
    )
    op.create_index("ix_script_workspace_id", "script", ["workspace_id"])
    op.create_index("ix_script_plan_id", "script", ["plan_id"])

    op.create_table(
        "critic_review",
        *_pk_and_timestamps(),
        sa.Column(
            "script_id",
            UUID(as_uuid=True),
            sa.ForeignKey("script.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("critic", sa.String(50), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons", JSONB(), nullable=True),
    )
    op.create_index("ix_critic_review_script_id", "critic_review", ["script_id"])

    op.create_table(
        "asset",
        *_pk_and_timestamps(),
        sa.Column(
            "script_id",
            UUID(as_uuid=True),
            sa.ForeignKey("script.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("uri", sa.String(1000), nullable=False),
        sa.Column("meta", JSONB(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('audio', 'image', 'depth', 'video')", name="ck_asset_kind"
        ),
    )
    op.create_index("ix_asset_script_id", "asset", ["script_id"])

    op.create_table(
        "post",
        *_pk_and_timestamps(),
        sa.Column(
            "script_id",
            UUID(as_uuid=True),
            sa.ForeignKey("script.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ig_media_id", sa.String(100), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("variant", sa.String(50), nullable=True),
    )
    op.create_index("ix_post_script_id", "post", ["script_id"])

    op.create_table(
        "post_metrics",
        *_pk_and_timestamps(),
        sa.Column(
            "post_id",
            UUID(as_uuid=True),
            sa.ForeignKey("post.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("saves", sa.Integer(), nullable=True),
        sa.Column("shares", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Integer(), nullable=True),
        sa.Column("watch_time", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_post_metrics_post_id", "post_metrics", ["post_id"])

    op.create_table(
        "cost_log",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("ix_cost_log_workspace_id", "cost_log", ["workspace_id"])

    op.create_table(
        "render_job",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "script_id",
            UUID(as_uuid=True),
            sa.ForeignKey("script.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("props", JSONB(), nullable=False, server_default="{}"),
        sa.Column("video_uri", sa.String(1000), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')", name="ck_render_job_status"
        ),
    )
    op.create_index("ix_render_job_workspace_id", "render_job", ["workspace_id"])
    op.create_index("ix_render_job_script_id", "render_job", ["script_id"])

    # ---------------------------------------------------------------------- CRM + Jarvis
    op.create_table(
        "staff",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("tg_id", sa.Integer(), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("json", JSONB(), nullable=True),
    )
    op.create_index("ix_staff_workspace_id", "staff", ["workspace_id"])

    op.create_table(
        "campaign",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            UUID(as_uuid=True),
            sa.ForeignKey("post.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("spend_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_campaign_workspace_id", "campaign", ["workspace_id"])
    op.create_index("ix_campaign_post_id", "campaign", ["post_id"])

    op.create_table(
        "lead",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaign.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("ig_handle", sa.String(100), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("temperature", sa.String(20), nullable=True),
        sa.Column("stage", sa.String(20), nullable=False, server_default="new"),
        sa.Column(
            "assigned_to",
            UUID(as_uuid=True),
            sa.ForeignKey("staff.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "source IN ('ig_dm', 'ig_comment', 'lead_form', 'site', 'phone')",
            name="ck_lead_source",
        ),
        sa.CheckConstraint(
            "stage IN ('new', 'contacted', 'meeting', 'deal', 'lost')",
            name="ck_lead_stage",
        ),
    )
    op.create_index("ix_lead_workspace_id", "lead", ["workspace_id"])
    op.create_index("ix_lead_campaign_id", "lead", ["campaign_id"])
    op.create_index("ix_lead_assigned_to", "lead", ["assigned_to"])
    # docs/02 "Muhim indekslar": lead(workspace_id, stage)
    op.create_index("ix_lead_workspace_stage", "lead", ["workspace_id", "stage"])

    op.create_table(
        "contact_event",
        *_pk_and_timestamps(),
        sa.Column(
            "lead_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lead.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_contact_event_lead_id", "contact_event", ["lead_id"])

    op.create_table(
        "deal",
        *_pk_and_timestamps(),
        sa.Column(
            "lead_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lead.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
    )
    op.create_index("ix_deal_lead_id", "deal", ["lead_id"])

    op.create_table(
        "task",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "staff_id",
            UUID(as_uuid=True),
            sa.ForeignKey("staff.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lead.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("reminders_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_task_workspace_id", "task", ["workspace_id"])
    op.create_index("ix_task_staff_id", "task", ["staff_id"])
    op.create_index("ix_task_lead_id", "task", ["lead_id"])
    # docs/02 "Muhim indekslar": task(due_at) where status='open'
    op.execute(
        "CREATE INDEX ix_task_due_at_open ON task (due_at) WHERE status = 'open'"
    )

    op.create_table(
        "call_log",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lead.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "staff_id",
            UUID(as_uuid=True),
            sa.ForeignKey("staff.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("recording_uri", sa.String(1000), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(50), nullable=True),
    )
    op.create_index("ix_call_log_workspace_id", "call_log", ["workspace_id"])
    op.create_index("ix_call_log_lead_id", "call_log", ["lead_id"])
    op.create_index("ix_call_log_staff_id", "call_log", ["staff_id"])

    op.create_table(
        "jarvis_action",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "level IN ('autonomous', 'requires_approval')", name="ck_jarvis_action_level"
        ),
    )
    op.create_index("ix_jarvis_action_workspace_id", "jarvis_action", ["workspace_id"])

    op.create_table(
        "daily_report",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_daily_report_workspace_id", "daily_report", ["workspace_id"])

    op.create_table(
        "crm_link",
        *_pk_and_timestamps(),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chatwoot_contact_id", sa.String(100), nullable=False),
        sa.Column("twenty_person_id", sa.String(100), nullable=False),
        sa.Column(
            "lead_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lead.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_crm_link_workspace_id", "crm_link", ["workspace_id"])
    op.create_index("ix_crm_link_lead_id", "crm_link", ["lead_id"])

    # docs/02: "post_metrics -> campaign -> lead: qaysi Reels qancha lid/sotuv berdi"
    op.execute(
        """
        CREATE VIEW campaign_roi AS
        SELECT
            c.id AS campaign_id,
            c.workspace_id AS workspace_id,
            c.name AS name,
            c.spend_usd AS spend_usd,
            count(DISTINCT l.id) AS leads_count,
            count(DISTINCT d.id) AS deals_count,
            COALESCE(sum(d.amount), 0) AS revenue_usd
        FROM campaign c
        LEFT JOIN lead l ON l.campaign_id = c.id
        LEFT JOIN deal d ON d.lead_id = l.id
        GROUP BY c.id, c.workspace_id, c.name, c.spend_usd
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS campaign_roi")

    op.drop_table("crm_link")
    op.drop_table("daily_report")
    op.drop_table("jarvis_action")
    op.drop_table("call_log")
    op.execute("DROP INDEX IF EXISTS ix_task_due_at_open")
    op.drop_table("task")
    op.drop_table("deal")
    op.drop_table("contact_event")
    op.drop_table("lead")
    op.drop_table("campaign")
    op.drop_table("staff")

    op.drop_table("render_job")
    op.drop_table("cost_log")
    op.drop_table("post_metrics")
    op.drop_table("post")
    op.drop_table("asset")
    op.drop_table("critic_review")
    op.drop_table("script")
    op.drop_table("content_plan")
    op.execute("DROP INDEX IF EXISTS ix_taste_memory_embedding_ivfflat")
    op.drop_table("taste_memory")
    op.drop_table("reference_video")
    op.drop_table("ig_audit")
    op.drop_table("brand_profile")
    op.drop_table("workspace")
