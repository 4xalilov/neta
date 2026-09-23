from aiogram import Router

from bot.handlers import approval, brief, jarvis, settings, start


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(brief.router)
    root.include_router(approval.router)
    root.include_router(jarvis.router)
    root.include_router(settings.router)
    return root


__all__ = ["build_router"]
