"""CRM dashboard + Jarvis jurnali (docs/06-jarvis-crm.md "CRM web-sahifa (bosqich 5.8)").

Twenty CRM lidlar/vazifalar UI'ni o'zi beradi (docs/07) — bizning tomonimizda faqat:
- ``GET /crm`` — bitta sahifali dashboard (KPI, lidlar oqimi, voronka, kampaniya ROI,
  xodimlar, Jarvis jurnali). Statik JS/CSS ``engine/static/crm/`` dan.
- ``GET /v1/crm/dashboard`` — shu sahifani to'ldiradigan JSON (SQLAlchemy, sqlite ham,
  postgres ham ishlaydi — dialektga xos SQL yo'q, kun bo'yicha guruhlash Python'da).
- ``POST /v1/crm/actions/{action_id}/decision`` — Jarvis jurnalidagi ✅/❌ tugmalari,
  ``engine.jarvis.supervisor.decide`` ga delegatsiya qiladi.
- ``POST /v1/crm/demo-seed`` — "Demo ma'lumot yuklash" tugmasi (faqat
  ``settings.crm_demo_seed_enabled`` yoqilganda; productionda ``false`` bo'lishi kerak).

Vault sahifasidagi statik-fayl pattern (``engine/api/vault_routes.py``) shu yerda ham
qaytariladi: bitta darajali fayl nomi, ``..``/``/`` bloklangan, ``resolve()`` orqali
katalogdan chiqib ketish tekshiriladi.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.api.jarvis_routes import get_deps
from engine.db import get_session
from engine.jarvis import supervisor
from engine.jarvis.deps import JarvisDeps
from engine.jarvis.policy import level_for
from engine.models.content import ContentPlan, CostLog, Post, PostMetrics, Script, Workspace
from engine.models.crm import Campaign, Deal, JarvisAction, Lead, Staff, Task
from engine.settings import settings

router = APIRouter()

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "crm"
_STATIC_CONTENT_TYPES = {
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
}

# docs/02 "CRM + Jarvis": lead.stage sirasi — voronka shu tartibda chiziladi.
FUNNEL_STAGES = ["new", "contacted", "meeting", "deal", "lost"]

# Kampaniya ROI hisoblashda daromad (UZS) va xarajat ($) bitta valyutaga tushirish uchun
# taxminiy kurs. Aniq kurs API'ga ulanish roadmap doirasidan tashqarida — shu doimiy
# yetarli (dashboard "taxminiy ROI" sifatida ko'rsatadi).
UZS_PER_USD = 12700.0

SessionDep = Annotated[AsyncSession, Depends(get_session)]
DepsDep = Annotated[JarvisDeps, Depends(get_deps)]


# --------------------------------------------------------------------------- statik sahifa


@router.get("/crm", response_class=HTMLResponse)
async def crm_dashboard_page() -> HTMLResponse:
    """CRM dashboard sahifasi (roadmap 5.8)."""
    html_path = _STATIC_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="index.html topilmadi")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@router.get("/crm/static/{file_name}")
async def crm_static_file(file_name: str) -> Response:
    """``index.html`` uchun JS/CSS — bitta darajali, ``..`` ga yo'l qo'yilmaydi."""
    if "/" in file_name or "\\" in file_name or file_name in {"..", "."}:
        raise HTTPException(status_code=404, detail="fayl topilmadi")
    candidate = (_STATIC_DIR / file_name).resolve()
    if _STATIC_DIR.resolve() not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="fayl topilmadi")
    content_type = _STATIC_CONTENT_TYPES.get(candidate.suffix.lower(), "application/octet-stream")
    return Response(candidate.read_bytes(), media_type=content_type)


# --------------------------------------------------------------------------- dashboard JSON


async def _resolve_workspace_id(
    session: AsyncSession, workspace_id: uuid.UUID | None
) -> uuid.UUID | None:
    if workspace_id is not None:
        return workspace_id
    return await session.scalar(select(Workspace.id).order_by(Workspace.created_at).limit(1))


_EMPTY_KPIS = {
    "leads_total": 0,
    "leads_today": 0,
    "hot": 0,
    "warm": 0,
    "cold": 0,
    "deals_count": 0,
    "revenue_uzs": 0.0,
    "cost_usd": 0.0,
    "cost_per_lead_usd": 0.0,
    "tasks_open": 0,
    "tasks_overdue": 0,
    "reels_published": 0,
}


def _empty_dashboard(workspace_id: uuid.UUID | None) -> dict[str, Any]:
    return {
        "workspace_id": str(workspace_id) if workspace_id else None,
        "kpis": dict(_EMPTY_KPIS),
        "kpis_prev": dict(_EMPTY_KPIS),
        "leads_by_day": [],
        "funnel": [{"stage": stage, "count": 0} for stage in FUNNEL_STAGES],
        "campaigns": [],
        "staff": [],
        "jarvis_actions": [],
        "pending_actions": 0,
    }


@router.get("/v1/crm/dashboard")
async def crm_dashboard(
    session: SessionDep,
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> JSONResponse:
    """Dashboard uchun bitta JSON: KPI, lidlar oqimi, voronka, kampaniya ROI,
    xodimlar, Jarvis jurnali (docs/06 "CRM web-sahifa")."""
    ws_id = await _resolve_workspace_id(session, workspace_id)
    if ws_id is None:
        return JSONResponse(_empty_dashboard(None))

    now = datetime.now(UTC)
    window_start = now - timedelta(days=days)
    prev_window_start = now - timedelta(days=2 * days)
    today = now.date()

    leads = list(
        (await session.scalars(select(Lead).where(Lead.workspace_id == ws_id))).all()
    )

    # Voronka — konveyerning JORIY holati (bosqichlar bo'yicha), oynaga bog'liq emas.
    funnel_counts = {stage: 0 for stage in FUNNEL_STAGES}
    for lead in leads:
        stage = str(lead.stage)
        if stage in funnel_counts:
            funnel_counts[stage] += 1
    funnel = [{"stage": stage, "count": funnel_counts[stage]} for stage in FUNNEL_STAGES]

    leads_by_day = _bucket_leads_by_day(leads, days=days, today=today)

    lead_ids = [lead.id for lead in leads]
    deals: list[Deal] = []
    if lead_ids:
        deals = list(
            (await session.scalars(select(Deal).where(Deal.lead_id.in_(lead_ids)))).all()
        )

    cost_rows = list(
        (
            await session.scalars(
                select(CostLog).where(CostLog.workspace_id == ws_id)
            )
        ).all()
    )

    tasks = list(
        (await session.scalars(select(Task).where(Task.workspace_id == ws_id))).all()
    )

    posts_published = list(
        (
            await session.scalars(
                select(Post.published_at)
                .join(Script, Post.script_id == Script.id)
                .where(Script.workspace_id == ws_id, Post.published_at.is_not(None))
            )
        ).all()
    )

    # ``kpis`` — joriy ``days`` kunlik oyna; ``kpis_prev`` — undan oldingi xuddi shu
    # uzunlikdagi oyna (delta chiplari uchun, docs/06). ``tasks_open``/``tasks_overdue``
    # uchun bosqichma-bosqich tarix saqlanmagani sababli ``until`` chegarasidan
    # foydalaniladi (taxminiy, lekin izchil — pastdagi ``_compute_kpis`` izohiga qarang).
    kpis = _compute_kpis(
        leads=leads, deals=deals, tasks=tasks, cost_rows=cost_rows,
        posts_published=posts_published, since=window_start, until=now,
    )
    kpis_prev = _compute_kpis(
        leads=leads, deals=deals, tasks=tasks, cost_rows=cost_rows,
        posts_published=posts_published, since=prev_window_start, until=window_start,
    )

    campaigns = await _campaigns_roi(session, ws_id, leads=leads, deals=deals)
    staff = _staff_summary(tasks, await _staff_rows(session, ws_id), now=now)

    actions_result = await session.scalars(
        select(JarvisAction)
        .where(JarvisAction.workspace_id == ws_id)
        .order_by(JarvisAction.created_at.desc())
        .limit(30)
    )
    jarvis_actions = [_action_summary(a) for a in actions_result]

    pending_actions = (
        await session.scalar(
            select(func.count(JarvisAction.id)).where(
                JarvisAction.workspace_id == ws_id, JarvisAction.status == "pending"
            )
        )
        or 0
    )

    return JSONResponse(
        {
            "workspace_id": str(ws_id),
            "kpis": kpis,
            "kpis_prev": kpis_prev,
            "leads_by_day": leads_by_day,
            "funnel": funnel,
            "campaigns": campaigns,
            "staff": staff,
            "jarvis_actions": jarvis_actions,
            "pending_actions": pending_actions,
        }
    )


def _aware(value: datetime | None) -> datetime | None:
    """sqlite ``DateTime(timezone=True)`` tzinfo'ni saqlamaydi (postgresda saqlanadi) —
    Python tomonida ``datetime.now(UTC)`` bilan solishtirishdan oldin UTC deb belgilaymiz."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _as_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    return value.date()


def _in_window(value: datetime | None, since: datetime, until: datetime) -> bool:
    aware = _aware(value)
    return aware is not None and since <= aware < until


def _compute_kpis(
    *,
    leads: list[Lead],
    deals: list[Deal],
    tasks: list[Task],
    cost_rows: list[CostLog],
    posts_published: list[datetime | None],
    since: datetime,
    until: datetime,
) -> dict[str, Any]:
    """KPI to'plami, ``[since, until)`` oynasiga cheklangan (``crm_dashboard`` buni
    joriy va oldingi oyna uchun ikki marta chaqiradi — delta chiplari uchun).

    ``leads_today`` — bu ``until``ning kalendar kuni (joriy oyna uchun bu haqiqatan
    "bugun", oldingi oyna uchun — o'sha davr tugagan kun). ``tasks_open``/
    ``tasks_overdue`` uchun holat tarixi saqlanmagani sababli joriy ``status`` bilan
    ``due_at < until`` taxminidan foydalaniladi — bu aniq tarixiy suratga olish emas,
    faqat ikki oynani solishtirish uchun izchil taxmin.
    """
    leads_in_window = [lead for lead in leads if _in_window(lead.created_at, since, until)]
    leads_total = len(leads_in_window)
    until_date = until.date()
    leads_today = sum(1 for lead in leads_in_window if _as_date(lead.created_at) == until_date)
    hot = sum(1 for lead in leads_in_window if lead.temperature == "hot")
    warm = sum(1 for lead in leads_in_window if lead.temperature == "warm")
    cold = sum(1 for lead in leads_in_window if lead.temperature == "cold")

    won_in_window = [
        d for d in deals
        if d.status == "won" and _in_window(d.closed_at, since, until)
    ]
    deals_count = len(won_in_window)
    revenue_uzs = sum(
        (d.amount or 0.0) for d in won_in_window if (d.currency or "UZS").upper() == "UZS"
    )

    cost_usd = sum(
        (c.usd or 0.0) for c in cost_rows if _in_window(c.created_at, since, until)
    )
    cost_per_lead_usd = (cost_usd / leads_total) if leads_total else 0.0

    tasks_open = sum(1 for t in tasks if t.status == "open")
    tasks_overdue = sum(
        1
        for t in tasks
        if t.status == "open" and _aware(t.due_at) is not None and _aware(t.due_at) < until
    )

    reels_published = sum(1 for p in posts_published if _in_window(p, since, until))

    return {
        "leads_total": leads_total,
        "leads_today": leads_today,
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "deals_count": deals_count,
        "revenue_uzs": revenue_uzs,
        "cost_usd": round(cost_usd, 2),
        "cost_per_lead_usd": round(cost_per_lead_usd, 4),
        "tasks_open": tasks_open,
        "tasks_overdue": tasks_overdue,
        "reels_published": reels_published,
    }


def _bucket_leads_by_day(leads: list[Lead], *, days: int, today: date) -> list[dict[str, Any]]:
    """Kun bo'yicha guruhlash Python'da (dialektga xos SQL date_trunc ishlatilmaydi).

    Aniq ``days`` ta bucket qaytaradi: ``today - (days - 1)`` dan ``today``gacha
    (jami ``days`` kun, bugungi kunni ham qo'shib).
    """
    start_date = today - timedelta(days=max(days, 1) - 1)
    buckets: dict[date, dict[str, int]] = {
        start_date + timedelta(days=i): {"leads": 0, "hot": 0} for i in range(max(days, 1))
    }
    for lead in leads:
        d = _as_date(lead.created_at)
        if d is None or d not in buckets:
            continue
        buckets[d]["leads"] += 1
        if lead.temperature == "hot":
            buckets[d]["hot"] += 1
    return [
        {"date": d.isoformat(), "leads": buckets[d]["leads"], "hot": buckets[d]["hot"]}
        for d in sorted(buckets)
    ]


async def _campaigns_roi(
    session: AsyncSession, ws_id: uuid.UUID, *, leads: list[Lead], deals: list[Deal]
) -> list[dict[str, Any]]:
    campaigns = list(
        (
            await session.scalars(
                select(Campaign).where(Campaign.workspace_id == ws_id).order_by(Campaign.created_at)
            )
        ).all()
    )
    if not campaigns:
        return []

    lead_campaign: dict[uuid.UUID, uuid.UUID | None] = {lead.id: lead.campaign_id for lead in leads}
    leads_per_campaign: dict[uuid.UUID, int] = {}
    for campaign_id in lead_campaign.values():
        if campaign_id is not None:
            leads_per_campaign[campaign_id] = leads_per_campaign.get(campaign_id, 0) + 1

    revenue_per_campaign: dict[uuid.UUID, float] = {}
    deals_per_campaign: dict[uuid.UUID, int] = {}
    for deal in deals:
        if deal.status != "won":
            continue
        campaign_id = lead_campaign.get(deal.lead_id)
        if campaign_id is None:
            continue
        if (deal.currency or "UZS").upper() == "UZS":
            revenue_per_campaign[campaign_id] = revenue_per_campaign.get(campaign_id, 0.0) + (
                deal.amount or 0.0
            )
        deals_per_campaign[campaign_id] = deals_per_campaign.get(campaign_id, 0) + 1

    post_ids = [c.post_id for c in campaigns if c.post_id is not None]
    reach_by_post: dict[uuid.UUID, int] = {}
    if post_ids:
        rows = (
            await session.execute(
                select(PostMetrics.post_id, func.coalesce(func.sum(PostMetrics.reach), 0))
                .where(PostMetrics.post_id.in_(post_ids))
                .group_by(PostMetrics.post_id)
            )
        ).all()
        reach_by_post = {row[0]: int(row[1] or 0) for row in rows}

    out: list[dict[str, Any]] = []
    for c in campaigns:
        revenue_uzs = revenue_per_campaign.get(c.id, 0.0)
        spend_usd = c.spend_usd or 0.0
        roi = ((revenue_uzs / UZS_PER_USD) - spend_usd) / spend_usd if spend_usd > 0 else 0.0
        out.append(
            {
                "id": str(c.id),
                "name": c.name,
                "spend_usd": round(spend_usd, 2),
                "leads": leads_per_campaign.get(c.id, 0),
                "deals": deals_per_campaign.get(c.id, 0),
                "revenue_uzs": revenue_uzs,
                "roi": round(roi, 4),
                "post_reach": reach_by_post.get(c.post_id, 0) if c.post_id else 0,
            }
        )
    return out


async def _staff_rows(session: AsyncSession, ws_id: uuid.UUID) -> list[Staff]:
    return list(
        (
            await session.scalars(
                select(Staff).where(Staff.workspace_id == ws_id).order_by(Staff.created_at)
            )
        ).all()
    )


def _staff_summary(
    tasks: list[Task], staff_rows: list[Staff], *, now: datetime
) -> list[dict[str, Any]]:
    tasks_by_staff: dict[uuid.UUID, list[Task]] = {}
    for t in tasks:
        tasks_by_staff.setdefault(t.staff_id, []).append(t)

    out: list[dict[str, Any]] = []
    for s in staff_rows:
        staff_tasks = tasks_by_staff.get(s.id, [])
        open_tasks = sum(1 for t in staff_tasks if t.status == "open")
        done_tasks = [t for t in staff_tasks if t.status == "done"]
        overdue = sum(
            1
            for t in staff_tasks
            if t.status == "open" and _aware(t.due_at) is not None and _aware(t.due_at) < now
        )
        if done_tasks:
            hours = [
                (t.updated_at - t.created_at).total_seconds() / 3600.0
                for t in done_tasks
                if t.updated_at and t.created_at
            ]
            avg_response_h = round(sum(hours) / len(hours), 2) if hours else 0.0
        else:
            avg_response_h = 0.0
        out.append(
            {
                "id": str(s.id),
                "name": s.name,
                "open_tasks": open_tasks,
                "done_tasks": len(done_tasks),
                "overdue": overdue,
                "avg_response_h": avg_response_h,
            }
        )
    return out


def _action_summary(a: JarvisAction) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "type": a.type,
        "level": str(a.level),
        "status": a.status,
        "payload": a.payload,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "approved_by": a.approved_by,
        "executed_at": a.executed_at.isoformat() if a.executed_at else None,
    }


# --------------------------------------------------------------------------- Jarvis qaroriy


@router.post("/v1/crm/actions/{action_id}/decision")
async def crm_action_decision(
    action_id: uuid.UUID, body: Annotated[dict, Body()], deps: DepsDep
) -> dict[str, str]:
    decision = body.get("decision")
    if decision not in ("yes", "no", "edit"):
        raise HTTPException(
            status_code=422, detail="decision 'yes' | 'no' | 'edit' bo'lishi kerak"
        )
    try:
        action = await supervisor.decide(deps, action_id, decision, body.get("edit_text"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": str(action.id), "status": action.status}


# --------------------------------------------------------------------------- demo seed


@router.post("/v1/crm/demo-seed")
async def crm_demo_seed(
    session: SessionDep,
    workspace_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, Any]:
    """"Demo ma'lumot yuklash" tugmasi: dashboard bo'sh bo'lganda ko'rsatiladi.

    Faqat ``settings.crm_demo_seed_enabled`` yoqilganda ishlaydi (productionda
    ``false`` qilinishi kerak) va workspace'da lid bo'lmaganda idempotent (allaqachon
    seed qilingan/haqiqiy workspace'ga hech narsa yozmaydi).
    """
    if not settings.crm_demo_seed_enabled:
        raise HTTPException(status_code=403, detail="demo-seed o'chirilgan")

    if workspace_id is not None:
        ws = await session.get(Workspace, workspace_id)
        if ws is None:
            raise HTTPException(status_code=404, detail="workspace topilmadi")
    else:
        ws = await session.scalar(select(Workspace).order_by(Workspace.created_at).limit(1))
        if ws is None:
            ws = Workspace(name="Demo IG do'koni", timezone="Asia/Tashkent")
            session.add(ws)
            await session.flush()

    existing_leads = await session.scalar(
        select(func.count(Lead.id)).where(Lead.workspace_id == ws.id)
    )
    if existing_leads:
        return {"skipped": True, "reason": "workspace'da lid allaqachon bor", "leads": existing_leads}

    counts = await _seed_demo_data(session, ws.id)
    await session.commit()
    return {"skipped": False, "workspace_id": str(ws.id), **counts}


async def _seed_demo_data(session: AsyncSession, ws_id: uuid.UUID) -> dict[str, int]:
    rnd = random.Random(42)
    now = datetime.now(UTC)

    # --- xodimlar --------------------------------------------------------
    staff_names = ["Aziz", "Malika", "Bekzod"]
    staff_rows = [Staff(workspace_id=ws_id, name=n, role="sotuv") for n in staff_names]
    session.add_all(staff_rows)
    await session.flush()

    # --- kampaniyalar (3 Reels post + metrikalar) -------------------------
    plan = ContentPlan(
        workspace_id=ws_id, week_start=(now - timedelta(days=21)).date(), aida_json={}, status="published"
    )
    session.add(plan)
    await session.flush()

    reels_topics = [
        ("Bahor kolleksiyasi tanishtiruv", 3_500_000, 41_000),
        ("Mijoz fikri: tez yetkazib berish", 2_100_000, 27_500),
        ("Chegirma aksiyasi 3 kun", 5_200_000, 63_200),
    ]
    scripts = [
        Script(workspace_id=ws_id, plan_id=plan.id, day=i + 1, body=topic, status="published")
        for i, (topic, _, _) in enumerate(reels_topics)
    ]
    session.add_all(scripts)
    await session.flush()

    posts = [
        Post(
            script_id=script.id,
            ig_media_id=f"demo_reel_{i}",
            published_at=now - timedelta(days=21 - i * 7),
            variant="a",
        )
        for i, script in enumerate(scripts)
    ]
    session.add_all(posts)
    await session.flush()

    metrics = [
        PostMetrics(
            post_id=post.id,
            reach=reels_topics[i][2],
            saves=int(reels_topics[i][2] * 0.03),
            shares=int(reels_topics[i][2] * 0.015),
            comments=int(reels_topics[i][2] * 0.006),
            watch_time=rnd.uniform(8.0, 14.0),
            fetched_at=now,
        )
        for i, post in enumerate(posts)
    ]
    session.add_all(metrics)

    campaigns = [
        Campaign(
            workspace_id=ws_id,
            post_id=post.id,
            name=f"Reels: {reels_topics[i][0]}",
            spend_usd=reels_topics[i][1] / UZS_PER_USD * 0.08,
            started_at=post.published_at,
        )
        for i, post in enumerate(posts)
    ]
    session.add_all(campaigns)
    await session.flush()

    # --- lidlar (40 ta, 30 kun bo'ylab) -----------------------------------
    sources = ["ig_dm", "ig_comment", "lead_form", "site"]
    stage_plan = (
        ["new"] * 14
        + ["contacted"] * 9
        + ["meeting"] * 7
        + ["deal"] * 8
        + ["lost"] * 2
    )
    rnd.shuffle(stage_plan)
    uz_names = [
        "Diyor", "Madina", "Shaxzod", "Nilufar", "Javlon", "Sevinch", "Bekzod",
        "Zarina", "Otabek", "Gulnora", "Sanjar", "Kamola", "Rustam", "Feruza",
    ]

    leads: list[Lead] = []
    for i in range(40):
        stage = stage_plan[i]
        temperature = "hot" if stage in ("meeting", "deal") else rnd.choice(["hot", "warm", "warm", "cold"])
        created_at = now - timedelta(
            days=rnd.randint(0, 29), hours=rnd.randint(0, 23), minutes=rnd.randint(0, 59)
        )
        campaign = campaigns[i % len(campaigns)] if rnd.random() < 0.75 else None
        assigned = staff_rows[i % len(staff_rows)]
        leads.append(
            Lead(
                workspace_id=ws_id,
                campaign_id=campaign.id if campaign else None,
                source=rnd.choice(sources),
                name=f"{rnd.choice(uz_names)} {rnd.choice(uz_names)}",
                phone=f"+9989{rnd.randint(10_000_000, 99_999_999)}",
                score=round(rnd.uniform(20, 95), 1),
                temperature=temperature,
                stage=stage,
                assigned_to=assigned.id,
                created_at=created_at,
            )
        )
    session.add_all(leads)
    await session.flush()

    # --- bitimlar (8 ta, UZS) ---------------------------------------------
    deal_leads = [lead for lead in leads if lead.stage == "deal"]
    deal_statuses = ["won", "won", "won", "won", "won", "won", "lost", "open"]
    deals = []
    for lead, status in zip(deal_leads, deal_statuses, strict=False):
        amount = round(rnd.uniform(1_800_000, 12_000_000), -3)
        closed_at = None
        if status != "open":
            # kelajakka chiqib ketmasin (lid yaqinda yaratilgan bo'lishi mumkin) —
            # ``now``dan kamida bir soat oldin bo'lishi kerak.
            closed_at = min(
                lead.created_at + timedelta(days=rnd.randint(1, 5)), now - timedelta(hours=1)
            )
        deals.append(
            Deal(lead_id=lead.id, amount=amount, currency="UZS", status=status, closed_at=closed_at)
        )
    session.add_all(deals)

    # --- vazifalar (12 ta, ba'zilari muddati o'tgan) -----------------------
    tasks = []
    for i in range(12):
        staff = staff_rows[i % len(staff_rows)]
        lead = leads[(i * 3) % len(leads)]
        if i < 4:  # muddati o'tgan, ochiq
            due_at = now - timedelta(days=rnd.randint(1, 4))
            status = "open"
            created_at = due_at - timedelta(days=rnd.randint(1, 3))
            updated_at = created_at
        elif i < 9:  # ochiq, muddati oldinda
            due_at = now + timedelta(days=rnd.randint(1, 6))
            status = "open"
            created_at = now - timedelta(hours=rnd.randint(1, 48))
            updated_at = created_at
        else:  # bajarilgan — xodimlar kartasidagi "o'rtacha javob vaqti" uchun
            # created_at -> updated_at oralig'i 2-30 soat bo'lishi kerak (haqiqiy javob
            # vaqti kabi ko'rinishi uchun).
            created_at = now - timedelta(hours=rnd.randint(48, 240))
            updated_at = created_at + timedelta(hours=rnd.randint(2, 30))
            due_at = created_at + timedelta(hours=rnd.randint(4, 48))
            status = "done"
        tasks.append(
            Task(
                workspace_id=ws_id,
                staff_id=staff.id,
                lead_id=lead.id,
                title=f"{lead.name} bilan bog'lanish",
                due_at=due_at,
                status=status,
                created_at=created_at,
                updated_at=updated_at,
            )
        )
    session.add_all(tasks)

    # --- Jarvis harakatlar jurnali (15 ta) ---------------------------------
    # Har turdagi harakat CRM dashboardida inson o'qiy oladigan xulosaga aylanadi
    # (engine/static/crm/crm.js ``jarvisTitle``) — shuning uchun payload shu funksiya
    # kutgan maydonlarni o'z ichiga oladi va matnlar qatordan-qatorga farq qiladi.
    reply_texts = [
        "Salom! Bahor kolleksiyasi haqida savolingiz bo'lsa yordam beraman.",
        "Xayrli kun! Mahsulot hali mavjud, o'lchamingizni ayting iltimos.",
        "Rahmat murojaat uchun — bugun kechqurun qo'ng'iroq qilsam bo'ladimi?",
        "Chegirma faqat shu hafta amal qiladi, buyurtma bera olasizmi?",
        "Yetkazib berish 1-2 kun ichida, manzilingizni yuboring iltimos.",
    ]
    call_reasons = [
        "narx bo'yicha savol qoldi",
        "o'lcham mos kelmadi, muqobil taklif kerak",
        "buyurtmani tasdiqlash",
        "yetkazib berish sanasini kelishish",
    ]
    task_titles = [
        "Qo'ng'iroq qilish",
        "Narxlar ro'yxatini yuborish",
        "Uchrashuvni tasdiqlash",
        "Chegirma haqida eslatish",
        "Buyurtmani rasmiylashtirish",
    ]

    action_specs = (
        [("send_report", "executed")] * 3
        + [("assign_task", "executed")] * 3
        + [("escalate_owner", "executed")] * 2
        + [("message_lead", "pending")] * 3
        + [("message_lead", "executed")] * 1
        + [("message_lead", "cancelled")] * 1
        + [("call_lead", "pending")] * 1
        + [("call_lead", "executed")] * 1
    )
    jarvis_actions = []
    for i, (action_type, status) in enumerate(action_specs):
        lead = leads[(i * 7 + 3) % len(leads)]
        staff = staff_rows[i % len(staff_rows)]
        created_at = now - timedelta(hours=rnd.randint(1, 96))

        if action_type == "message_lead":
            payload = {
                "lead_id": str(lead.id),
                "lead_name": lead.name,
                "temperature": lead.temperature,
                "reply_text": rnd.choice(reply_texts),
            }
        elif action_type == "call_lead":
            payload = {
                "lead_id": str(lead.id),
                "lead_name": lead.name,
                "reason": rnd.choice(call_reasons),
            }
        elif action_type == "assign_task":
            due_at = created_at + timedelta(hours=rnd.randint(2, 30))
            payload = {
                "staff_id": str(staff.id),
                "staff_name": staff.name,
                "title": rnd.choice(task_titles),
                "due_at": due_at.isoformat(),
                "lead_id": str(lead.id),
            }
        elif action_type == "escalate_owner":
            payload = {
                "staff_id": str(staff.id),
                "staff_name": staff.name,
                "title": rnd.choice(task_titles),
                "hours_overdue": rnd.randint(3, 30),
            }
        else:  # send_report
            payload = {
                "leads": rnd.randint(3, 9),
                "hot": rnd.randint(1, 4),
                "overdue": rnd.randint(0, 3),
            }

        jarvis_actions.append(
            JarvisAction(
                workspace_id=ws_id,
                type=action_type,
                level=str(level_for(action_type)),
                payload=payload,
                status=status,
                approved_by="owner" if status == "executed" and level_for(action_type) == "requires_approval" else None,
                executed_at=created_at + timedelta(minutes=rnd.randint(2, 90)) if status == "executed" else None,
                created_at=created_at,
            )
        )
    session.add_all(jarvis_actions)

    # --- xarajatlar (cost_log) ---------------------------------------------
    nodes = ["script_writer", "critic", "tts", "image_gen", "vision_qa"]
    providers = ["gemini", "claude", "azure", "fal"]
    cost_rows = []
    for _ in range(24):
        cost_rows.append(
            CostLog(
                workspace_id=ws_id,
                node=rnd.choice(nodes),
                provider=rnd.choice(providers),
                tokens_in=rnd.randint(200, 4000),
                tokens_out=rnd.randint(50, 1200),
                usd=round(rnd.uniform(0.03, 1.1), 4),
                created_at=now - timedelta(days=rnd.randint(0, 29), hours=rnd.randint(0, 23)),
            )
        )
    session.add_all(cost_rows)

    return {
        "staff": len(staff_rows),
        "campaigns": len(campaigns),
        "posts": len(posts),
        "leads": len(leads),
        "deals": len(deals),
        "tasks": len(tasks),
        "jarvis_actions": len(jarvis_actions),
        "cost_log": len(cost_rows),
    }


__all__ = ["router"]
