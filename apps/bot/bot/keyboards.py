"""Inline keyboards for every screen in docs/08-design-system.md.

Callback data uses a single compact scheme ``cb:<action>:<id>:<arg>``
(ASCII, <= 64 bytes) built with :class:`CB`, an
``aiogram.filters.callback_data.CallbackData`` subclass.
"""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

NO_ARG = "-"


class CB(CallbackData, prefix="cb"):
    action: str
    id: str = NO_ARG
    arg: str = NO_ARG


def _btn(text: str, action: str, id_: str = NO_ARG, arg: str = NO_ARG) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=CB(action=action, id=id_, arg=arg).pack())


# -- menu ---------------------------------------------------
def menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("📝 Brif", "menu", arg="brief"), _btn("📅 Reja", "menu", arg="plan")],
            [_btn("📊 Hisobot", "menu", arg="report"), _btn("⚙️ Sozlamalar", "menu", arg="settings")],
        ]
    )


def staff_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("📊 Hisobot", "menu", arg="report")]])


# -- brief progress ---------------------------------------------------
def brief_progress_kb(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("❌ Bekor", "brief_cancel", id_=job_id)]])


# -- script approval ---------------------------------------------------
def script_approval_kb(script_id: str, hooks: list[str], selected_idx: int = 0) -> InlineKeyboardMarkup:
    hook_rows = []
    for idx, hook in enumerate(hooks):
        mark = "🔘" if idx == selected_idx else "⚪"
        label = f"{mark} {idx + 1}. {hook}"[:60]
        hook_rows.append([_btn(label, "hook", id_=script_id, arg=str(idx))])
    action_row = [
        _btn("✅ Tasdiq", "script_ok", id_=script_id, arg=str(selected_idx)),
        _btn("✏️ Tahrir", "script_edit", id_=script_id),
        _btn("🔄 Qayta", "script_retry", id_=script_id),
    ]
    cancel_row = [_btn("❌ Bekor", "script_no", id_=script_id)]
    return InlineKeyboardMarkup(inline_keyboard=[*hook_rows, action_row, cancel_row])


# -- video approval ---------------------------------------------------
def video_approval_kb(script_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("✅ Nashr", "video_pub", id_=script_id),
                _btn("🕒 Rejalashtir", "video_sched", id_=script_id),
            ],
            [_btn("❌ Rad", "video_no", id_=script_id)],
        ]
    )


# -- jarvis daily report ---------------------------------------------------
def jarvis_report_kb(workspace_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("✉️ Hammasiga yoz", "jr_all", id_=workspace_id),
                _btn("👤 Xodimga eslat", "jr_remind", id_=workspace_id),
            ]
        ]
    )


# -- jarvis approval request ---------------------------------------------------
def approval_request_kb(action_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("✅ Ha", "appr_yes", id_=action_id),
                _btn("❌ Yo'q", "appr_no", id_=action_id),
                _btn("✏️ Tahrir", "appr_edit", id_=action_id),
            ]
        ]
    )


# -- settings ---------------------------------------------------
def settings_kb(pronoun: str, voice: str, register: str) -> InlineKeyboardMarkup:
    def mark(current: str, value: str) -> str:
        return "🔘" if current == value else "⚪"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(f"{mark(pronoun, 'siz')} Siz", "set_pron", arg="siz"),
                _btn(f"{mark(pronoun, 'sen')} Sen", "set_pron", arg="sen"),
            ],
            [
                _btn(f"{mark(voice, 'madina')} Madina", "set_voice", arg="madina"),
                _btn(f"{mark(voice, 'sardor')} Sardor", "set_voice", arg="sardor"),
            ],
            [
                _btn(f"{mark(register, 'casual')} Erkin", "set_register", arg="casual"),
                _btn(f"{mark(register, 'neutral')} Neytral", "set_register", arg="neutral"),
                _btn(f"{mark(register, 'formal')} Rasmiy", "set_register", arg="formal"),
            ],
            [_btn("◀️ Orqaga", "menu", arg="home")],
        ]
    )


def back_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("❌ Bekor", "cancel")]])
