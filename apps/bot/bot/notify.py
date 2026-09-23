"""Redis pub/sub subscriber: the API pushes screens to the bot via `tg:notify`.

Message format (JSON, published to the `tg:notify` channel)::

    {"chat_id": 123456, "kind": "script|video|report|approval|voice_reply|clarify", "payload": {...}}

See `apps/bot/README.md` for each `payload` shape. `build_notification` is the
pure renderer (kind + payload -> text, keyboard) used both by the subscriber
and by tests.
"""
from __future__ import annotations

import asyncio
import json
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from redis.asyncio import Redis

from bot import texts
from bot.keyboards import (
    approval_request_kb,
    jarvis_report_kb,
    script_approval_kb,
    task_kb,
    video_approval_kb,
)
from bot.settings import settings

log = logging.getLogger(__name__)

NOTIFY_CHANNEL = "tg:notify"


def build_notification(kind: str, payload: dict) -> tuple[str, InlineKeyboardMarkup | None]:
    """Pick the right screen (text + keyboard) for a notify message `kind`."""
    if kind == "script":
        hooks = payload.get("hooks", [])
        selected_idx = payload.get("selected_idx", 0)
        text = texts.SCRIPT_APPROVAL.format(
            hook=hooks[selected_idx] if hooks else "-",
            body=payload.get("body", "-"),
            cta=payload.get("cta", "-"),
            uz_score=payload.get("uz_score", "-"),
            brand_score=payload.get("brand_score", "-"),
            hook_score=payload.get("hook_score", "-"),
        )
        return text, script_approval_kb(payload["script_id"], hooks, selected_idx)

    if kind == "video":
        text = texts.VIDEO_APPROVAL.format(
            cost=payload.get("cost", "0.00"),
            vision_qa=payload.get("vision_qa", "-"),
            duration=payload.get("duration", "-"),
        )
        return text, video_approval_kb(payload["script_id"])

    if kind == "report":
        text = texts.JARVIS_REPORT.format(
            leads=payload.get("leads", 0),
            hot=payload.get("hot", 0),
            sales=payload.get("sales", 0),
            revenue=payload.get("revenue", 0),
            overdue=payload.get("overdue", 0),
        )
        return text, jarvis_report_kb(payload["workspace_id"])

    if kind == "approval":
        text = texts.JARVIS_APPROVAL_REQUEST.format(description=payload.get("description", "-"))
        return text, approval_request_kb(payload["action_id"])

    if kind == "voice_reply":
        # Jarvis's spoken/typed reply to a voice command (roadmap 5.10). The
        # voice note itself (if `audio_url` is present) is sent separately by
        # `_handle_message`, after this text screen.
        text = texts.VOICE_REPLY_NOTIFY.format(text=payload.get("text", "-"))
        return text, None

    if kind == "clarify":
        # Low-confidence intent (< 0.7) -> a clarifying question, same
        # ✅/❌/✏️ shape as the "approval" kind, keyed by `action_id` when given.
        text = texts.VOICE_CLARIFY.format(question=payload.get("question", "-"))
        action_id = payload.get("action_id")
        return text, (approval_request_kb(action_id) if action_id else None)

    if kind == "task":
        # A staff member was voice-assigned a task (`assign_task` intent,
        # apps/api/README.md "Yangi tg:notify kind"). `due` is the human
        # phrase ("ertaga 15:00"); fall back to the raw `due_at` if missing.
        text = texts.TASK_NEW.format(
            title=payload.get("title", "-"),
            due=payload.get("due") or payload.get("due_at") or "-",
        )
        return text, task_kb(payload["task_id"])

    if kind == "reminder":
        # `remind_staff` intent -> a staff member's open task(s). Shows
        # `title` when the API sends a single task; otherwise falls back to
        # the `titles` list, then `note`.
        titles = payload.get("titles") or []
        body = payload.get("title") or (", ".join(titles) if titles else payload.get("note")) or "-"
        text = texts.JARVIS_REMINDER.format(staff_name=payload.get("staff_name", "-"), body=body)
        return text, None

    log.warning("unknown notify kind: %s", kind)
    return texts.ERROR_GENERIC, None


async def _handle_message(bot: Bot, raw: bytes | str) -> None:
    try:
        data = json.loads(raw)
        chat_id = data["chat_id"]
        kind = data["kind"]
        payload = data.get("payload", {})
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("malformed notify payload: %r", raw)
        return

    text, keyboard = build_notification(kind, payload)
    await bot.send_message(chat_id, text, reply_markup=keyboard)

    if kind == "voice_reply" and payload.get("audio_url"):
        # `audio_fmt` picks the Telegram send method (apps/api/README.md
        # "Ovozli boshqaruv"): "ogg" -> send_voice, "mp3"/"wav" (no ffmpeg on
        # the API side) -> send_audio, missing (older payloads) defaults to
        # "ogg", explicit `null` means text-only -> no audio is sent at all.
        audio_fmt = payload.get("audio_fmt", "ogg")
        if audio_fmt is not None:
            sender = bot.send_voice if audio_fmt == "ogg" else bot.send_audio
            try:
                await sender(chat_id, payload["audio_url"])
            except Exception:
                log.exception("failed to send voice note for voice_reply")


async def run_notify_subscriber(bot: Bot, redis_url: str | None = None) -> None:
    """Subscribe to `tg:notify` and render+send each message. Runs forever."""
    redis = Redis.from_url(redis_url or settings.redis_url)
    pubsub = redis.pubsub()
    await pubsub.subscribe(NOTIFY_CHANNEL)
    log.info("subscribed to redis channel %s", NOTIFY_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                await _handle_message(bot, message["data"])
            except Exception:
                log.exception("failed to handle notify message")
    finally:
        await pubsub.unsubscribe(NOTIFY_CHANNEL)
        await redis.aclose()


def start_notify_task(bot: Bot) -> asyncio.Task:
    return asyncio.create_task(run_notify_subscriber(bot))
