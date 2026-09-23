"""Ssenariy va video tasdiqlash ekranlari."""
from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot import texts
from bot.api_client import ApiClient, ApiError
from bot.keyboards import CB, script_approval_kb, video_approval_kb
from bot.states import ScriptRejectStates, VideoRejectStates

log = logging.getLogger(__name__)
router = Router(name="approval")

_HOOK_LABEL_RE = re.compile(r"^[🔘⚪]\s*\d+\.\s*(.*)$")


def _extract_hooks(markup: InlineKeyboardMarkup | None) -> list[str]:
    hooks: list[str] = []
    if markup is None:
        return hooks
    for row in markup.inline_keyboard:
        for button in row:
            if button.callback_data and button.callback_data.startswith("cb:hook:"):
                match = _HOOK_LABEL_RE.match(button.text)
                hooks.append(match.group(1) if match else button.text)
    return hooks


# -- hook selection (radio) ---------------------------------------------------
@router.callback_query(CB.filter(F.action == "hook"))
async def on_hook_select(callback: CallbackQuery, callback_data: CB) -> None:
    await callback.answer()
    if callback.message is None:
        return
    hooks = _extract_hooks(callback.message.reply_markup)
    if not hooks:
        return
    selected_idx = int(callback_data.arg)
    await callback.message.edit_reply_markup(
        reply_markup=script_approval_kb(callback_data.id, hooks, selected_idx)
    )


# -- script approve / retry ---------------------------------------------------
@router.callback_query(CB.filter(F.action == "script_ok"))
async def on_script_approve(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    hook_idx = int(callback_data.arg) if callback_data.arg != "-" else 0
    try:
        await api.approve_script(callback_data.id, hook_idx=hook_idx)
    except ApiError:
        log.exception("approve_script failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Tasdiqlandi ✅")
    if callback.message is not None:
        await callback.message.edit_text(texts.SCRIPT_APPROVED.format(hook_idx=hook_idx + 1))


@router.callback_query(CB.filter(F.action == "script_retry"))
async def on_script_retry(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.reject(callback_data.id, reason="qayta yozish so'raldi")
    except ApiError:
        log.exception("script retry failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Qayta yozilmoqda 🔄")
    if callback.message is not None:
        await callback.message.edit_text(texts.SCRIPT_RETRY)


@router.callback_query(CB.filter(F.action == "script_edit"))
async def on_script_edit(callback: CallbackQuery, callback_data: CB, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ScriptRejectStates.waiting_reason)
    await state.update_data(script_id=callback_data.id, mode="edit")
    if callback.message is not None:
        await callback.message.edit_text(texts.ASK_REJECT_REASON)


@router.callback_query(CB.filter(F.action == "script_no"))
async def on_script_reject_start(
    callback: CallbackQuery, callback_data: CB, state: FSMContext
) -> None:
    await callback.answer()
    await state.set_state(ScriptRejectStates.waiting_reason)
    await state.update_data(script_id=callback_data.id, mode="reject")
    if callback.message is not None:
        await callback.message.edit_text(texts.ASK_REJECT_REASON)


@router.message(ScriptRejectStates.waiting_reason)
async def on_script_reject_reason(message: Message, api: ApiClient, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    script_id = data.get("script_id", "-")
    reason = (message.text or "").strip()
    try:
        await api.reject(script_id, reason=reason)
    except ApiError:
        log.exception("reject failed")
        await message.answer(texts.ERROR_GENERIC)
        return
    await message.answer(texts.SCRIPT_REJECTED.format(reason=reason))


# -- video approval ---------------------------------------------------
@router.callback_query(CB.filter(F.action == "video_pub"))
async def on_video_publish(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.approve_video(callback_data.id, action="publish")
    except ApiError:
        log.exception("approve_video publish failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Nashr qilindi ✅")
    if callback.message is not None:
        await callback.message.edit_text(texts.VIDEO_PUBLISHED)


@router.callback_query(CB.filter(F.action == "video_sched"))
async def on_video_schedule(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.approve_video(callback_data.id, action="schedule")
    except ApiError:
        log.exception("approve_video schedule failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Rejalashtirildi 🕒")
    if callback.message is not None:
        await callback.message.edit_text(texts.VIDEO_SCHEDULED)


@router.callback_query(CB.filter(F.action == "video_no"))
async def on_video_reject_start(
    callback: CallbackQuery, callback_data: CB, state: FSMContext
) -> None:
    await callback.answer()
    await state.set_state(VideoRejectStates.waiting_reason)
    await state.update_data(script_id=callback_data.id)
    if callback.message is not None:
        await callback.message.edit_text(texts.ASK_VIDEO_REJECT_REASON)


@router.message(VideoRejectStates.waiting_reason)
async def on_video_reject_reason(message: Message, api: ApiClient, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    script_id = data.get("script_id", "-")
    reason = (message.text or "").strip()
    try:
        await api.reject(script_id, reason=reason)
    except ApiError:
        log.exception("video reject failed")
        await message.answer(texts.ERROR_GENERIC)
        return
    await message.answer(texts.VIDEO_REJECTED.format(reason=reason))


__all__ = ["router", "script_approval_kb", "video_approval_kb"]
