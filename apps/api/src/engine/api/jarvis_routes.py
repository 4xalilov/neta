"""Jarvis HTTP marshruti: Chatwoot webhook, qo'lda event, tasdiq navbati, kunlik hisobot.

``router`` ``engine.main`` (boshqa agent) tomonidan ``try/except ImportError`` bilan
ulanadi (roadmap 5.x). Shuning uchun bu modul import vaqtida og'ir/tarmoqqa chiqadigan
ishlarni bajarmaydi — CRM/DB ulanishlari faqat ``Depends(get_deps)`` orqali, so'rov
kelganda yaratiladi.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException, Query
from sqlalchemy import select

from engine import db
from engine.integrations import chatwoot as chatwoot_module
from engine.integrations.crm_adapter import get_crm
from engine.jarvis import reporter, supervisor
from engine.jarvis.deps import JarvisDeps
from engine.models.crm import JarvisAction
from engine.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def _redis_notify(*, chat_id, kind: str, payload: dict) -> None:
    """Standart ``notify``: Redis ``tg:notify`` kanaliga JSON e'lon qiladi — Telegram bot
    (BIZNIKI, alohida app) shu kanalni tinglab ega/xodimga xabar yuboradi.

    Redis ulanish xatosi Jarvis oqimini to'xtatmasligi kerak — faqat log yoziladi.
    """
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        try:
            await client.publish(
                "tg:notify",
                json.dumps(
                    {"chat_id": chat_id, "kind": kind, "payload": payload},
                    ensure_ascii=False,
                    default=str,
                ),
            )
        finally:
            await client.aclose()
    except Exception:
        logger.warning("jarvis_routes: tg:notify e'lon qilishda xato", exc_info=True)


def get_deps() -> JarvisDeps:
    """Standart ``JarvisDeps``: ``settings.crm_provider`` bo'yicha CRM, asosiy DB session
    factory, Redis ``tg:notify`` orqali bildirishnoma.

    Testlarda: ``app.dependency_overrides[get_deps] = lambda: fake_deps``.
    """
    return JarvisDeps(crm=get_crm(), session_factory=db.async_session, notify=_redis_notify)


DepsDep = Annotated[JarvisDeps, Depends(get_deps)]
WebhookSecretHeader = Annotated[str | None, Header(alias="X-Webhook-Secret")]


@router.post("/webhooks/chatwoot")
async def chatwoot_webhook(
    background_tasks: BackgroundTasks,
    deps: DepsDep,
    payload: Annotated[dict, Body()],
    x_webhook_secret: WebhookSecretHeader = None,
) -> dict:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if not chatwoot_module.verify_signature(
        raw, x_webhook_secret, settings.chatwoot_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="X-Webhook-Secret noto'g'ri yoki yo'q")

    async def _run() -> None:
        try:
            await chatwoot_module.handle_webhook(
                payload,
                crm=deps.crm,
                session_factory=deps.session_factory,
                notify=deps.notify,
            )
        except Exception:
            logger.exception("jarvis_routes: chatwoot webhookni qayta ishlashda xato")

    background_tasks.add_task(_run)
    return {"status": "accepted"}


@router.post("/v1/jarvis/events")
async def inject_event(event: Annotated[dict, Body()], deps: DepsDep) -> dict:
    """Qo'lda event yuborish (test/dev uchun) — ``jarvis.supervisor.handle_event`` ni to'g'ridan-
    to'g'ri chaqiradi, kutmasdan (webhookdan farqli, background task ishlatilmaydi)."""
    action = await supervisor.handle_event(event, deps)
    if action is None:
        return {"status": "ignored"}
    return {"status": "ok", "action_id": str(action.id), "action_status": action.status}


@router.get("/v1/jarvis/actions")
async def list_actions(
    deps: DepsDep, status: Annotated[str, Query()] = "pending"
) -> list[dict]:
    async with deps.session_factory() as session:
        result = await session.scalars(
            select(JarvisAction).where(JarvisAction.status == status)
        )
        return [
            {
                "id": str(a.id),
                "workspace_id": str(a.workspace_id),
                "type": a.type,
                "level": str(a.level),
                "status": a.status,
                "payload": a.payload,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in result
        ]


@router.post("/v1/jarvis/actions/{action_id}/decision")
async def decide_action(
    action_id: uuid.UUID, body: Annotated[dict, Body()], deps: DepsDep
) -> dict:
    decision = body.get("decision")
    if decision not in ("yes", "no", "edit"):
        raise HTTPException(status_code=422, detail="decision 'yes' | 'no' | 'edit' bo'lishi kerak")
    try:
        action = await supervisor.decide(deps, action_id, decision, body.get("edit_text"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": str(action.id), "status": action.status}


@router.get("/v1/jarvis/report/daily")
async def daily_report(deps: DepsDep, workspace_id: Annotated[uuid.UUID, Query()]) -> dict:
    async with deps.session_factory() as session:
        result = await reporter.build_daily_report(session, workspace_id=workspace_id)
    return {"text": result.text}
