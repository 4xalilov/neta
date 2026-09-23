"""⚙️ Sozlamalar: siz/sen, ovoz, registr — `update_brand_profile` orqali saqlanadi;
🎙 Jarvis rejimi — per-chat Redis flag (`bot/voice_mode.py`)."""
from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot import texts
from bot.api_client import ApiClient, ApiError
from bot.keyboards import CB, settings_kb
from bot.settings import settings as bot_settings
from bot.voice_mode import get_voice_mode, set_voice_mode

log = logging.getLogger(__name__)
router = Router(name="settings")

FIELD_BY_ACTION = {"set_pron": "pronoun", "set_voice": "voice", "set_register": "register"}


async def _workspace_id(api: ApiClient) -> str | None:
    try:
        workspace = await api.get_workspace(owner_tg_id=bot_settings.owner_tg_id)
    except ApiError:
        return None
    return workspace.get("id") if workspace else None


def _render(profile: dict) -> str:
    return texts.SETTINGS_HEADING.format(
        pronoun=texts.PRONOUN_LABELS.get(profile.get("pronoun", "siz"), "Siz"),
        voice=texts.VOICE_LABELS.get(profile.get("voice", "madina"), "Madina"),
        register=texts.REGISTER_LABELS.get(profile.get("register", "neutral"), "Neytral"),
    )


def _chat_id(callback: CallbackQuery) -> int:
    return callback.message.chat.id if callback.message is not None else bot_settings.owner_tg_id


async def _render_screen(callback: CallbackQuery, api: ApiClient, redis: Any = None) -> None:
    workspace_id = await _workspace_id(api)
    if workspace_id is None:
        if callback.message is not None:
            await callback.message.edit_text(texts.ERROR_GENERIC)
        return
    try:
        workspace = await api.get_workspace(owner_tg_id=bot_settings.owner_tg_id)
    except ApiError:
        workspace = None
    profile = (workspace or {}).get("brand_profile", {})
    voice_mode = await get_voice_mode(redis, _chat_id(callback))
    if callback.message is not None:
        await callback.message.edit_text(
            _render(profile),
            reply_markup=settings_kb(
                profile.get("pronoun", "siz"),
                profile.get("voice", "madina"),
                profile.get("register", "neutral"),
                voice_mode,
            ),
        )


@router.callback_query(F.data == CB(action="menu", arg="settings").pack())
async def on_menu_settings(callback: CallbackQuery, api: ApiClient, redis: Any = None) -> None:
    await callback.answer()
    await _render_screen(callback, api, redis)


@router.callback_query(CB.filter(F.action.in_(FIELD_BY_ACTION)))
async def on_settings_change(
    callback: CallbackQuery, callback_data: CB, api: ApiClient, redis: Any = None
) -> None:
    field = FIELD_BY_ACTION[callback_data.action]
    workspace_id = await _workspace_id(api)
    if workspace_id is None:
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    try:
        profile = await api.update_brand_profile(workspace_id, **{field: callback_data.arg})
    except ApiError:
        log.exception("update_brand_profile failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Saqlandi ✅")
    voice_mode = await get_voice_mode(redis, _chat_id(callback))
    if callback.message is not None:
        await callback.message.edit_text(
            _render(profile),
            reply_markup=settings_kb(
                profile.get("pronoun", "siz"),
                profile.get("voice", "madina"),
                profile.get("register", "neutral"),
                voice_mode,
            ),
        )


@router.callback_query(CB.filter(F.action == "voice_mode_toggle"))
async def on_voice_mode_toggle(callback: CallbackQuery, api: ApiClient, redis: Any = None) -> None:
    chat_id = _chat_id(callback)
    current = await get_voice_mode(redis, chat_id)
    await set_voice_mode(redis, chat_id, not current)
    await callback.answer("Saqlandi ✅")
    await _render_screen(callback, api, redis)
