"""``/v1`` API so'rov/javob modellari (bot kontrakti: apps/bot/bot/api_client.py)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    owner_tg_id: int
    name: str = Field(min_length=1, max_length=200)


class WorkspaceOut(BaseModel):
    id: str
    name: str
    owner_tg_id: int | None = None
    timezone: str = "Asia/Tashkent"
    brand_profile: dict[str, Any] = Field(default_factory=dict)


class BrandProfilePatch(BaseModel):
    """Istalgan maydonlar (bot: ``pronoun``, ``voice``, ``register``) — mavjud JSON bilan birlashadi."""

    model_config = ConfigDict(extra="allow")


class BriefCreate(BaseModel):
    workspace_id: str
    text: str = Field(min_length=1, max_length=4000)
    plan_item: dict[str, Any] | None = None


class BriefOut(BaseModel):
    job_id: str


class JobOut(BaseModel):
    job_id: str
    status: str
    stage: str = ""
    progress: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None


class ScriptApprove(BaseModel):
    hook_idx: int = Field(default=0, ge=0, le=9)


class ScriptReject(BaseModel):
    reason: str = ""
    retry: bool = False


class VideoApprove(BaseModel):
    action: Literal["publish", "schedule"]


class ScriptOut(BaseModel):
    id: str
    workspace_id: str
    status: str
    hooks: list[str] = Field(default_factory=list)
    hook_idx: int = 0            # bot kontrakti (apps/bot/README.md)
    selected_hook_idx: int = 0   # = hook_idx
    body: str | None = None
    cta: str | None = None
    tts_text: str | None = None
    score: float | None = None
    iteration: int = 0
    job_id: str | None = None


class OkOut(BaseModel):
    ok: bool = True
    detail: str | None = None
    job_id: str | None = None


class DailyReportOut(BaseModel):
    workspace_id: str
    date: str
    leads: int = 0
    hot: int = 0
    sales: int = 0
    revenue: float = 0.0
    overdue: int = 0
    scripts: dict[str, int] = Field(default_factory=dict)
    videos: int = 0
    cost_usd: float = 0.0
    cost_by_node: dict[str, float] = Field(default_factory=dict)


class JarvisDecision(BaseModel):
    decision: Literal["yes", "no", "edit"]
    comment: str | None = None
