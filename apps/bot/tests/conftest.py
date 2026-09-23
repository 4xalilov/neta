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
        reply_markup: Any = None,
    ) -> None:
        self.text = text
        self.from_user = from_user or FakeUser(id=1, full_name="Test User")
        self.chat = SimpleNamespace(title=chat_title)
        self.reply_markup = reply_markup
        self.answer = AsyncMock(side_effect=self._answer)
        self.edit_text = AsyncMock()
        self.edit_reply_markup = AsyncMock()
        self._children: list[FakeMessage] = []

    async def _answer(self, text: str, reply_markup: Any = None) -> FakeMessage:
        msg = FakeMessage(text=text, from_user=self.from_user, reply_markup=reply_markup)
        self._children.append(msg)
        return msg


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
