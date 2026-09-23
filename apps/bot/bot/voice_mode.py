"""Per-chat "🎙 Jarvis rejimi" flag: when on, the owner's plain text messages are
also routed to `/v1/voice/command` (as `text`) instead of only the old
button-driven flows. Stored in Redis as ``chat:{id}:voice_mode`` -> ``"on"``/``"off"``.

Default is **on** for the owner (roadmap 5.10: "har voice xabar buyruq";
typed short commands are the text-mode equivalent of that). Every function here
tolerates a missing/``None`` redis client or a Redis error by falling back to
`default`, so a Redis outage degrades to "voice mode on" rather than crashing
a handler.

Also holds the sibling "active workspace" stickiness key
(``chat:{id}:workspace_id``): the API's `/v1/voice/command` response carries
the workspace that ended up active after the command (e.g. after "fitnes
klub uchun 3 ta reels tayyorla" switches the active client), and the bot
remembers it per chat so every later `voice_command` call from that chat
sends it back as `workspace_id` (`bot/handlers/voice.py`).
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

_KEY_FMT = "chat:{chat_id}:voice_mode"
_WORKSPACE_KEY_FMT = "chat:{chat_id}:workspace_id"


def _key(chat_id: int) -> str:
    return _KEY_FMT.format(chat_id=chat_id)


def _workspace_key(chat_id: int) -> str:
    return _WORKSPACE_KEY_FMT.format(chat_id=chat_id)


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


async def get_active_workspace(redis: Any, chat_id: int) -> str | None:
    """Read the sticky active `workspace_id` for `chat_id`. No redis / missing
    key / error -> ``None`` (callers fall back to `get_workspace`)."""
    if redis is None:
        return None
    try:
        value = await redis.get(_workspace_key(chat_id))
    except Exception:
        log.debug("active workspace read failed for chat=%s", chat_id, exc_info=True)
        return None
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode()
    return str(value)


async def set_active_workspace(redis: Any, chat_id: int, workspace_id: str) -> None:
    """Persist the sticky active `workspace_id` for `chat_id`. No-op (logged)
    if redis is unavailable."""
    if redis is None:
        return
    try:
        await redis.set(_workspace_key(chat_id), workspace_id)
    except Exception:
        log.debug("active workspace write failed for chat=%s", chat_id, exc_info=True)
