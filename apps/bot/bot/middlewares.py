"""Owner-only guard and logging middlewares."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.settings import settings

log = logging.getLogger("bot")

# callback actions the owner alone is allowed to perform (approvals, settings, ...)
OWNER_ONLY_ACTIONS = {
    "script_ok",
    "script_edit",
    "script_retry",
    "script_no",
    "video_pub",
    "video_sched",
    "video_no",
    "jr_all",
    "jr_remind",
    "appr_yes",
    "appr_no",
    "appr_edit",
    "set_pron",
    "set_voice",
    "set_register",
    "voice_mode_toggle",
    "voice_mode_set",
}


def _user_id(event: TelegramObject) -> int | None:
    if isinstance(event, Message) and event.from_user:
        return event.from_user.id
    if isinstance(event, CallbackQuery) and event.from_user:
        return event.from_user.id
    return None


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        log.info("update: %s from=%s", type(event).__name__, _user_id(event))
        return await handler(event, data)


class OwnerOnlyMiddleware(BaseMiddleware):
    """Blocks owner-only callback actions from non-owner chats."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery) and event.data:
            action = event.data.split(":")[1] if event.data.count(":") >= 1 else ""
            if action in OWNER_ONLY_ACTIONS and _user_id(event) != settings.owner_tg_id:
                await event.answer("⛔ Bu amal faqat egaga ruxsat etilgan.", show_alert=True)
                return None
        return await handler(event, data)
