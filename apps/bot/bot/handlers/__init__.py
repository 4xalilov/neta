from aiogram import Router

from bot.handlers import approval, brief, jarvis, settings, start, voice


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(brief.router)
    root.include_router(approval.router)
    root.include_router(jarvis.router)
    root.include_router(settings.router)
    # last: catches the owner's plain text when 🎙 Jarvis rejimi is on (only
    # matches messages with no active FSM state, so it never shadows the
    # state-specific handlers above).
    root.include_router(voice.router)
    return root


__all__ = ["build_router"]
