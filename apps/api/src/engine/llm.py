"""Yagona LLM kirish nuqtasi. Hech qayerda SDK to'g'ridan-to'g'ri chaqirilmaydi.

Ommaviy API:
- ``complete(tier, system, user, *, json_mode=False, node="", workspace_id="", ...) -> LLMResult``
- ``complete_json(tier, system, user, *, node="", workspace_id="", ...) -> dict``
- ``set_fake(handler)`` / ``clear_fake()`` — testlar uchun provayderlarni chetlab o'tish.
- ``parse_json(text) -> dict`` — ```json bloklari, ortiqcha vergul va h.k.ni tuzatib o'qiydi.

Tier -> model ``settings`` dan: draft / critic / vision / final. Provayder model id'dan
aniqlanadi: ``gemini*`` -> google-genai, ``claude*`` -> anthropic. Har muvaffaqiyatli
chaqiriq ``cost_tracker.log`` orqali yoziladi.
"""
from __future__ import annotations

import asyncio
import base64
import inspect
import json
import logging
import random
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

import anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from engine import cost_tracker
from engine.settings import settings

__all__ = [
    "LLMError",
    "LLMJSONError",
    "LLMRefusalError",
    "LLMResult",
    "Tier",
    "clear_fake",
    "complete",
    "complete_json",
    "parse_json",
    "set_fake",
]

logger = logging.getLogger(__name__)

Tier = Literal["draft", "critic", "vision", "final"]
ImageInput = bytes | str  # xom bayt, http(s) URL yoki data: URL
FakeHandler = Callable[[Tier, str, str], "str | dict | Awaitable[str | dict]"]

DEFAULT_MAX_TOKENS = 2048
RETRY_BASE_DELAY_S = 1.0  # 1s, 2s, 4s ... (+ jitter); testlarda 0 qilinadi

# Claude Opus 5 / Fable 5.x: refusal bo'lsa server tomonda boshqa modelga o'tish.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODEL_PREFIXES = ("claude-opus-5", "claude-fable-5", "claude-mythos-5")
# temperature faqat shu (eski) modellarda qabul qilinadi; Opus 4.7+/Sonnet 5/Fable 400 qaytaradi.
_SAMPLING_MODEL_PREFIXES = (
    "claude-haiku-4", "claude-sonnet-4", "claude-opus-4-6", "claude-opus-4-5",
    "claude-opus-4-1", "claude-opus-4-0", "claude-3",
)

JSON_SYSTEM_SUFFIX = (
    "\n\nReturn ONLY a single valid JSON object. No markdown code fences, "
    "no commentary before or after the JSON."
)
JSON_RETRY_NUDGE = (
    "\n\nYour previous reply was not valid JSON. Return only valid JSON: one JSON object, "
    "no markdown fences, no explanations."
)


class LLMError(RuntimeError):
    """LLM chaqirig'i muvaffaqiyatsiz (retry'lardan keyin ham)."""


class LLMRefusalError(LLMError):
    """Model xavfsizlik sababli rad etdi (``stop_reason == "refusal"``)."""


class LLMJSONError(LLMError, ValueError):
    """Javobni JSON sifatida o'qib bo'lmadi."""


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    usd: float
    model: str = ""
    provider: str = ""


# ---------------------------------------------------------------- fake (testlar)

_fake: FakeHandler | None = None


def set_fake(handler: FakeHandler) -> None:
    """``complete`` provayderlarni chetlab o'tib ``handler(tier, system, user)`` ni qaytaradi.

    Handler ``str`` yoki ``dict`` (JSON'ga aylantiriladi) qaytaradi, async ham bo'lishi mumkin.
    Tokenlar ``len/4`` bilan taxmin qilinadi, $ narx jadvalidan hisoblanadi.
    """
    global _fake
    _fake = handler


def clear_fake() -> None:
    global _fake
    _fake = None


# ---------------------------------------------------------------- clients

_anthropic: anthropic.AsyncAnthropic | None = None
_gemini: genai.Client | None = None


def _anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        # retry'ni o'zimiz boshqaramiz (ikki qavat retry bo'lmasin)
        _anthropic = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key or None,
            max_retries=0,
            timeout=settings.llm_timeout_s,
        )
    return _anthropic


def _gemini_client() -> genai.Client:
    global _gemini
    if _gemini is None:
        _gemini = genai.Client(api_key=settings.gemini_api_key or None)
    return _gemini


# ---------------------------------------------------------------- helpers

def _model_for(tier: Tier) -> str:
    models = {
        "draft": settings.llm_draft_model,
        "critic": settings.llm_critic_model,
        "vision": settings.llm_vision_model,
        "final": settings.llm_final_model,
    }
    if tier not in models:
        raise ValueError(f"Noma'lum tier: {tier!r}")
    return models[tier]


def _provider_for(model: str) -> str:
    if model.startswith("gemini"):
        return "google"
    if model.startswith("claude"):
        return "anthropic"
    raise ValueError(f"Model id'dan provayderni aniqlab bo'lmadi: {model!r}")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _sniff_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return "image/png"


def _mime_from_url(url: str) -> str:
    path = url.split("?", 1)[0].lower()
    for ext, mime in ((".png", "image/png"), (".webp", "image/webp"), (".gif", "image/gif")):
        if path.endswith(ext):
            return mime
    return "image/jpeg"


def _decode_data_url(url: str) -> tuple[bytes, str]:
    header, _, payload = url.partition(",")
    mime = header[5:].split(";", 1)[0] or "image/png"
    return base64.b64decode(payload), mime


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
        return True
    if isinstance(exc, anthropic.APIConnectionError):  # APITimeoutError ham shu yerda
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (408, 409, 429) or exc.status_code >= 500
    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", 0) or 0
        return code in (408, 429) or code >= 500
    return False


async def _with_retry(call: Callable[[], Awaitable[Any]], what: str) -> Any:
    attempts = max(1, settings.llm_max_retries)
    for attempt in range(attempts):
        try:
            return await asyncio.wait_for(call(), timeout=settings.llm_timeout_s)
        except Exception as exc:
            if not _is_transient(exc) or attempt == attempts - 1:
                raise
            delay = RETRY_BASE_DELAY_S * (2 ** attempt)
            delay += random.uniform(0, RETRY_BASE_DELAY_S)
            logger.warning("llm: %s vaqtinchalik xato (%s), %d-urinish %.1fs keyin",
                           what, type(exc).__name__, attempt + 2, delay)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


# ---------------------------------------------------------------- providers

async def _call_anthropic(model: str, system: str, user: str, *, json_mode: bool,
                          max_tokens: int, temperature: float | None,
                          images: list[ImageInput] | None,
                          effort: str | None) -> tuple[str, int, int, str]:
    content: str | list[dict[str, Any]] = user
    if images:
        blocks: list[dict[str, Any]] = []
        for img in images:
            if isinstance(img, bytes):
                source = {"type": "base64", "media_type": _sniff_mime(img),
                          "data": base64.standard_b64encode(img).decode("ascii")}
            elif img.startswith("data:"):
                raw, mime = _decode_data_url(img)
                source = {"type": "base64", "media_type": mime,
                          "data": base64.standard_b64encode(raw).decode("ascii")}
            else:
                source = {"type": "url", "url": img}
            blocks.append({"type": "image", "source": source})
        blocks.append({"type": "text", "text": user})
        content = blocks

    # Yangi modellarda assistant prefill taqiqlangan — JSON'ni system orqali so'raymiz.
    sys_text = system + JSON_SYSTEM_SUFFIX if json_mode else system
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if sys_text.strip():
        kwargs["system"] = sys_text
    if effort:
        kwargs["output_config"] = {"effort": effort}
    if temperature is not None:
        if model.startswith(_SAMPLING_MODEL_PREFIXES):
            kwargs["extra_body"] = {"temperature": temperature}
        else:
            logger.debug("llm: %s temperature qabul qilmaydi, e'tiborsiz qoldirildi", model)

    client = _anthropic_client()
    if model.startswith(_FALLBACK_MODEL_PREFIXES):
        resp = await client.beta.messages.create(
            **kwargs, betas=[_FALLBACK_BETA], fallbacks="default",
        )
    else:
        resp = await client.messages.create(**kwargs)

    if resp.stop_reason == "refusal":
        details = getattr(resp, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        raise LLMRefusalError(f"{model} rad etdi (category={category})")
    if resp.stop_reason == "max_tokens":
        logger.warning("llm: %s max_tokens=%d ga yetdi, javob kesilgan bo'lishi mumkin",
                       model, max_tokens)

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    usage = resp.usage
    tokens_in = (usage.input_tokens
                 + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
                 + (getattr(usage, "cache_read_input_tokens", 0) or 0))
    served_by = getattr(resp, "model", None) or model  # fallback ishlagan bo'lishi mumkin
    return text, tokens_in, usage.output_tokens, served_by


async def _call_gemini(model: str, system: str, user: str, *, json_mode: bool,
                       max_tokens: int, temperature: float | None,
                       images: list[ImageInput] | None,
                       audio: bytes | None = None,
                       audio_mime: str | None = None) -> tuple[str, int, int, str]:
    contents: Any = user
    if images or audio:
        parts: list[Any] = []
        if audio:  # inline audio part (STT, roadmap 5.10) — Gemini audio/ogg|wav|mp3 qabul qiladi
            parts.append(genai_types.Part.from_bytes(data=audio,
                                                     mime_type=audio_mime or "audio/ogg"))
        for img in images or []:
            if isinstance(img, bytes):
                parts.append(genai_types.Part.from_bytes(data=img, mime_type=_sniff_mime(img)))
            elif img.startswith("data:"):
                raw, mime = _decode_data_url(img)
                parts.append(genai_types.Part.from_bytes(data=raw, mime_type=mime))
            else:
                parts.append(genai_types.Part.from_uri(file_uri=img, mime_type=_mime_from_url(img)))
        parts.append(user)
        contents = parts

    config = genai_types.GenerateContentConfig(
        system_instruction=system or None,
        max_output_tokens=max_tokens,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )
    resp = await _gemini_client().aio.models.generate_content(
        model=model, contents=contents, config=config,
    )
    text = resp.text or ""
    um = resp.usage_metadata
    tokens_in = (getattr(um, "prompt_token_count", 0) or 0) if um else 0
    tokens_out = 0
    if um:  # "thinking" tokenlari ham output narxida hisoblanadi
        tokens_out = ((getattr(um, "candidates_token_count", 0) or 0)
                      + (getattr(um, "thoughts_token_count", 0) or 0))
    return text, tokens_in, tokens_out, model


# ---------------------------------------------------------------- public API

async def complete(tier: Tier, system: str, user: str, *, json_mode: bool = False,
                   node: str = "", workspace_id: str = "",
                   max_tokens: int = DEFAULT_MAX_TOKENS, temperature: float | None = None,
                   images: list[ImageInput] | None = None,
                   effort: str | None = None,
                   audio: bytes | None = None,
                   audio_mime: str | None = None) -> LLMResult:
    """Bitta LLM chaqiriq: tier bo'yicha model, retry, timeout, cost_tracker.

    ``images`` — bayt, http(s) URL yoki data: URL ro'yxati (odatda ``tier="vision"``).
    ``audio`` + ``audio_mime`` (masalan ``"audio/ogg"``) — FAQAT Gemini modellari (STT,
    ``engine.integrations.stt.GeminiSTT``); Claude modeliga audio berilsa ``LLMError``.
    ``temperature`` — faqat qabul qiladigan modellarga yuboriladi (Gemini, eski Claude).
    ``effort`` — faqat Claude (``low|medium|high|xhigh|max``).
    """
    model = _model_for(tier)
    if audio is not None and not model.startswith("gemini"):
        raise LLMError(
            f"audio kirish faqat Gemini provayderida qo'llab-quvvatlanadi ({tier} tier -> {model})"
        )

    if _fake is not None:
        out = _fake(tier, system, user)
        if inspect.isawaitable(out):
            out = await out
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        tokens_in = _estimate_tokens(system + user)
        tokens_out = _estimate_tokens(text)
        usd = cost_tracker.price(model, tokens_in, tokens_out)
        await cost_tracker.log(workspace_id, node, "fake", model, tokens_in, tokens_out, usd)
        return LLMResult(text, tokens_in, tokens_out, usd, model=model, provider="fake")

    provider = _provider_for(model)
    if provider == "anthropic":
        async def call() -> tuple[str, int, int, str]:
            return await _call_anthropic(model, system, user, json_mode=json_mode,
                                         max_tokens=max_tokens, temperature=temperature,
                                         images=images, effort=effort)
    else:
        async def call() -> tuple[str, int, int, str]:
            return await _call_gemini(model, system, user, json_mode=json_mode,
                                      max_tokens=max_tokens, temperature=temperature,
                                      images=images, audio=audio, audio_mime=audio_mime)

    text, tokens_in, tokens_out, served_by = await _with_retry(call, f"{provider}:{model}")
    usd = cost_tracker.price(served_by, tokens_in, tokens_out)
    await cost_tracker.log(workspace_id, node, provider, served_by, tokens_in, tokens_out, usd)
    return LLMResult(text, tokens_in, tokens_out, usd, model=served_by, provider=provider)


_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def parse_json(text: str) -> dict:
    """LLM javobidan JSON obyektini o'qiydi, keng tarqalgan xatolarni tuzatadi.

    Tuzatiladi: ```json ... ``` bloklari, JSON atrofidagi matn, ortiqcha vergullar,
    "aqlli" qo'shtirnoqlar. Obyekt (dict) bo'lmasa — ``LLMJSONError``.
    """
    s = text.strip().lstrip("﻿")
    m = _FENCE_RE.search(s)
    if m:
        s = m.group(1).strip()

    candidates = [s]
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        candidates.append(s[start:end + 1])

    for cand in candidates:
        for variant in (cand, _repair(cand)):
            try:
                val = json.loads(variant)
            except json.JSONDecodeError:
                continue
            if isinstance(val, dict):
                return val
    raise LLMJSONError(f"JSON obyekt emas: {text[:200]!r}")


def _repair(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"')
    return _TRAILING_COMMA_RE.sub(r"\1", s)


async def complete_json(tier: Tier, system: str, user: str, *, node: str = "",
                        workspace_id: str = "", max_tokens: int = DEFAULT_MAX_TOKENS,
                        temperature: float | None = None,
                        images: list[ImageInput] | None = None,
                        effort: str | None = None,
                        audio: bytes | None = None,
                        audio_mime: str | None = None) -> dict:
    """``complete(json_mode=True)`` + ``parse_json``; yaroqsiz bo'lsa 1 marta qayta so'raydi."""
    kw: dict[str, Any] = {
        "json_mode": True, "node": node, "workspace_id": workspace_id,
        "max_tokens": max_tokens, "temperature": temperature,
        "images": images, "effort": effort, "audio": audio, "audio_mime": audio_mime,
    }
    res = await complete(tier, system, user, **kw)
    try:
        return parse_json(res.text)
    except LLMJSONError:
        logger.warning("llm: %s/%s yaroqsiz JSON qaytardi, qayta so'ralmoqda", tier, node)
    res = await complete(tier, system, user + JSON_RETRY_NUDGE, **kw)
    return parse_json(res.text)
