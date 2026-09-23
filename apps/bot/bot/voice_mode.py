"""Per-chat "🎙 Jarvis rejimi" flag: when on, the owner's plain text messages are
also routed to `/v1/voice/command` (as `text`) instead of only the old
button-driven flows. Stored in Redis as ``chat:{id}:voice_mode`` -> ``"on"``/``"off"``.

Default is **on** for the owner (roadmap 5.10: "har voice xabar buyruq";
typed short commands are the text-mode equivalent of that). Every function here
tolerates a missing/``None`` redis client or a Redis error by falling back to
`default`, so a Redis outage degrades to "voice mode on" rather than crashing
a handler.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

_KEY_FMT = "chat:{chat_id}:voice_mode"


def _key(chat_id: int) -> str:
    return _KEY_FMT.format(chat_id=chat_id)


async def get_voice_mode(redis: Any, chat_id: int, default: bool = True) -> bool:
    """Read the toggle for `chat_id`. Missing key / no redis / error -> `default`."""
    if redis is None:
        return default
    try:
        value = await redis.get(_key(chat_id))
    except Exception:
        log.debug("voice_mode read failed for chat=%s", chat_id, exc_info=True)
        return default
    if value is None:
        return default
    if isinstance(value, bytes):
        value = value.decode()
    return str(value) == "on"


async def set_voice_mode(redis: Any, chat_id: int, on: bool) -> None:
    """Persist the toggle for `chat_id`. No-op (logged) if redis is unavailable."""
    if redis is None:
        return
    try:
        await redis.set(_key(chat_id), "on" if on else "off")
    except Exception:
        log.debug("voice_mode write failed for chat=%s", chat_id, exc_info=True)
