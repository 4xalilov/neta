"""arq worker: brif → DaySubgraph (approval interrupt'gacha) → Telegram xabarlari.

Ishga tushirish: ``arq engine.worker.WorkerSettings`` (docker-compose ``worker`` servisi).

Joblar:
- ``run_brief(ctx, workspace_id, brief, thread_id, plan_item=None)`` — grafni boshidan
  interrupt'gacha yuritadi. ``thread_id`` == API ``job_id``.
- ``resume_brief(ctx, thread_id, decision)`` — ``Command(resume=decision)`` bilan davom.

``tg:notify`` xabarlari (``engine.jobs.notify``): ``script`` (kritiklardan o'tgach),
``video`` (interrupt — ega qarori kutilmoqda), ``error`` (istalgan xato).
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, ClassVar

from arq.connections import RedisSettings
from langgraph.types import Command
from sqlalchemy import select

from engine import cost_sink, db, jobs
from engine.graphs.day_subgraph import close_graph, get_graph
from engine.models import BrandProfile, ReferenceVideo, TasteMemory, Workspace
from engine.settings import settings

logger = logging.getLogger(__name__)

NODE_NEXT_STAGE = {
    "writer": "critics",
    "collect": "writer",       # halqa davom etsa; script_ready bo'lsa → asset_gen
    "asset_gen": "render",
    "render": "vision_qa",
    "vision_qa": "approval",
}


# ---------------------------------------------------------------- kontekst

def _taste_line(row: TasteMemory) -> str:
    label = {"rejected": "RAD", "approved": "TASDIQ"}.get(str(row.kind), "IZOH")
    reason = f" — sabab: {row.reason}" if row.reason else ""
    return f"{label}{reason}: {row.text[:200]}"


async def load_context(workspace_id: str) -> dict[str, Any]:
    """Workspace, brand_profile, taste top-k (hozircha eng so'nggilari; pgvector — 3.4),
    referens strukturalar."""
    ws_id = uuid.UUID(workspace_id)
    async with db.async_session() as s:
        ws = await s.get(Workspace, ws_id)
        if ws is None:
            raise ValueError(f"workspace topilmadi: {workspace_id}")
        bp = (await s.execute(
            select(BrandProfile).where(BrandProfile.workspace_id == ws_id)
            .order_by(BrandProfile.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        taste_rows = (await s.execute(
            select(TasteMemory).where(TasteMemory.workspace_id == ws_id)
            .order_by(TasteMemory.created_at.desc()).limit(settings.taste_top_k)
        )).scalars().all()
        refs = (await s.execute(
            select(ReferenceVideo.structure_json).where(ReferenceVideo.workspace_id == ws_id)
            .order_by(ReferenceVideo.created_at.desc()).limit(3)
        )).scalars().all()
    return {
        "chat_id": ws.owner_tg_id or settings.owner_tg_id,
        "brand_profile": dict(bp.data or {}) if bp else {},
        "taste": [_taste_line(r) for r in taste_rows],
        "references": [r for r in refs if r],
    }


# ---------------------------------------------------------------- xabar payloadlari

def script_payload(values: dict[str, Any]) -> dict[str, Any]:
    script = values.get("script") or {}
    scores = {r.get("critic"): r.get("score") for r in values.get("best_reviews") or []}
    return {
        "script_id": values.get("script_id"),
        "hooks": script.get("hooks", []),
        "selected_idx": values.get("best_hook_idx", 0),
        "body": script.get("body", ""),
        "cta": script.get("cta", ""),
        "uz_score": scores.get("uz", "-"),
        "brand_score": scores.get("brand", "-"),
        "hook_score": scores.get("hook", "-"),
        "iteration": values.get("iteration", 0),
        "warnings": list(values.get("errors") or []),
    }


def vision_qa_summary(vqa: dict[str, Any]) -> str:
    if not vqa:
        return "-"
    issues = vqa.get("issues") or []
    if vqa.get("pass") and not issues:
        return "OK ✅"
    head = "OK ⚠️" if vqa.get("pass") else "Muammo ❌"
    detail = "; ".join(f"#{i.get('frame', 0) + 1}: {i.get('issue', '')}" for i in issues[:3])
    return f"{head} {detail}".strip()


def video_payload(intr: dict[str, Any]) -> dict[str, Any]:
    cost = float(intr.get("cost_usd") or 0.0)
    duration = intr.get("duration_s")
    return {
        "script_id": intr.get("script_id"),
        "video_url": intr.get("video_url"),
        "cost": f"{cost:.2f}",
        "cost_usd": cost,
        "vision_qa": vision_qa_summary(intr.get("vision_qa") or {}),
        "vision_qa_detail": intr.get("vision_qa") or {},
        "duration": round(duration) if isinstance(duration, (int, float)) else "-",
        "hooks": intr.get("hooks", []),
        "selected_idx": intr.get("best_hook_idx", 0),
        "warnings": intr.get("errors", []),
    }


# ---------------------------------------------------------------- graf yurituvchi

async def _drive(graph: Any, graph_input: Any, thread_id: str, chat_id: int | None) -> str:
    """Grafni stream qiladi, job holati va xabarlarni yangilaydi.

    Qaytaradi: ``"awaiting_approval"`` | ``"published"`` | ``"scheduled"`` | ``"rejected"``.
    """
    config = {"configurable": {"thread_id": thread_id}}
    interrupted = False
    async for chunk in graph.astream(graph_input, config, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "__interrupt__":
                intr = update[0].value if update else {}
                payload = video_payload(intr)
                await jobs.update(thread_id, status="done", stage="awaiting_approval",
                                  video_url=payload["video_url"] or "",
                                  cost_usd=payload["cost_usd"])
                await jobs.notify(chat_id, "video", payload)
                interrupted = True
                continue
            update = update or {}
            fields: dict[str, Any] = {}
            if update.get("script_id"):
                fields["script_id"] = update["script_id"]
            if update.get("video_url"):
                fields["video_url"] = update["video_url"]
            if update.get("cost_usd") is not None:
                fields["cost_usd"] = update["cost_usd"]
            if node == "collect" and update.get("script_ready"):
                values = (await graph.aget_state(config)).values
                await jobs.update(thread_id, stage="asset_gen",
                                  script_id=values.get("script_id"), **fields)
                await jobs.notify(chat_id, "script", script_payload(values))
                continue
            if node == "approval" and not update.get("approved"):
                await jobs.update(thread_id, status="done", stage="rejected", **fields)
                return "rejected"
            if node == "publish":
                stage = update.get("publish_status") or "published"
                stage = "published" if stage == "approved" else stage
                await jobs.update(thread_id, status="done", stage=stage, **fields)
                return stage
            if node in NODE_NEXT_STAGE:
                await jobs.update(thread_id, stage=NODE_NEXT_STAGE[node], **fields)
            elif fields:
                await jobs.update(thread_id, **fields)
    if interrupted:
        # Ega video tayyor bo'lmasdan rad etgan bo'lsa (API ``job_pending`` ga yozgan).
        pending = await jobs.pop_pending_decision(thread_id)
        if pending is not None:
            return await _drive(graph, Command(resume=pending), thread_id, chat_id)
        return "awaiting_approval"
    values = (await graph.aget_state(config)).values
    stage = values.get("publish_status") or "done"
    return "published" if stage == "approved" else stage


async def _fail(thread_id: str, chat_id: int | None, exc: BaseException) -> dict[str, Any]:
    logger.exception("brief %s xato bilan tugadi", thread_id, exc_info=exc)
    err = f"{type(exc).__name__}: {exc}"[:500]
    await jobs.update(thread_id, status="failed", error=err)
    await jobs.notify(chat_id, "error", {"job_id": thread_id, "error": err})
    return {"status": "failed", "error": err}


async def run_brief(ctx: dict, workspace_id: str, brief: str, thread_id: str,
                    plan_item: dict | None = None) -> dict[str, Any]:
    chat_id: int | None = None
    try:
        await jobs.update(thread_id, status="running", stage="writer",
                          workspace_id=workspace_id)
        context = await load_context(workspace_id)
        chat_id = context.pop("chat_id")
        await jobs.update(thread_id, chat_id=chat_id or 0)
        state = {
            "workspace_id": workspace_id,
            "thread_id": thread_id,
            "brief": brief,
            "day": 0,
            "plan_item": plan_item or {"aida": "attention", "format": "reels"},
            "iteration": 0,
            "started_at": time.time(),
            **context,
        }
        graph = await get_graph()
        stage = await _drive(graph, state, thread_id, chat_id)
    except Exception as exc:  # noqa: BLE001 — har qanday xato egaga xabar qilinadi
        return await _fail(thread_id, chat_id, exc)
    return {"status": "done", "stage": stage}


async def resume_brief(ctx: dict, thread_id: str, decision: dict[str, Any]) -> dict[str, Any]:
    job = await jobs.get(thread_id) or {}
    chat_id = job.get("chat_id") or None
    try:
        graph = await get_graph()
        snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        if not snapshot.next:
            logger.warning("resume_brief: %s interrupt'da emas, o'tkazib yuborildi", thread_id)
            return {"status": "noop"}
        await jobs.update(thread_id, status="running", stage="publish")
        stage = await _drive(graph, Command(resume=decision), thread_id, chat_id)
    except Exception as exc:  # noqa: BLE001 — har qanday xato egaga xabar qilinadi
        return await _fail(thread_id, chat_id, exc)
    return {"status": "done", "stage": stage}


# ---------------------------------------------------------------- arq sozlamalari

async def startup(ctx: dict) -> None:
    cost_sink.install()
    await get_graph()


async def shutdown(ctx: dict) -> None:
    await close_graph()
    cost_sink.uninstall()


class WorkerSettings:
    functions: ClassVar[list] = [run_brief, resume_brief]
    # Placeholder: 4.4 analytics (48h), 5.8 kunlik hisobot 09:00 — arq.cron(...) bilan.
    cron_jobs: ClassVar[list] = []
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 4
    job_timeout = 30 * 60  # render 15 daq + LLM/TTS/FLUX
    keep_result = 3600
