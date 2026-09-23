"""Render node (roadmap 1.6, 1.7): ``render_job`` yozuvi → BullMQ ``render`` navbati → natijani kutish.

Natija ikki manbadan kuzatiladi (qaysi biri avval): BullMQ job hash (``render_queue.get_result``)
va ``render_job`` qatori (Node worker kelajakda DB'ni o'zi yangilashi mumkin). Poll oralig'i
va timeout — ``settings.render_poll_interval_s`` / ``settings.render_timeout_s`` (15 daq).
Xato yoki timeout — ``RuntimeError`` (worker ushlaydi va egaga xato xabari yuboradi).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from engine import render_queue
from engine.integrations import storage
from engine.models import Asset, RenderJob, RenderJobStatus
from engine.settings import settings

from ..state import DayState
from . import _common as c


async def _create_job(state: DayState) -> str:
    ws_id = c.as_uuid(state.get("workspace_id"))
    async with c.session() as s:
        row = RenderJob(workspace_id=ws_id, script_id=c.as_uuid(state.get("script_id")),
                        status=RenderJobStatus.QUEUED, props=state.get("props") or {})
        s.add(row)
        await s.commit()
        return str(row.id)


async def _db_status(job_id: str) -> tuple[str | None, str | None, str | None]:
    async with c.session() as s:
        row = await s.get(RenderJob, c.as_uuid(job_id))
        if row is None:
            return None, None, None
        return row.status, row.video_uri, row.error


async def _finish(state: DayState, job_id: str, status: str, *, video_uri: str | None = None,
                  error: str | None = None, attempts: int = 0) -> None:
    async with c.session() as s:
        row = await s.get(RenderJob, c.as_uuid(job_id))
        if row is not None:
            row.status = status
            row.video_uri = video_uri or row.video_uri
            row.error = error
            row.attempts = max(row.attempts or 0, attempts)
        script_id = c.as_uuid(state.get("script_id"))
        if video_uri and script_id is not None:
            s.add(Asset(script_id=script_id, kind="video", uri=video_uri,
                        meta={"render_job_id": job_id,
                              "composition": state.get("composition", "ReelsBasic")}))
        await s.commit()


async def wait_for_render(job_id: str) -> render_queue.RenderResult:
    deadline = time.monotonic() + settings.render_timeout_s
    polls = 0
    while True:
        polls += 1
        res = await render_queue.get_result(job_id)
        if res.status in ("done", "failed"):
            return res
        db_status, db_uri, db_err = await _db_status(job_id)
        if db_status == RenderJobStatus.DONE and db_uri:
            return render_queue.RenderResult("done", video_uri=db_uri)
        if db_status == RenderJobStatus.FAILED:
            return render_queue.RenderResult("failed", error=db_err or "render failed")
        if time.monotonic() >= deadline:
            return render_queue.RenderResult(
                "failed", error=f"render timeout ({settings.render_timeout_s:.0f}s, {polls} poll)")
        await asyncio.sleep(settings.render_poll_interval_s)


async def render(state: DayState) -> dict[str, Any]:
    ws = state.get("workspace_id", "")
    job_id = state.get("render_job_id") or await _create_job(state)
    output_key = storage.key_for(ws, "video", "mp4")
    await render_queue.enqueue_render(
        job_id=job_id, workspace_id=ws, composition=state.get("composition", "ReelsBasic"),
        props=state.get("props") or {}, output_key=output_key,
    )
    res = await wait_for_render(job_id)
    if res.status != "done" or not res.video_uri:
        await _finish(state, job_id, RenderJobStatus.FAILED, error=res.error)
        raise RuntimeError(f"render_job {job_id} muvaffaqiyatsiz: {res.error}")
    await _finish(state, job_id, RenderJobStatus.DONE, video_uri=res.video_uri, attempts=1)
    return {
        "render_job_id": job_id,
        "video_uri": res.video_uri,
        "video_url": storage.public_url(res.video_uri),
        "cost_usd": c.run_cost(state),
    }
