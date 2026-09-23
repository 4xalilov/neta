"""Yangi uslub (StyleTheme) taklifi: LLM (tier ``critic``) + internet ilhom (URL).

``propose`` faqat tema JSON'ini qaytaradi (hali bazaga yozilmagan — ``engine.
styles.registry.submit`` buni ``candidate`` qator qiladi). Mavjud nomlar bilan
to'qnashmasligi uchun ``style_theme`` jadvalidan o'zi o'qiydi.
"""

from __future__ import annotations

import logging
import re

import httpx
from sqlalchemy import select

from engine import llm
from engine.agents import prompt_loader
from engine.db import async_session
from engine.models.style import StyleTheme

from . import schema as style_schema

logger = logging.getLogger(__name__)

__all__ = ["propose", "propose_from_url"]

MAX_URL_BYTES = 20 * 1024
_URL_TIMEOUT_S = 15.0


async def _existing_names() -> list[str]:
    async with async_session() as session:
        rows = (await session.scalars(select(StyleTheme.name).order_by(StyleTheme.name))).all()
        return list(dict.fromkeys(rows))


async def _base_theme_json(base: str | None) -> dict | None:
    if not base:
        return None
    async with async_session() as session:
        row = await session.scalar(select(StyleTheme).where(StyleTheme.name == base))
        return dict(row.theme_json) if row and row.theme_json else None


async def propose(
    inspiration: str, *, niche: str = "", mood: str = "", base: str | None = None,
    workspace_id: str = "",
) -> dict:
    """Yangi ``StyleTheme`` JSON'ini taklif qiladi (sxemaga mos bo'lishga harakat qiladi).

    Sxemaga mos kelmasa xatolar bilan bir marta qayta so'raladi (``complete_json``
    o'zi ham JSON parse xatosida bitta qayta so'rov qiladi — bu ustiga sxema
    darajasidagi tekshiruv qo'shiladi).
    """
    schema_obj = style_schema.load_schema()
    existing = await _existing_names()
    base_theme = await _base_theme_json(base)

    system = prompt_loader.render(
        "style_proposer",
        schema=schema_obj,
        existing_names=existing,
        niche=niche or "—",
        mood=mood or "—",
        base_theme_name=base or "—",
        base_theme=base_theme or "—",
    )
    user = f"Ilhom: {inspiration}".strip()

    data = await llm.complete_json(
        "critic", system, user, node="style_proposer", workspace_id=workspace_id,
        max_tokens=4096,
    )

    problems = style_schema.validate_theme(data)
    if problems:
        repair_user = (
            f"{user}\n\nOldingi javobingiz JSON Schema'ga mos kelmadi:\n- "
            + "\n- ".join(problems)
            + "\n\nXatolarni tuzatib, TO'LIQ JSON obyektni qayta yuboring."
        )
        data = await llm.complete_json(
            "critic", system, repair_user, node="style_proposer", workspace_id=workspace_id,
            max_tokens=4096,
        )
    return data


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


async def propose_from_url(url: str) -> str:
    """Sahifa matnini "best effort" o'qiydi (20 KB chegara) — ilhom sifatida ishlatiladi.

    Tarmoq/HTTP xatosida bo'sh emas, tavsifli qator qaytaradi (chaqiruvchi buni
    ``inspiration`` sifatida ishlatishi mumkin — pipeline yiqilmasin).
    """
    try:
        async with httpx.AsyncClient(timeout=_URL_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw = resp.content[:MAX_URL_BYTES]
    except Exception as exc:  # noqa: BLE001 - best effort, tarmoq xatosi pipeline'ni to'xtatmasin
        logger.warning("proposer: %s dan ilhom matni olinmadi: %s", url, exc)
        return f"(havoladan matn olinmadi: {url})"

    text = _strip_html(raw.decode("utf-8", "ignore"))
    return text[:MAX_URL_BYTES]
