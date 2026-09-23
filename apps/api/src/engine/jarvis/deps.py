"""Jarvis bog'liqliklari — bitta joyda CRM, DB session factory, bildirishnoma va vaqt.

Barcha ``jarvis/*`` funksiyalari global holatga emas, shu ``JarvisDeps`` ga tayanadi —
testlarda soxta CRM/notify/soat berish oson (``httpx.MockTransport`` yoki
``InMemoryCRM`` + qo'lda ``now`` funksiyasi).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from engine.integrations.crm_adapter import CRM

# notify(*, chat_id, kind, payload) -> None. ``chat_id`` yoki haqiqiy Telegram id (int),
# yoki "owner" kabi mantiqiy kalit bo'lishi mumkin — chaqiruvchi (masalan jarvis_routes)
# uni haqiqiy chat id'ga aylantiradi.
NotifyFn = Callable[..., Awaitable[None]]


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class JarvisDeps:
    crm: CRM
    session_factory: async_sessionmaker[AsyncSession]
    notify: NotifyFn
    now: Callable[[], datetime] = field(default=_utcnow)
