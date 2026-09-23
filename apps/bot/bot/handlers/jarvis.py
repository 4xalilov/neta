"""Jarvis kunlik hisobot va tasdiq so'rovi ekranlari."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot import texts
from bot.api_client import ApiClient, ApiError
from bot.keyboards import CB, jarvis_report_kb
from bot.settings import settings

_TASK_STATUS_ACK = {"done": texts.TASK_DONE_ACK, "delayed": texts.TASK_DELAYED_ACK}

log = logging.getLogger(__name__)
router = Router(name="jarvis")


async def _workspace_id(api: ApiClient) -> str | None:
    try:
        workspace = await api.get_workspace(owner_tg_id=settings.owner_tg_id)
    except ApiError:
        return None
    return workspace.get("id") if workspace else None


@router.callback_query(F.data == CB(action="menu", arg="report").pack())
async def on_menu_report(callback: CallbackQuery, api: ApiClient) -> None:
    await callback.answer()
    workspace_id = await _workspace_id(api)
    if workspace_id is None:
        if callback.message is not None:
            await callback.message.edit_text(texts.ERROR_GENERIC)
        return
    try:
        report = await api.daily_report(workspace_id)
    except ApiError:
        log.exception("daily_report failed")
        if callback.message is not None:
            await callback.message.edit_text(texts.ERROR_GENERIC)
        return
    text = texts.JARVIS_REPORT.format(
        leads=report.get("leads", 0),
        hot=report.get("hot", 0),
        sales=report.get("sales", 0),
        revenue=report.get("revenue", 0),
        overdue=report.get("overdue", 0),
    )
    if callback.message is not None:
        await callback.message.edit_text(text, reply_markup=jarvis_report_kb(workspace_id))


@router.callback_query(CB.filter(F.action == "jr_all"))
async def on_jarvis_message_all(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.jarvis_decision(f"report:{callback_data.id}:all", decision="yes")
    except ApiError:
        log.exception("jarvis message-all failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Yuborildi ✉️")
    if callback.message is not None:
        await callback.message.answer(texts.JARVIS_REPORT_ACK)


@router.callback_query(CB.filter(F.action == "jr_remind"))
async def on_jarvis_remind_staff(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.jarvis_decision(f"report:{callback_data.id}:remind", decision="yes")
    except ApiError:
        log.exception("jarvis remind-staff failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Eslatildi 👤")
    if callback.message is not None:
        await callback.message.answer(texts.JARVIS_REMIND_ACK)


# -- approval request (requires_approval, LangGraph interrupt) ---------------------------------------------------
@router.callback_query(CB.filter(F.action == "appr_yes"))
async def on_approval_yes(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.jarvis_decision(callback_data.id, decision="yes")
    except ApiError:
        log.exception("jarvis_decision yes failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Tasdiqlandi ✅")
    if callback.message is not None:
        await callback.message.edit_text(texts.JARVIS_APPROVAL_YES)


@router.callback_query(CB.filter(F.action == "appr_no"))
async def on_approval_no(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.jarvis_decision(callback_data.id, decision="no")
    except ApiError:
        log.exception("jarvis_decision no failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Rad etildi ❌")
    if callback.message is not None:
        await callback.message.edit_text(texts.JARVIS_APPROVAL_NO)


# -- kind="task" screen (a staff member was voice-assigned a task) ---------------------------------------------------
@router.callback_query(CB.filter(F.action == "task_status"))
async def on_task_status(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    status = callback_data.arg  # "done" | "delayed"
    try:
        await api.task_status(callback_data.id, status=status)
    except ApiError:
        log.exception("task_status failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Saqlandi ✅")
    if callback.message is not None:
        await callback.message.edit_text(_TASK_STATUS_ACK.get(status, texts.TASK_DONE_ACK))


@router.callback_query(CB.filter(F.action == "appr_edit"))
async def on_approval_edit(callback: CallbackQuery, callback_data: CB, api: ApiClient) -> None:
    try:
        await api.jarvis_decision(callback_data.id, decision="edit")
    except ApiError:
        log.exception("jarvis_decision edit failed")
        await callback.answer(texts.ERROR_GENERIC, show_alert=True)
        return
    await callback.answer("Tahrirlash")
    if callback.message is not None:
        await callback.message.edit_text(texts.JARVIS_APPROVAL_EDIT)
