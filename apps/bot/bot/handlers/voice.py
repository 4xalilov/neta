"""Voice-first Jarvis (roadmap 5.10): owner/staff voice messages, the owner's
typed commands (when "🎙 Jarvis rejimi" is on) and the `/jarvis` help screen.

Everything here talks to a single API endpoint, `ApiClient.voice_command`
(`POST /v1/voice/command`, see `apps/bot/README.md`), and reuses
`handlers/brief.py::poll_job` when the response carries a `job_id` (a brief
pipeline the voice command kicked off).
"""
from __future__ import annotations

import base64
import logging
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot import texts
from bot.api_client import ApiClient, ApiError
from bot.handlers.brief import poll_job
from bot.keyboards import CB, brief_progress_kb, voice_mode_kb, voice_result_kb
from bot.settings import settings
from bot.states import VoiceStates
from bot.voice_mode import get_voice_mode, set_voice_mode

log = logging.getLogger(__name__)
router = Router(name="voice")

# Any protocol with .edit_text / .answer / .answer_voice -- a real aiogram
# Message, or the FakeMessage the placeholder message itself already is.
_Editable = Any


def _role(user_id: int | None) -> str:
    return "owner" if user_id == settings.owner_tg_id else "staff"


def _chat_id(callback: CallbackQuery) -> int:
    return callback.message.chat.id if callback.message is not None else settings.owner_tg_id


async def _workspace_id(api: ApiClient) -> str | None:
    try:
        workspace = await api.get_workspace(owner_tg_id=settings.owner_tg_id)
    except ApiError:
        return None
    return workspace.get("id") if workspace else None


async def _safe_edit(target: _Editable, text: str, **kwargs: Any) -> None:
    try:
        await target.edit_text(text, **kwargs)
    except Exception:
        log.debug("edit_text skipped", exc_info=True)


# -- rendering the voice_command result screen ---------------------------------------------------
async def _render_result(placeholder: _Editable, api: ApiClient, result: dict) -> None:
    transcript = result.get("transcript") or "-"
    reply_text = result.get("reply_text") or "-"
    actions = result.get("actions") or []
    pending = next((a for a in actions if a.get("status") == "pending"), None)
    action_id = pending.get("id") if pending else None
    show_confirm = bool(result.get("needs_confirmation")) or pending is not None

    await _safe_edit(
        placeholder,
        texts.VOICE_RESULT.format(transcript=transcript, reply_text=reply_text),
        reply_markup=voice_result_kb(action_id=action_id, show_confirm=show_confirm),
    )

    await _send_voice_note(placeholder, result)

    job_id = result.get("job_id")
    if job_id:
        await _poll_brief(placeholder, api, job_id)


async def _send_voice_note(placeholder: _Editable, result: dict) -> None:
    audio_b64 = result.get("audio_b64")
    audio_url = result.get("audio_url")
    if audio_b64:
        try:
            audio_bytes = base64.b64decode(audio_b64)
        except (ValueError, TypeError):
            log.warning("voice_command returned invalid audio_b64")
            audio_bytes = None
        if audio_bytes:
            await placeholder.answer_voice(BufferedInputFile(audio_bytes, filename="jarvis.ogg"))
    elif audio_url:
        await placeholder.answer_voice(audio_url)


async def _poll_brief(placeholder: _Editable, api: ApiClient, job_id: str) -> None:
    progress_msg = await placeholder.answer(texts.BRIEF_STARTED, reply_markup=brief_progress_kb(job_id))

    async def edit(new_text: str) -> None:
        await _safe_edit(progress_msg, new_text, reply_markup=brief_progress_kb(job_id))

    await poll_job(edit, api, job_id)


async def _run_voice_command(
    placeholder: _Editable,
    api: ApiClient,
    *,
    chat_id: int,
    audio: bytes | None = None,
    text: str | None = None,
    workspace_id: str | None = None,
    role: str = "owner",
) -> None:
    try:
        result = await api.voice_command(
            chat_id, audio=audio, text=text, workspace_id=workspace_id, role=role
        )
    except ApiError:
        log.exception("voice_command failed")
        await _safe_edit(placeholder, texts.ERROR_GENERIC)
        return
    await _render_result(placeholder, api, result)


# -- entry point 1: voice / audio messages (owner + staff) ---------------------------------------------------
@router.message(F.voice | F.audio)
async def on_voice_message(message: Message, api: ApiClient, bot: Bot) -> None:
    user = message.from_user
    file = message.voice or message.audio
    if file is None:
        return
    try:
        buf = await bot.download(file)
        audio_bytes = buf.read() if hasattr(buf, "read") else bytes(buf)
    except Exception:
        log.exception("failed to download voice/audio file")
        await message.answer(texts.ERROR_GENERIC)
        return

    placeholder = await message.answer(texts.VOICE_LISTENING)
    workspace_id = await _workspace_id(api)
    await _run_voice_command(
        placeholder,
        api,
        chat_id=message.chat.id,
        audio=audio_bytes,
        workspace_id=workspace_id,
        role=_role(user.id if user else None),
    )


# -- entry point 2: owner's plain text, when 🎙 Jarvis rejimi is on ---------------------------------------------------
@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def on_owner_text_via_voice_mode(message: Message, api: ApiClient, redis: Any = None) -> None:
    user = message.from_user
    if user is None or user.id != settings.owner_tg_id:
        return
    on = await get_voice_mode(redis, message.chat.id)
    if not on:
        return  # 🎙 Jarvis rejimi off -> old flows (no dedicated catch-all here)
    workspace_id = await _workspace_id(api)
    placeholder = await message.answer(texts.VOICE_LISTENING)
    await _run_voice_command(
        placeholder,
        api,
        chat_id=message.chat.id,
        text=message.text,
        workspace_id=workspace_id,
        role="owner",
    )


# -- ✏️ Tuzatish: type a corrected transcript, re-sent as text ---------------------------------------------------
@router.callback_query(CB.filter(F.action == "voice_fix"))
async def on_voice_fix_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(VoiceStates.waiting_correction)
    if callback.message is not None:
        await callback.message.edit_text(texts.VOICE_ASK_CORRECTION)


@router.message(VoiceStates.waiting_correction)
async def on_voice_correction_text(message: Message, api: ApiClient, state: FSMContext) -> None:
    await state.clear()
    corrected = (message.text or "").strip()
    if not corrected:
        await message.answer(texts.ERROR_GENERIC)
        return
    user = message.from_user
    workspace_id = await _workspace_id(api)
    placeholder = await message.answer(texts.VOICE_LISTENING)
    await _run_voice_command(
        placeholder,
        api,
        chat_id=message.chat.id,
        text=corrected,
        workspace_id=workspace_id,
        role=_role(user.id if user else None),
    )


# -- ✅ Ha / ❌ Yo'q (needs_confirmation / pending action) ---------------------------------------------------
@router.callback_query(CB.filter(F.action == "voice_yes"))
async def on_voice_confirm_yes(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.jarvis_decision(callback_data.id, decision="yes")
    except ApiError:
        log.exception("jarvis_decision yes failed (voice)")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Tasdiqlandi ✅")
    if callback.message is not None:
        await callback.message.edit_text(texts.JARVIS_APPROVAL_YES)


@router.callback_query(CB.filter(F.action == "voice_no"))
async def on_voice_confirm_no(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.jarvis_decision(callback_data.id, decision="no")
    except ApiError:
        log.exception("jarvis_decision no failed (voice)")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Rad etildi ❌")
    if callback.message is not None:
        await callback.message.edit_text(texts.JARVIS_APPROVAL_NO)


# -- 🔁 Qayta ayting ---------------------------------------------------
@router.callback_query(CB.filter(F.action == "voice_retry"))
async def on_voice_retry(callback: CallbackQuery) -> None:
    await callback.answer("Ovozli xabar yuboring 🔁")
    if callback.message is not None:
        await callback.message.edit_text(texts.VOICE_RETRY)


# -- 🎙 Jarvis rejimi toggle screen (from the menu) ---------------------------------------------------
@router.callback_query(F.data == CB(action="menu", arg="voice").pack())
async def on_menu_voice_mode(callback: CallbackQuery, redis: Any = None) -> None:
    await callback.answer()
    chat_id = _chat_id(callback)
    on = await get_voice_mode(redis, chat_id)
    if callback.message is not None:
        await callback.message.edit_text(
            texts.VOICE_MODE_HEADING.format(state=texts.VOICE_MODE_LABELS[on]),
            reply_markup=voice_mode_kb(on),
        )


@router.callback_query(CB.filter(F.action == "voice_mode_set"))
async def on_voice_mode_set(callback: CallbackQuery, callback_data: CB, redis: Any = None) -> None:
    on = callback_data.arg == "on"
    chat_id = _chat_id(callback)
    await set_voice_mode(redis, chat_id, on)
    await callback.answer("Saqlandi ✅")
    if callback.message is not None:
        await callback.message.edit_text(
            texts.VOICE_MODE_HEADING.format(state=texts.VOICE_MODE_LABELS[on]),
            reply_markup=voice_mode_kb(on),
        )


# -- /jarvis help screen ---------------------------------------------------
@router.message(Command("jarvis"))
async def cmd_jarvis_help(message: Message) -> None:
    await message.answer(texts.JARVIS_HELP)
