"""`/brief <matn>` yoki FSM: brif matnini qabul qilib, ssenariy tayyorlanishini kuzatadi."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.api_client import ApiClient, ApiError
from bot.keyboards import CB, brief_progress_kb
from bot.settings import settings
from bot.states import BriefStates

log = logging.getLogger(__name__)
router = Router(name="brief")

DONE_STATUSES = {"done", "completed", "success"}
FAILED_STATUSES = {"error", "failed"}


async def _get_workspace_id(api: ApiClient, owner_tg_id: int) -> str | None:
    try:
        workspace = await api.get_workspace(owner_tg_id=owner_tg_id)
    except ApiError:
        return None
    return workspace.get("id") if workspace else None


async def poll_job(
    edit: Callable[[str], Awaitable[None]],
    api: ApiClient,
    job_id: str,
    *,
    interval_s: float | None = None,
    timeout_s: float | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict:
    """Poll `get_job` every `interval_s` seconds (edits the same message) until
    it reaches a terminal state or `timeout_s` elapses. Returns the final job.
    """
    interval_s = interval_s if interval_s is not None else settings.brief_poll_interval_s
    timeout_s = timeout_s if timeout_s is not None else settings.brief_poll_timeout_s
    elapsed = 0.0
    while elapsed < timeout_s:
        try:
            job = await api.get_job(job_id)
        except ApiError:
            job = {"status": "unknown"}
        status = job.get("status", "unknown")
        if status in DONE_STATUSES:
            await edit(texts.BRIEF_DONE)
            return job
        if status in FAILED_STATUSES:
            await edit(texts.BRIEF_FAILED.format(error=job.get("error", "noma'lum")))
            return job
        await edit(
            texts.BRIEF_PROGRESS.format(
                stage=job.get("stage", "-"), progress=job.get("progress", 0)
            )
        )
        await sleep(interval_s)
        elapsed += interval_s
    await edit(texts.BRIEF_TIMEOUT)
    return {"status": "timeout"}


async def _start_brief(message: Message, api: ApiClient, text: str) -> None:
    user = message.from_user
    if user is None:
        return
    workspace_id = await _get_workspace_id(api, settings.owner_tg_id)
    if workspace_id is None:
        await message.answer(texts.ERROR_GENERIC)
        return
    try:
        job_id = await api.create_brief(workspace_id=workspace_id, text=text)
    except ApiError:
        log.exception("create_brief failed")
        await message.answer(texts.ERROR_GENERIC)
        return

    progress_msg = await message.answer(texts.BRIEF_STARTED, reply_markup=brief_progress_kb(job_id))

    async def edit(new_text: str) -> None:
        try:
            await progress_msg.edit_text(new_text, reply_markup=brief_progress_kb(job_id))
        except Exception:
            log.debug("edit_text skipped", exc_info=True)

    await poll_job(edit, api, job_id)


@router.message(Command("brief"))
async def cmd_brief(message: Message, api: ApiClient, state: FSMContext) -> None:
    args = message.text.split(maxsplit=1) if message.text else []
    brief_text = args[1].strip() if len(args) > 1 else ""
    if not brief_text:
        await state.set_state(BriefStates.waiting_text)
        await message.answer(texts.ASK_BRIEF)
        return
    await _start_brief(message, api, brief_text)


@router.message(BriefStates.waiting_text)
async def on_brief_text(message: Message, api: ApiClient, state: FSMContext) -> None:
    await state.clear()
    await _start_brief(message, api, (message.text or "").strip())


@router.callback_query(F.data == CB(action="menu", arg="brief").pack())
async def on_menu_brief(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(BriefStates.waiting_text)
    if callback.message:
        await callback.message.edit_text(texts.ASK_BRIEF)


@router.callback_query(F.data.startswith("cb:brief_cancel:"))
async def on_brief_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Bekor qilindi")
    if callback.message:
        await callback.message.edit_text(texts.CANCELLED)
