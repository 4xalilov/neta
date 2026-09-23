"""Brif job holati Redis'da (API o'qiydi, worker yozadi) + ``tg:notify`` pub/sub.

Kalitlar:
- ``job:{job_id}`` (hash): ``status`` (queued|running|done|failed), ``stage``, ``progress``,
  ``workspace_id``, ``thread_id``, ``script_id``, ``video_url``, ``error``, ``cost_usd``,
  ``chat_id``, ``hook_idx``, ``updated_at``. ``job_id == thread_id`` (LangGraph).
- ``script_job:{script_id}`` → ``job_id`` (bot script_id bilan murojaat qiladi).
- ``job_pending:{job_id}`` → JSON qaror: graf hali interrupt'ga yetmagan paytda kelgan rad
  (worker interrupt'ga yetganda darhol shu qaror bilan davom ettiradi).

``status == "done"`` + ``stage == "awaiting_approval"`` — video tayyor, ega qarorini kutmoqda
(bot polling ``done`` da to'xtaydi). Keyingi bosqichlar: ``published`` / ``scheduled`` /
``rejected``.

``tg:notify`` formati (apps/bot/bot/notify.py)::

    {"chat_id": int, "kind": "script|video|report|approval|error", "payload": {...}}
"""
from __future__ import annotations

import json
import time
from typing import Any

from redis.asyncio import Redis

from engine.settings import settings

NOTIFY_CHANNEL = "tg:notify"
JOB_TTL_S = 7 * 86_400

STAGE_PROGRESS = {
    "queued": 0,
    "writer": 10,
    "critics": 30,
    "script_ready": 40,
    "asset_gen": 50,
    "render": 70,
    "vision_qa": 90,
    "awaiting_approval": 100,
    "published": 100,
    "scheduled": 100,
    "rejected": 100,
}

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def set_redis(client: Redis | None) -> None:
    """Testlar: ``fakeredis.aioredis.FakeRedis(decode_responses=True)``."""
    global _redis
    _redis = client


def _key(job_id: str) -> str:
    return f"job:{job_id}"


async def create(job_id: str, *, workspace_id: str, chat_id: int | None = None) -> None:
    r = get_redis()
    await r.hset(_key(job_id), mapping={
        "status": "queued", "stage": "queued", "progress": 0,
        "workspace_id": workspace_id, "thread_id": job_id,
        "chat_id": chat_id or 0, "updated_at": time.time(),
    })
    await r.expire(_key(job_id), JOB_TTL_S)


async def update(job_id: str, **fields: Any) -> None:
    if "stage" in fields and "progress" not in fields:
        fields["progress"] = STAGE_PROGRESS.get(fields["stage"], 0)
    clean = {k: ("" if v is None else v) for k, v in fields.items()}
    clean["updated_at"] = time.time()
    r = get_redis()
    await r.hset(_key(job_id), mapping={k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                                        for k, v in clean.items()})
    await r.expire(_key(job_id), JOB_TTL_S)
    if fields.get("script_id"):
        await r.set(f"script_job:{fields['script_id']}", job_id, ex=JOB_TTL_S)


async def get(job_id: str) -> dict[str, Any] | None:
    raw = await get_redis().hgetall(_key(job_id))
    if not raw:
        return None
    out: dict[str, Any] = dict(raw)
    for k in ("progress", "chat_id"):
        try:
            out[k] = int(float(out.get(k) or 0))
        except ValueError:
            out[k] = 0
    try:
        out["cost_usd"] = float(out.get("cost_usd") or 0.0)
    except ValueError:
        out["cost_usd"] = 0.0
    return out


async def job_for_script(script_id: str) -> str | None:
    return await get_redis().get(f"script_job:{script_id}")


async def set_pending_decision(job_id: str, decision: dict[str, Any]) -> None:
    await get_redis().set(f"job_pending:{job_id}", json.dumps(decision), ex=JOB_TTL_S)


async def pop_pending_decision(job_id: str) -> dict[str, Any] | None:
    r = get_redis()
    raw = await r.get(f"job_pending:{job_id}")
    if raw is None:
        return None
    await r.delete(f"job_pending:{job_id}")
    return json.loads(raw)


async def notify(chat_id: int | None, kind: str, payload: dict[str, Any]) -> None:
    """``tg:notify`` kanaliga xabar (chat_id bo'lmasa jim o'tadi)."""
    if not chat_id:
        return
    msg = json.dumps({"chat_id": int(chat_id), "kind": kind, "payload": payload},
                     ensure_ascii=False, default=str)
    await get_redis().publish(NOTIFY_CHANNEL, msg)
