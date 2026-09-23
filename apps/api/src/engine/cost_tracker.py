"""Har LLM/TTS/FLUX chaqirig'i shu yerga yoziladi (cost_log jadvali).

- ``price()`` — model narx jadvali bo'yicha $ hisoblaydi.
- ``log()`` / ``log_media()`` — yozuvni xotiradagi ``RECENT`` ga qo'shadi va, agar
  ``set_sink()`` orqali DB sink ro'yxatdan o'tgan bo'lsa, unga ham uzatadi.
- ``summary()`` — workspace bo'yicha jami $ va node kesimi (``RECENT`` asosida).

Bu modul ``engine.models`` ni import qilmaydi: DB yozuvi sink orqali ulanadi.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

# (input $/1M token, output $/1M token). Narxlar: 2026-09-23 holatiga.
# Claude — Anthropic first-party API narxlari (claude-api skill, cached 2026-06-24).
# Gemini — Google AI Studio ommaviy narxlari (<=200k prompt, paid tier).
PRICES_USD_PER_1M: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-fable-5-1": (10.0, 50.0),
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    # Google
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}

RECENT: deque[dict[str, Any]] = deque(maxlen=1000)

Sink = Callable[[dict[str, Any]], Awaitable[None]]
_sink: Sink | None = None


def _lookup(model: str) -> tuple[float, float] | None:
    """Aniq moslik, bo'lmasa eng uzun prefiks (masalan ``gemini-2.5-flash-001``)."""
    if model in PRICES_USD_PER_1M:
        return PRICES_USD_PER_1M[model]
    best = max((k for k in PRICES_USD_PER_1M if model.startswith(k)), key=len, default=None)
    return PRICES_USD_PER_1M[best] if best else None


def price(model: str, tokens_in: int, tokens_out: int) -> float:
    """Chaqiriq narxi ($). Noma'lum model — 0.0 va ogohlantirish."""
    p = _lookup(model)
    if p is None:
        logger.warning("cost_tracker: narx jadvalida yo'q model: %s", model)
        return 0.0
    return (tokens_in * p[0] + tokens_out * p[1]) / 1_000_000


def set_sink(sink: Sink | None) -> None:
    """DB sinkni ro'yxatdan o'tkazish (``None`` — o'chirish). Sink yozuv dict'ini oladi."""
    global _sink
    _sink = sink


async def _emit(entry: dict[str, Any]) -> None:
    RECENT.append(entry)
    if _sink is not None:
        try:
            await _sink(entry)
        except Exception:  # sink xatosi asosiy chaqiriqni buzmasligi kerak
            logger.exception("cost_tracker: sink yozuvida xato")


async def log(workspace_id: str, node: str, provider: str, model: str,
              tokens_in: int, tokens_out: int, usd: float, kind: str = "llm") -> None:
    await _emit({
        "ts": time.time(), "workspace_id": workspace_id, "node": node, "kind": kind,
        "provider": provider, "model": model, "tokens_in": tokens_in,
        "tokens_out": tokens_out, "usd": usd, "meta": {},
    })


async def log_media(workspace_id: str, node: str, provider: str, usd: float,
                    meta: dict[str, Any] | None = None, kind: str = "media") -> None:
    """TTS / FLUX / render kabi token'siz xarajatlar uchun."""
    await _emit({
        "ts": time.time(), "workspace_id": workspace_id, "node": node, "kind": kind,
        "provider": provider, "model": (meta or {}).get("model", ""), "tokens_in": 0,
        "tokens_out": 0, "usd": usd, "meta": dict(meta or {}),
    })


def summary(workspace_id: str) -> dict[str, Any]:
    """``{"usd_total": float, "by_node": {node: usd}}`` — ``RECENT`` bo'yicha."""
    by_node: dict[str, float] = {}
    total = 0.0
    for e in RECENT:
        if e["workspace_id"] != workspace_id:
            continue
        total += e["usd"]
        by_node[e["node"]] = by_node.get(e["node"], 0.0) + e["usd"]
    return {"usd_total": total, "by_node": by_node}
