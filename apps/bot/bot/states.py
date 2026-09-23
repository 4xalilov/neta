"""FSM states shared across handlers."""
from aiogram.fsm.state import State, StatesGroup


class BriefStates(StatesGroup):
    waiting_text = State()


class ScriptRejectStates(StatesGroup):
    waiting_reason = State()


class VideoRejectStates(StatesGroup):
    waiting_reason = State()


class VoiceStates(StatesGroup):
    """✏️ Tuzatish: owner types a corrected transcript, re-sent as `text` to
    `/v1/voice/command` (bot/handlers/voice.py)."""

    waiting_correction = State()
