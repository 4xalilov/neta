"""Nodlar uchun umumiy yordamchilar: DB sessiya, uuid, xarajat, o'zbek normalizatori."""
from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from typing import Any

from engine import cost_tracker, db
from engine.uz import normalize as uz_normalize

from ..state import DayState


def session():
    """``engine.db.async_session()`` — runtime'da o'qiladi (testlar monkeypatch qiladi)."""
    return db.async_session()


def as_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def run_cost(state: DayState) -> float:
    """Shu run xarajati: ``cost_tracker.RECENT`` dagi workspace yozuvlari ``started_at`` dan beri.

    Cheklov: bitta workspace'da parallel ikki run bo'lsa, ikkalasi ham bir-birining
    xarajatini ko'radi; jarayon qayta ishga tushsa ``RECENT`` bo'shaydi (to'liq hisob —
    ``cost_log`` jadvalida).
    """
    ws = state.get("workspace_id", "")
    since = state.get("started_at", 0.0) or 0.0
    return round(
        sum(e["usd"] for e in cost_tracker.RECENT
            if e["workspace_id"] == ws and e["ts"] >= since),
        6,
    )


def now() -> float:
    return time.time()


def _fn(name: str) -> Callable[[str], str] | None:
    fn = getattr(uz_normalize, name, None)
    return fn if callable(fn) else None


def tts_text(text: str) -> str:
    fn = _fn("to_tts_text")
    return fn(text) if fn else text


def display_text(text: str) -> str:
    """``to_display_text`` bo'lsa u, bo'lmasa faqat apostrof normalizatsiyasi."""
    fn = _fn("to_display_text") or _fn("normalize_apostrophes")
    return fn(text) if fn else text


def subtitle_lines(text: str, max_chars: int = 42) -> list[str]:
    """``uz.normalize.subtitle_lines`` bo'lsa u, aks holda so'z chegarasida oddiy bo'lish."""
    fn = getattr(uz_normalize, "subtitle_lines", None)
    if callable(fn):
        try:
            return list(fn(text, max_chars))
        except TypeError:
            return list(fn(text))
    lines: list[str] = []
    cur = ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if len(cand) > max_chars and cur:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
