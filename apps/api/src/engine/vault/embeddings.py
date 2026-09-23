"""Vault embedding provayderlari (docs/10-obsidian-vault.md).

``settings.embedding_provider``:
- ``hash`` (standart, offline) — deterministik 768 o'lchamli hashed bag-of-words,
  L2 normalangan. Internet/kalit kerak emas, testlarda ishlatiladi.
- ``gemini`` — ``google-genai`` ``embed_content`` (model ``gemini-embedding-001``,
  ``output_dimensionality=768``). Lazy import — testlarda ishlatilmaydi.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import re

from engine.settings import settings

__all__ = ["DIM", "cosine", "embed"]

DIM = 768
_TOKEN_RE = re.compile(r"[^\W\d_][\w']*|\d+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _hash_embed_one(text: str) -> list[float]:
    vec = [0.0] * DIM
    for tok in _tokenize(text):
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        h = int.from_bytes(digest[:8], "big")
        idx = h % DIM
        sign = 1.0 if (h >> 63) & 1 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


async def _embed_hash(texts: list[str]) -> list[list[float]]:
    return [_hash_embed_one(t) for t in texts]


async def _embed_gemini(texts: list[str]) -> list[list[float]]:
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=settings.gemini_api_key)

    def _call() -> list[list[float]]:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=texts,
            config=genai_types.EmbedContentConfig(output_dimensionality=DIM),
        )
        return [list(e.values) for e in result.embeddings]

    return await asyncio.to_thread(_call)


async def embed(texts: list[str]) -> list[list[float]]:
    """Berilgan matnlarni ``settings.embedding_provider`` bo'yicha vektorlaydi."""
    if not texts:
        return []
    if settings.embedding_provider == "gemini":
        return await _embed_gemini(texts)
    return await _embed_hash(texts)


def cosine(a: list[float], b: list[float]) -> float:
    """Kosinus o'xshashligi; bo'sh/nol vektor bo'lsa 0.0."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
