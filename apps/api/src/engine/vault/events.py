"""Vault hodisalar shinasi (docs/10, roadmap 3.7): jonli graf uchun pub/sub.

``VaultBus`` jarayon ichida ``asyncio.Queue`` orqali obunachilarga (WebSocket
ulanishlari) hodisa yetkazadi. Ko'p jarayonli sozlamada (bir nechta uvicorn
worker/API + arq worker) ``settings.redis_url`` orqali ``vault:events``
kanaliga ham e'lon qilinadi — bu "eng yaxshi urinish" (best effort): Redis
yetib bo'lmasa xatolik yutiladi, faqat shu jarayon ichidagi obunachilar
xabar oladi.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)

REDIS_CHANNEL = "vault:events"


class VaultBus:
    """Jarayon ichi async pub/sub: ``subscribe()`` → ``asyncio.Queue``."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, payload: dict[str, Any]) -> None:
        """Jarayon ichidagi hamma obunachilarga yetkazadi + Redis'ga (best effort)."""
        for queue in list(self._subscribers):
            queue.put_nowait(payload)
        self._publish_redis(payload)

    def _publish_redis(self, payload: dict[str, Any]) -> None:
        try:
            from engine.jobs import get_redis
        except Exception:  # noqa: BLE001 — import muammosi bo'lsa jim o'tamiz (best effort)
            return
        try:
            redis = get_redis()
            coro = redis.publish(REDIS_CHANNEL, json.dumps(payload, default=str))
        except Exception:  # pragma: no cover - Redis mavjud bo'lmasa jim o'tamiz
            logger.debug("vault bus: redis publish skipped", exc_info=True)
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - event loop yo'q
            return
        task = loop.create_task(coro)
        task.add_done_callback(_ignore_redis_errors)

    @contextlib.asynccontextmanager
    async def listen(self) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue = self.subscribe()
        try:
            yield queue
        finally:
            self.unsubscribe(queue)


def _ignore_redis_errors(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:  # pragma: no cover - Redis mavjud bo'lmasa jim o'tamiz
        logger.debug("vault bus: redis publish failed: %s", exc)


vault_bus = VaultBus()
