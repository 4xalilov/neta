"""Jarvis supervisor: eventni tegishli funksiyaga yo'naltiradi, har taklif qilingan
harakatni ``policy.level_for`` orqali tekshiradi va ``jarvis_action`` jurnaliga yozadi.

TODO (5.5, docs/03 roadmap): hozircha LangGraph ishlatilmaydi — supervisor oddiy async
funksiyalar zanjiri (docs/07-open-source-foundations.md "Nima o'zimiz yozamiz": "Jarvis
miyasi ... BIZNIKI"). Keyingi bosqichda shu mantiq LangGraph supervisor grafiga
(``requires_approval`` uchun ``interrupt()`` bilan) o'raladi — tashqi interfeys
(``handle_event``/``decide``) o'zgarmasligi kerak, faqat ichki amalga oshirish LangGraph
node'lariga ko'chadi.

Oqim (docs/06 "Policy gate"):
- ``autonomous`` -> ``jarvis_action`` yoziladi va shu zahoti bajariladi (``status=executed``).
- ``requires_approval`` -> ``jarvis_action`` ``status=pending`` bilan yoziladi, ``notify(...)``
  orqali egaga tasdiq so'raladi; keyin ``decide()`` bajaradi yoki bekor qiladi.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.jarvis import lead_scorer, reporter, task_manager
from engine.jarvis.deps import JarvisDeps
from engine.jarvis.policy import Level, level_for
from engine.models.crm import JarvisAction, Task

logger = logging.getLogger(__name__)

# notify(chat_id=OWNER_CHAT_KEY, ...) — chaqiruvchi (masalan jarvis_routes) buni haqiqiy
# Telegram chat id'ga (settings.owner_tg_id) aylantiradi.
OWNER_CHAT_KEY = "owner"

ExecuteFn = Callable[[AsyncSession], Awaitable[None]]


def _to_uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


# ---------------------------------------------------------------- policy gate + jurnal


async def propose_action(
    deps: JarvisDeps,
    *,
    workspace_id: Any,
    action_type: str,
    payload: dict[str, Any],
    execute: ExecuteFn,
) -> JarvisAction:
    """Harakatni ``policy.level_for`` orqali tekshiradi, ``jarvis_action`` ga yozadi.

    ``execute`` — faqat avtonom bo'lsa (yoki keyin ``decide("yes")`` bilan) chaqiriladi;
    o'sha DB tranzaksiyasi ichida ishlaydi, shuning uchun ``Task``/boshqa yozuvlarni
    xavfsiz o'zgartirishi mumkin.
    """
    level = level_for(action_type)
    ws_id = _to_uuid(workspace_id)

    async with deps.session_factory() as session:
        action = JarvisAction(
            workspace_id=ws_id,
            type=action_type,
            level=level,
            payload=payload,
            status="pending",
        )
        session.add(action)
        await session.flush()
        action_id = action.id

        if level == Level.AUTONOMOUS:
            await execute(session)
            action.status = "executed"
            action.executed_at = deps.now()
            await session.commit()
        else:
            await session.commit()
            await deps.notify(
                chat_id=OWNER_CHAT_KEY,
                kind="approval",
                payload={"action_id": str(action_id), "type": action_type, **payload},
            )

    async with deps.session_factory() as session:
        result = await session.get(JarvisAction, action_id)
        assert result is not None
        return result


# ---------------------------------------------------------------- requires_approval bajaruvchilari


async def _execute_message_lead(deps: JarvisDeps, session: AsyncSession, payload: dict) -> None:
    conversation_id = payload.get("conversation_id")
    text = payload.get("reply_text") or payload.get("text")
    if not text:
        text = "Salom! Men Jarvis, virtual yordamchiman. Qanday yordam bera olaman?"
    if conversation_id is not None:
        from engine.integrations import chatwoot as chatwoot_module

        await chatwoot_module.reply(conversation_id, text)


async def _execute_call_lead(deps: JarvisDeps, session: AsyncSession, payload: dict) -> None:
    # bosqich 6 (LiveKit) — hozircha faqat log
    logger.info("jarvis.supervisor: call_lead hali amalga oshirilmagan (bosqich 6): %r", payload)


async def _execute_change_deal(deps: JarvisDeps, session: AsyncSession, payload: dict) -> None:
    lead_id = payload.get("lead_id")
    stage = payload.get("stage")
    if lead_id and stage:
        await deps.crm.update_stage(lead_id, stage)


_APPROVAL_EXECUTORS: dict[
    str, Callable[[JarvisDeps, AsyncSession, dict], Awaitable[None]]
] = {
    "message_lead": _execute_message_lead,
    "call_lead": _execute_call_lead,
    "change_deal": _execute_change_deal,
}


async def decide(
    deps: JarvisDeps, action_id: Any, decision: str, edit_text: str | None = None
) -> JarvisAction:
    """Ega tasdig'i: ``"yes"`` -> bajaradi, ``"no"`` -> bekor qiladi, ``"edit"`` -> matnni
    yangilab bajaradi (docs/06: "Ha / Yo'q / Tahrirlash")."""
    action_id = _to_uuid(action_id)
    async with deps.session_factory() as session:
        action = await session.get(JarvisAction, action_id)
        if action is None:
            raise ValueError(f"jarvis_action topilmadi: {action_id}")
        if action.status != "pending":
            return action

        if decision == "no":
            action.status = "cancelled"
            await session.commit()
            return action

        payload = dict(action.payload or {})
        if decision == "edit" and edit_text:
            payload["reply_text"] = edit_text
            action.payload = payload

        executor = _APPROVAL_EXECUTORS.get(action.type)
        if executor is not None:
            await executor(deps, session, payload)

        action.status = "executed"
        action.executed_at = deps.now()
        await session.commit()
        return action


async def batch_approve(deps: JarvisDeps, workspace_id: Any) -> list[JarvisAction]:
    """docs/06: "Ega bitta xabar bilan 'hammasiga ha' desa — batch approve"."""
    ws_id = _to_uuid(workspace_id)
    async with deps.session_factory() as session:
        result = await session.scalars(
            select(JarvisAction).where(
                JarvisAction.workspace_id == ws_id, JarvisAction.status == "pending"
            )
        )
        pending_ids = [a.id for a in result]

    return [await decide(deps, action_id, "yes") for action_id in pending_ids]


# ---------------------------------------------------------------- event handlers


async def _handle_lead_created(event: dict, deps: JarvisDeps) -> JarvisAction:
    workspace_id = event["workspace_id"]
    lead_id = event["lead_id"]

    scored = await lead_scorer.score_lead(deps.crm, lead_id, workspace_id=str(workspace_id))

    payload = {
        "lead_id": lead_id,
        "name": event.get("name"),
        "phone": event.get("phone"),
        "source": event.get("source"),
        "conversation_id": event.get("conversation_id"),
        "text": event.get("text"),
        "temperature": scored["temperature"],
        "score": scored["score"],
        "reason": scored["reason"],
        "next_step": scored["next_step"],
    }

    async def execute(session: AsyncSession) -> None:  # requires_approval — bu yerda chaqirilmaydi
        return None

    return await propose_action(
        deps, workspace_id=workspace_id, action_type="message_lead", payload=payload,
        execute=execute,
    )


async def _handle_lead_reply(event: dict, deps: JarvisDeps) -> JarvisAction:
    workspace_id = event["workspace_id"]
    payload = {
        "lead_id": event["lead_id"],
        "conversation_id": event.get("conversation_id"),
        "text": event.get("text"),
    }

    async def execute(session: AsyncSession) -> None:
        return None

    return await propose_action(
        deps, workspace_id=workspace_id, action_type="message_lead", payload=payload,
        execute=execute,
    )


async def _handle_task_overdue(event: dict, deps: JarvisDeps) -> JarvisAction:
    task_id = _to_uuid(event["task_id"])
    escalate = bool(event.get("escalate"))

    async with deps.session_factory() as session:
        task = await session.get(Task, task_id)
        if task is None:
            raise ValueError(f"jarvis.supervisor: vazifa topilmadi: {task_id}")
        workspace_id = task.workspace_id
        payload = {
            "task_id": str(task_id),
            "title": task.title,
            "staff_id": str(task.staff_id),
            "due_at": task.due_at.isoformat() if task.due_at else None,
        }

    if escalate:
        action_type = "escalate_owner"

        async def execute(session: AsyncSession) -> None:
            t = await session.get(Task, task_id)
            assert t is not None
            await task_manager.mark_escalated(session, t, deps.now())
            await deps.notify(chat_id=OWNER_CHAT_KEY, kind="escalation", payload=payload)
    else:
        action_type = "remind_staff"

        async def execute(session: AsyncSession) -> None:
            t = await session.get(Task, task_id)
            assert t is not None
            await task_manager.mark_reminded(session, t)
            await deps.notify(chat_id=payload["staff_id"], kind="reminder", payload=payload)

    return await propose_action(
        deps, workspace_id=workspace_id, action_type=action_type, payload=payload,
        execute=execute,
    )


async def _handle_cron_daily_report(event: dict, deps: JarvisDeps) -> JarvisAction:
    workspace_id = event["workspace_id"]
    company = event.get("company", "kompaniya")

    async with deps.session_factory() as session:
        report = await reporter.build_daily_report(
            session, workspace_id=_to_uuid(workspace_id), company=company
        )

    payload = {"text": report.text}

    async def execute(session: AsyncSession) -> None:
        await deps.notify(chat_id=OWNER_CHAT_KEY, kind="daily_report", payload=payload)

    return await propose_action(
        deps, workspace_id=workspace_id, action_type="send_report", payload=payload,
        execute=execute,
    )


async def _handle_owner_command(event: dict, deps: JarvisDeps) -> JarvisAction | None:
    text = (event.get("text") or "").strip().lower()
    workspace_id = event.get("workspace_id")

    if workspace_id and ("hammasiga ha" in text or text in ("ha", "hammasiga")):
        await batch_approve(deps, workspace_id)
        return None

    logger.info("jarvis.supervisor: owner.command hali ishlov berilmadi: %r", text)
    return None


async def _handle_staff_reply(event: dict, deps: JarvisDeps) -> JarvisAction | None:
    text = (event.get("text") or "").strip().lower()
    task_id = event.get("task_id")

    if task_id and "bajarildi" in text:
        async with deps.session_factory() as session:
            await task_manager.complete_task(session, _to_uuid(task_id))
            await session.commit()
        return None

    logger.info("jarvis.supervisor: staff.reply hali ishlov berilmadi: %r", text)
    return None


_HANDLERS: dict[str, Callable[[dict, JarvisDeps], Awaitable[JarvisAction | None]]] = {
    "lead.created": _handle_lead_created,
    "lead.reply": _handle_lead_reply,
    "task.overdue": _handle_task_overdue,
    "task.due_soon": _handle_task_overdue,
    "cron.daily_report": _handle_cron_daily_report,
    "owner.command": _handle_owner_command,
    "staff.reply": _handle_staff_reply,
}


async def handle_event(event: dict, deps: JarvisDeps) -> JarvisAction | None:
    """Eventni turi bo'yicha tegishli handler'ga yo'naltiradi (docs/06 "Event manbalari")."""
    event_type = event.get("type")
    handler = _HANDLERS.get(event_type)
    if handler is None:
        logger.warning("jarvis.supervisor: noma'lum event turi: %r", event_type)
        return None
    return await handler(event, deps)
