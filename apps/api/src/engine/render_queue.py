"""Remotion render navbati (BullMQ, Node worker ``apps/render``) uchun abstraksiya.

Navbat: ``settings.render_queue`` (``"render"``), job nomi ``"render"``, job id =
``render_job.id`` (idempotent qayta enqueue). Job data (Node worker kutgan format)::

    {"jobId": str, "workspaceId": str, "composition": "ReelsBasic"|"ReelsParallax",
     "props": {...Remotion props...}, "outputKey": "ws/<ws>/video/<uuid>.mp4"}

Natija BullMQ job hash'idan (``bull:render:<id>``) o'qiladi: ``finishedOn`` +
``returnvalue`` (JSON; ``uri``/``videoUri``/``outputKey`` kalitlaridan biri) yoki
``failedReason``. ``removeOnComplete`` 7 kun — natija o'qilguncha hash o'chmasin.

Enqueue uchun ``bullmq`` (pypi) ``Queue.add`` ishlatiladi. Versiya ``bullmq>=2,<3`` — chunki
arq ``redis<6`` talab qiladi, ``bullmq`` 3.x esa ``redis>=6``. 2.15 → Node ``bullmq`` 6.3.8
(apps/render) moslik qo'lda tekshirilgan (redis-server 7, completed + UnrecoverableError
yo'llari). Testlar: ``set_fake_queue(FakeRenderQueue())``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from engine.settings import settings

logger = logging.getLogger(__name__)

Status = Literal["pending", "running", "done", "failed"]


@dataclass
class RenderResult:
    status: Status
    video_uri: str | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class RenderQueue(Protocol):
    async def enqueue(self, job_id: str, data: dict[str, Any]) -> None: ...

    async def get_result(self, job_id: str) -> RenderResult: ...


def _video_uri_from(returnvalue: Any, output_key: str | None) -> str | None:
    if isinstance(returnvalue, dict):
        for key in ("videoUri", "uri", "video_uri"):
            if returnvalue.get(key):
                return str(returnvalue[key])
        output_key = returnvalue.get("outputKey") or output_key
    if output_key:
        return f"s3://{settings.s3_bucket}/{output_key}"
    return None


class BullMQRenderQueue:
    """Haqiqiy navbat: Redis'dagi BullMQ (``bullmq`` pypi paketi)."""

    def __init__(self, redis_url: str | None = None, name: str | None = None) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._name = name or settings.render_queue
        self._queue: Any = None

    def _q(self) -> Any:
        if self._queue is None:
            from bullmq import Queue

            self._queue = Queue(self._name, {"connection": self._redis_url})
        return self._queue

    async def enqueue(self, job_id: str, data: dict[str, Any]) -> None:
        await self._q().add("render", data, {
            "jobId": job_id,
            "attempts": 2,
            "backoff": {"type": "exponential", "delay": 10_000},
            "removeOnComplete": {"age": 7 * 86_400},
            "removeOnFail": {"age": 14 * 86_400},
        })

    async def get_result(self, job_id: str) -> RenderResult:
        q = self._q()
        raw: dict[str, Any] = await q.client.hgetall(f"{q.prefix}:{self._name}:{job_id}")
        if not raw:
            return RenderResult("pending")
        data = {}
        try:
            data = json.loads(raw.get("data") or "{}")
        except ValueError:
            pass
        output_key = data.get("outputKey")
        if raw.get("finishedOn"):
            if raw.get("failedReason") and not raw.get("returnvalue"):
                return RenderResult("failed", error=raw["failedReason"])
            try:
                rv = json.loads(raw.get("returnvalue") or "null")
            except ValueError:
                rv = None
            return RenderResult("done", video_uri=_video_uri_from(rv, output_key),
                                meta=rv if isinstance(rv, dict) else {})
        if raw.get("processedOn"):
            return RenderResult("running")
        return RenderResult("pending")

    async def close(self) -> None:
        if self._queue is not None:
            await self._queue.close()
            self._queue = None


class FakeRenderQueue:
    """Testlar uchun: enqueue qilingan joblarni saqlaydi, darhol (yoki ``pending_polls``
    so'rovdan keyin) ``done`` qaytaradi. ``fail=True`` — xato simulyatsiyasi."""

    def __init__(self, *, pending_polls: int = 0, fail: bool = False) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.polls: dict[str, int] = {}
        self.pending_polls = pending_polls
        self.fail = fail

    async def enqueue(self, job_id: str, data: dict[str, Any]) -> None:
        self.jobs[job_id] = data

    async def get_result(self, job_id: str) -> RenderResult:
        if job_id not in self.jobs:
            return RenderResult("pending")
        n = self.polls.get(job_id, 0) + 1
        self.polls[job_id] = n
        if n <= self.pending_polls:
            return RenderResult("running")
        if self.fail:
            return RenderResult("failed", error="fake render failed")
        key = self.jobs[job_id].get("outputKey")
        return RenderResult("done", video_uri=_video_uri_from(None, key))


_queue: RenderQueue | None = None


def get_queue() -> RenderQueue:
    global _queue
    if _queue is None:
        _queue = BullMQRenderQueue()
    return _queue


def set_fake_queue(queue: RenderQueue | None = None) -> RenderQueue:
    """Navbatni almashtiradi (default — yangi ``FakeRenderQueue``); o'rnatilganini qaytaradi."""
    global _queue
    _queue = queue if queue is not None else FakeRenderQueue()
    return _queue


def clear_fake_queue() -> None:
    global _queue
    _queue = None


async def enqueue_render(*, job_id: str, workspace_id: str, composition: str,
                         props: dict[str, Any], output_key: str) -> dict[str, Any]:
    data = {
        "jobId": job_id,
        "workspaceId": workspace_id,
        "composition": composition,
        "props": props,
        "outputKey": output_key,
    }
    await get_queue().enqueue(job_id, data)
    return data


async def get_result(job_id: str) -> RenderResult:
    return await get_queue().get_result(job_id)
