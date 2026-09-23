"""``/v1`` endpointlar — Telegram bot kontrakti (apps/bot/bot/api_client.py, apps/api/README.md).

Og'ir ish (graf) arq worker'da: ``POST /v1/briefs`` → ``run_brief``; tasdiq/rad →
``resume_brief``. Job holati Redis'da (``engine.jobs``).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from typing import Annotated, Any

import arq
from arq.connections import ArqRedis, RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine import jobs
from engine.db import get_session
from engine.models import (
    Asset,
    BrandProfile,
    ContentPlan,
    CostLog,
    Deal,
    JarvisAction,
    JarvisActionLevel,
    Lead,
    Script,
    Task,
    TasteMemory,
    TasteMemoryKind,
    Workspace,
)
from engine.settings import settings

from .schemas import (
    BrandProfilePatch,
    BriefCreate,
    BriefOut,
    DailyReportOut,
    JarvisDecision,
    JobOut,
    OkOut,
    ScriptApprove,
    ScriptOut,
    ScriptReject,
    VideoApprove,
    WorkspaceCreate,
    WorkspaceOut,
)

router = APIRouter(prefix="/v1")

DEFAULT_BRAND = {"pronoun": "siz", "address_form": "siz", "voice": "madina",
                 "register": "neutral"}
VOICE_MAP = {"madina": "uz-UZ-MadinaNeural", "sardor": "uz-UZ-SardorNeural"}
RETRY_REASONS = {"qayta yozish so'raldi"}  # bot "🔄 Qayta" tugmasi shu sababni yuboradi
ACTIVE_STATUSES = {"queued", "running"}


# ---------------------------------------------------------------- dependencies

async def get_arq_pool(request: Request) -> ArqRedis:
    pool = getattr(request.app.state, "arq", None)
    if pool is None:
        pool = await arq.create_pool(RedisSettings.from_dsn(settings.redis_url))
        request.app.state.arq = pool
    return pool


SessionDep = Annotated[AsyncSession, Depends(get_session)]
ArqDep = Annotated[ArqRedis, Depends(get_arq_pool)]


def _uuid(value: str, what: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(404, f"{what} topilmadi") from None


async def _brand(s: AsyncSession, ws_id: uuid.UUID) -> BrandProfile | None:
    return (await s.execute(
        select(BrandProfile).where(BrandProfile.workspace_id == ws_id)
        .order_by(BrandProfile.created_at.desc()).limit(1)
    )).scalar_one_or_none()


async def _workspace_out(s: AsyncSession, ws: Workspace) -> WorkspaceOut:
    bp = await _brand(s, ws.id)
    return WorkspaceOut(id=str(ws.id), name=ws.name, owner_tg_id=ws.owner_tg_id,
                        timezone=ws.timezone, brand_profile=dict(bp.data or {}) if bp else {})


async def _get_ws(s: AsyncSession, workspace_id: str) -> Workspace:
    ws = await s.get(Workspace, _uuid(workspace_id, "workspace"))
    if ws is None:
        raise HTTPException(404, "workspace topilmadi")
    return ws


async def _get_script(s: AsyncSession, script_id: str) -> Script:
    row = await s.get(Script, _uuid(script_id, "script"))
    if row is None:
        raise HTTPException(404, "script topilmadi")
    return row


def _script_out(row: Script, job_id: str | None = None) -> ScriptOut:
    hv = row.hook_variants or {}
    return ScriptOut(
        id=str(row.id), workspace_id=str(row.workspace_id), status=row.status,
        hooks=list(hv.get("hooks") or []), hook_idx=int(hv.get("selected") or 0),
        selected_hook_idx=int(hv.get("selected") or 0),
        body=row.body, cta=row.cta, tts_text=row.tts_text, score=row.score,
        iteration=row.iteration or 0, job_id=job_id,
    )


async def _enqueue_brief(pool: ArqRedis, ws: Workspace, text: str,
                         plan_item: dict | None) -> str:
    job_id = uuid.uuid4().hex
    await jobs.create(job_id, workspace_id=str(ws.id), chat_id=ws.owner_tg_id)
    await pool.enqueue_job("run_brief", str(ws.id), text, job_id, plan_item, _job_id=job_id)
    return job_id


# ---------------------------------------------------------------- workspaces

@router.post("/workspaces", response_model=WorkspaceOut)
async def create_workspace(body: WorkspaceCreate,
                           s: SessionDep) -> WorkspaceOut:
    existing = (await s.execute(
        select(Workspace).where(Workspace.owner_tg_id == body.owner_tg_id).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return await _workspace_out(s, existing)
    ws = Workspace(name=body.name, owner_tg_id=body.owner_tg_id)
    s.add(ws)
    await s.flush()
    s.add(BrandProfile(workspace_id=ws.id, data=dict(DEFAULT_BRAND)))
    await s.commit()
    return await _workspace_out(s, ws)


@router.get("/workspaces", response_model=WorkspaceOut)
async def get_workspace_by_owner(owner_tg_id: int,
                                 s: SessionDep) -> WorkspaceOut:
    ws = (await s.execute(
        select(Workspace).where(Workspace.owner_tg_id == owner_tg_id)
        .order_by(Workspace.created_at).limit(1)
    )).scalar_one_or_none()
    if ws is None:
        raise HTTPException(404, "workspace topilmadi")
    return await _workspace_out(s, ws)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(workspace_id: str,
                        s: SessionDep) -> WorkspaceOut:
    return await _workspace_out(s, await _get_ws(s, workspace_id))


@router.patch("/workspaces/{workspace_id}/brand-profile")
async def update_brand_profile(workspace_id: str, body: BrandProfilePatch,
                               s: SessionDep) -> dict[str, Any]:
    ws = await _get_ws(s, workspace_id)
    fields = body.model_dump()
    # Bot ``pronoun`` ni o'zgartiradi, promptlar ``address_form`` ni o'qiydi — sinxron.
    if "pronoun" in fields:
        fields.setdefault("address_form", fields["pronoun"])
    elif "address_form" in fields:
        fields["pronoun"] = fields["address_form"]
    if fields.get("voice") in VOICE_MAP:
        fields.setdefault("tts_voice", VOICE_MAP[fields["voice"]])
    bp = await _brand(s, ws.id)
    if bp is None:
        bp = BrandProfile(workspace_id=ws.id, data={**DEFAULT_BRAND, **fields})
        s.add(bp)
    else:
        bp.data = {**(bp.data or {}), **fields}  # yangi dict — JSON o'zgarishi aniqlanadi
    await s.commit()
    return dict(bp.data)


# ---------------------------------------------------------------- briefs / jobs

@router.post("/briefs", response_model=BriefOut)
async def create_brief(body: BriefCreate, s: SessionDep,
                       pool: ArqDep) -> BriefOut:
    ws = await _get_ws(s, body.workspace_id)
    job_id = await _enqueue_brief(pool, ws, body.text.strip(), body.plan_item)
    return BriefOut(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str) -> JobOut:
    job = await jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "job topilmadi")
    result = {k: job[k] for k in ("script_id", "video_url", "workspace_id") if job.get(k)}
    result["cost_usd"] = job.get("cost_usd", 0.0)
    return JobOut(job_id=job_id, status=job.get("status", "unknown"),
                  stage=job.get("stage", ""), progress=job.get("progress", 0),
                  result=result, error=job.get("error") or None)


# ---------------------------------------------------------------- scripts / videos

@router.post("/scripts/{script_id}/approve", response_model=ScriptOut)
async def approve_script(script_id: str, body: ScriptApprove,
                         s: SessionDep) -> ScriptOut:
    """Hook tanlovini saqlaydi. Graf to'xtamaydi — yakuniy qaror video tasdiqida."""
    row = await _get_script(s, script_id)
    hv = dict(row.hook_variants or {})
    hooks = list(hv.get("hooks") or [])
    if hooks and body.hook_idx >= len(hooks):
        raise HTTPException(422, "hook_idx noto'g'ri")
    row.hook_variants = {**hv, "selected": body.hook_idx}
    await s.commit()
    job_id = await jobs.job_for_script(script_id)
    if job_id:
        await jobs.update(job_id, hook_idx=body.hook_idx)
    return _script_out(row, job_id)


@router.post("/scripts/{script_id}/reject", response_model=OkOut)
async def reject_script(script_id: str, body: ScriptReject,
                        s: SessionDep,
                        pool: ArqDep) -> OkOut:
    """Rad: graf interrupt'da bo'lsa — ``resume_brief(reject)``; hali ishlayotgan bo'lsa —
    qaror navbatga (worker interrupt'ga yetganda qo'llaydi); graf yo'q bo'lsa — to'g'ridan
    ``taste_memory``. ``retry`` (yoki bot "🔄 Qayta") — shu brif bilan yangi job."""
    row = await _get_script(s, script_id)
    hv = row.hook_variants or {}
    decision = {"decision": "reject", "reason": body.reason,
                "hook_idx": int(hv.get("selected") or 0)}
    job_id = await jobs.job_for_script(script_id)
    job = await jobs.get(job_id) if job_id else None
    detail = "recorded"
    if job and job.get("stage") == "awaiting_approval":
        await pool.enqueue_job("resume_brief", job_id, decision)
        detail = "resumed"
    elif job and job.get("status") in ACTIVE_STATUSES:
        await jobs.set_pending_decision(job_id, decision)
        detail = "pending"
    else:
        hooks = hv.get("hooks") or [""]
        s.add(TasteMemory(workspace_id=row.workspace_id, kind=TasteMemoryKind.REJECTED,
                          text=f"Hook: {hooks[0]}\nBody: {row.body or ''}",
                          reason=body.reason or None))
        row.status = "rejected"
        await s.commit()

    new_job: str | None = None
    if body.retry or body.reason.strip().lower() in RETRY_REASONS:
        plan = await s.get(ContentPlan, row.plan_id)
        brief = ((plan.aida_json or {}) if plan else {}).get("brief")
        if brief:
            ws = await s.get(Workspace, row.workspace_id)
            if ws is not None:
                plan_item = (plan.aida_json or {}).get("plan_item") if plan else None
                new_job = await _enqueue_brief(pool, ws, brief, plan_item)
    return OkOut(detail=detail, job_id=new_job)


@router.post("/scripts/{script_id}/video-approve", response_model=OkOut)
async def approve_video(script_id: str, body: VideoApprove,
                        s: SessionDep,
                        pool: ArqDep) -> OkOut:
    row = await _get_script(s, script_id)
    job_id = await jobs.job_for_script(script_id)
    job = await jobs.get(job_id) if job_id else None
    if not job or job.get("stage") != "awaiting_approval":
        raise HTTPException(409, "video hali tasdiqqa tayyor emas")
    hook_idx = job.get("hook_idx")
    if hook_idx in (None, ""):
        hook_idx = (row.hook_variants or {}).get("selected") or 0
    decision = {"decision": "approve" if body.action == "publish" else "schedule",
                "hook_idx": int(hook_idx), "reason": ""}
    await pool.enqueue_job("resume_brief", job_id, decision)
    return OkOut(detail=body.action, job_id=job_id)


# ---------------------------------------------------------------- reports / jarvis

@router.get("/workspaces/{workspace_id}/daily-report", response_model=DailyReportOut)
async def daily_report(workspace_id: str,
                       s: SessionDep) -> DailyReportOut:
    """Stub (5.8 da Jarvis Reporter to'ldiradi): bugungi lid/vazifa/ssenariy/xarajat soni."""
    ws = await _get_ws(s, workspace_id)
    today = datetime.now(UTC).date()
    start = datetime.combine(today, time.min, tzinfo=UTC)
    now = datetime.now(UTC)

    async def scalar(stmt: Any) -> Any:
        return (await s.execute(stmt)).scalar() or 0

    leads = await scalar(select(func.count(Lead.id)).where(
        Lead.workspace_id == ws.id, Lead.created_at >= start))
    hot = await scalar(select(func.count(Lead.id)).where(
        Lead.workspace_id == ws.id, Lead.created_at >= start, Lead.temperature == "hot"))
    overdue = await scalar(select(func.count(Task.id)).where(
        Task.workspace_id == ws.id, Task.status == "open", Task.due_at < now))
    sales = await scalar(select(func.count(Deal.id)).join(Lead, Deal.lead_id == Lead.id).where(
        Lead.workspace_id == ws.id, Deal.closed_at >= start))
    revenue = await scalar(select(func.sum(Deal.amount)).join(Lead, Deal.lead_id == Lead.id)
                           .where(Lead.workspace_id == ws.id, Deal.closed_at >= start))
    script_rows = (await s.execute(
        select(Script.status, func.count(Script.id))
        .where(Script.workspace_id == ws.id, Script.created_at >= start)
        .group_by(Script.status)
    )).all()
    videos = await scalar(select(func.count(Asset.id)).join(Script, Asset.script_id == Script.id)
                          .where(Script.workspace_id == ws.id, Asset.kind == "video",
                                 Asset.created_at >= start))
    cost_rows = (await s.execute(
        select(CostLog.node, func.sum(CostLog.usd))
        .where(CostLog.workspace_id == ws.id, CostLog.created_at >= start)
        .group_by(CostLog.node)
    )).all()
    by_node = {node: round(float(usd or 0.0), 6) for node, usd in cost_rows}
    return DailyReportOut(
        workspace_id=str(ws.id), date=today.isoformat(), leads=leads, hot=hot, sales=sales,
        revenue=float(revenue or 0.0), overdue=overdue,
        scripts={st: n for st, n in script_rows}, videos=videos,
        cost_usd=round(sum(by_node.values()), 6), cost_by_node=by_node,
    )


DECISION_STATUS = {"yes": "approved", "no": "rejected", "edit": "edit_requested"}


@router.post("/jarvis-actions/{action_id}/decision", response_model=OkOut)
async def jarvis_decision(action_id: str, body: JarvisDecision,
                          s: SessionDep) -> OkOut:
    """Stub: qarorni ``jarvis_action`` ga yozadi (bajarish — Jarvis agenti, 5.5/5.6).

    ``action_id`` — ``jarvis_action.id`` (uuid) yoki bot hisobot tugmalari
    ``report:<workspace_id>:<all|remind>`` (yangi ``report_followup`` harakati yoziladi).
    """
    status = DECISION_STATUS[body.decision]
    try:
        row = await s.get(JarvisAction, uuid.UUID(action_id))
    except ValueError:
        row = None
    if row is not None:
        row.status = status
        row.approved_by = "owner"
        row.payload = {**(row.payload or {}), "decision": body.decision,
                       "comment": body.comment}
        await s.commit()
        return OkOut(detail=status)
    parts = action_id.split(":")
    if len(parts) == 3 and parts[0] == "report":
        ws = await _get_ws(s, parts[1])
        s.add(JarvisAction(workspace_id=ws.id, type=f"report_{parts[2]}",
                           level=JarvisActionLevel.AUTONOMOUS, status=status,
                           approved_by="owner",
                           payload={"source": "daily_report", "action": parts[2],
                                    "decision": body.decision, "comment": body.comment}))
        await s.commit()
        return OkOut(detail=status)
    raise HTTPException(404, "jarvis action topilmadi")
