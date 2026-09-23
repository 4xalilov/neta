"""Yagona LLM kirish nuqtasi. Hech qayerda SDK to'g'ridan-to'g'ri chaqirilmaydi.

TODO (0.4): anthropic va google-genai adapterlari, retry, JSON-mode, cost_tracker.
"""
from dataclasses import dataclass
from typing import Literal

Tier = Literal["draft", "critic", "vision"]


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    usd: float


async def complete(tier: Tier, system: str, user: str, *, json_mode: bool = False,
                   node: str = "", workspace_id: str = "") -> LLMResult:
    raise NotImplementedError("0.4 vazifasida amalga oshiriladi")
