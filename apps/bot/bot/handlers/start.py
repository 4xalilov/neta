"""`/start` — ega ro'yxatdan o'tadi, workspace yaratiladi, menyu ko'rsatiladi."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot import texts
from bot.api_client import ApiClient, ApiError
from bot.keyboards import menu_kb, staff_menu_kb
from bot.settings import settings

log = logging.getLogger(__name__)
router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, api: ApiClient) -> None:
    user = message.from_user
    if user is None:
        return

    if user.id == settings.owner_tg_id:
        try:
            workspace = await api.get_workspace(owner_tg_id=user.id)
            if workspace is None:
                name = message.chat.title or user.full_name or "Mening biznesim"
                workspace = await api.create_workspace(owner_tg_id=user.id, name=name)
            workspace_name = workspace.get("name", "-") if workspace else "-"
        except ApiError:
            log.exception("failed to create/get workspace for owner=%s", user.id)
            await message.answer(texts.ERROR_GENERIC)
            return

        await message.answer(texts.WELCOME_OWNER.format(workspace_name=workspace_name))
        await message.answer(texts.MENU_HEADING, reply_markup=menu_kb())
    else:
        await message.answer(texts.WELCOME_STAFF.format(full_name=user.full_name))
        await message.answer(texts.MENU_HEADING, reply_markup=staff_menu_kb())
