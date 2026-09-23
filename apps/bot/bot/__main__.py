"""Entry point: `python -m bot`. Polling by default; webhook mode via env
(`WEBHOOK_MODE=true`). Importing this module never starts the bot — only
running it as `__main__` does.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from redis.asyncio import Redis

from bot.api_client import ApiClient
from bot.handlers import build_router
from bot.middlewares import LoggingMiddleware, OwnerOnlyMiddleware
from bot.notify import start_notify_task
from bot.settings import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")


def build_dispatcher(api: ApiClient, redis: Redis) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(LoggingMiddleware())
    dp.callback_query.outer_middleware(OwnerOnlyMiddleware())
    dp.include_router(build_router())
    dp["api"] = api
    dp["redis"] = redis  # bot/voice_mode.py: per-chat "🎙 Jarvis rejimi" flag
    return dp


async def run_polling() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    api = ApiClient()
    redis = Redis.from_url(settings.redis_url)
    dp = build_dispatcher(api, redis)

    notify_task = start_notify_task(bot)
    try:
        await dp.start_polling(bot)
    finally:
        notify_task.cancel()
        await api.aclose()
        await redis.aclose()
        await bot.session.close()


async def run_webhook() -> None:
    """Optional webhook mode (aiohttp web server)."""
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from aiohttp import web

    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    if not settings.webhook_url:
        raise RuntimeError("WEBHOOK_URL is not set")

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    api = ApiClient()
    redis = Redis.from_url(settings.redis_url)
    dp = build_dispatcher(api, redis)

    await bot.set_webhook(settings.webhook_url)
    start_notify_task(bot)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.webhook_host, settings.webhook_port)
    await site.start()
    log.info("webhook server listening on %s:%s", settings.webhook_host, settings.webhook_port)
    await asyncio.Event().wait()


def main() -> None:
    if settings.webhook_mode:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
