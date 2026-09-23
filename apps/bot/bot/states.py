"""FSM states shared across handlers."""
from aiogram.fsm.state import State, StatesGroup


class BriefStates(StatesGroup):
    waiting_text = State()


class ScriptRejectStates(StatesGroup):
    waiting_reason = State()


class VideoRejectStates(StatesGroup):
    waiting_reason = State()
