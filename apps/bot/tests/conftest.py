from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest


class FakeUser(SimpleNamespace):
    id: int
    full_name: str


class FakeMessage:
    """Minimal stand-in for aiogram's Message, enough for handler tests."""

    def __init__(
        self,
        text: str | None = None,
        from_user: FakeUser | None = None,
        chat_title: str | None = None,
        chat_id: int = 1,
        reply_markup: Any = None,
        voice: Any = None,
        audio: Any = None,
    ) -> None:
        self.text = text
        self.from_user = from_user or FakeUser(id=1, full_name="Test User")
        self.chat = SimpleNamespace(title=chat_title, id=chat_id)
        self.reply_markup = reply_markup
        self.voice = voice
        self.audio = audio
        self.answer = AsyncMock(side_effect=self._answer)
        self.answer_voice = AsyncMock(side_effect=self._answer_voice)
        self.answer_audio = AsyncMock(side_effect=self._answer_audio)
        self.edit_text = AsyncMock()
        self.edit_reply_markup = AsyncMock()
        self._children: list[FakeMessage] = []
        self.voice_notes_sent: list[Any] = []
        self.audio_notes_sent: list[Any] = []

    async def _answer(self, text: str, reply_markup: Any = None) -> FakeMessage:
        msg = FakeMessage(
            text=text, from_user=self.from_user, chat_id=self.chat.id, reply_markup=reply_markup
        )
        self._children.append(msg)
        return msg

    async def _answer_voice(self, voice: Any, **kwargs: Any) -> FakeMessage:
        self.voice_notes_sent.append(voice)
        msg = FakeMessage(from_user=self.from_user, chat_id=self.chat.id)
        self._children.append(msg)
        return msg

    async def _answer_audio(self, audio: Any, **kwargs: Any) -> FakeMessage:
        self.audio_notes_sent.append(audio)
        msg = FakeMessage(from_user=self.from_user, chat_id=self.chat.id)
        self._children.append(msg)
        return msg


class FakeBot:
    """Minimal stand-in for aiogram's Bot, only `download()` is used by handlers."""

    def __init__(self, downloaded: bytes = b"fake-ogg-bytes") -> None:
        import io

        self._buf = io.BytesIO(downloaded)
        self.download = AsyncMock(return_value=self._buf)


class FakeRedis:
    """In-memory stand-in for redis.asyncio.Redis, enough for bot/voice_mode.py."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str) -> None:
        self.store[key] = value


class FakeCallbackQuery:
    def __init__(self, data: str, message: FakeMessage | None = None, from_user: FakeUser | None = None) -> None:
        self.data = data
        self.message = message
        self.from_user = from_user or FakeUser(id=1, full_name="Test User")
        self.answer = AsyncMock()


class FakeApiClient:
    """Records calls and returns pre-programmed results; raises on `*_error` flags."""

    def __init__(self, **results: Any) -> None:
        self.results = results
        self.calls: list[tuple[str, tuple, dict]] = []

    async def _call(self, _name: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((_name, args, kwargs))
        if _name in self.results:
            result = self.results[_name]
            if isinstance(result, Exception):
                raise result
            return result
        return {}

    def __getattr__(self, name: str):
        async def method(*args: Any, **kwargs: Any) -> Any:
            return await self._call(name, *args, **kwargs)

        return method


@pytest.fixture
def fake_user() -> FakeUser:
    return FakeUser(id=1, full_name="Test User")
