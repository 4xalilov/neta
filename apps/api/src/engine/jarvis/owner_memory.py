"""Ega suhbat xotirasi (roadmap 5.10): oxirgi N almashuv → niyat prompti.

"uni ertaga qil", "o'sha lidga yoz", "yana bir marta" kabi havolalarni LLM hal qilishi uchun
``recent()`` natijasi ``jarvis_intents.md`` promptiga ``{history}`` sifatida beriladi. Bundan
tashqari ``engine.jarvis.intents`` deterministik zaxira qiladi (LLM havolani hal qilmasa):
``last_value(turns, "lead_ids")`` va h.k.

Jadval: ``engine.models.owner.OwnerMemory`` (``owner_memory``).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.models.owner import OwnerMemory

ROLES = ("user", "jarvis")


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


async def remember(
    session: AsyncSession,
    *,
    chat_id: int,
    role: str,
    text: str,
    workspace_id: Any = None,
    intent: dict | None = None,
) -> OwnerMemory:
    """Bitta qator yozadi (``flush``; ``commit`` — chaqiruvchida).

    ``created_at`` Python soatidan (mikrosekund bilan) — sqlite'da ``now()`` soniya aniqligida,
    bir soniyada yozilgan user/jarvis qatorlari tartibi buzilmasin.
    """
    if role not in ROLES:
        raise ValueError(f"owner_memory: noto'g'ri role {role!r}")
    row = OwnerMemory(
        workspace_id=_uuid_or_none(workspace_id),
        chat_id=int(chat_id),
        role=role,
        text=text or "",
        intent_json=intent,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


async def recent(session: AsyncSession, chat_id: int, n: int = 10) -> list[OwnerMemory]:
    """Shu chatning oxirgi ``n`` qatori, eskidan yangiga (prompt uchun tabiiy tartib)."""
    if n <= 0:
        return []
    rows = await session.scalars(
        select(OwnerMemory)
        .where(OwnerMemory.chat_id == int(chat_id))
        .order_by(OwnerMemory.created_at.desc())
        .limit(n)
    )
    return list(reversed(list(rows)))


def as_prompt_turns(turns: list[OwnerMemory]) -> list[dict[str, Any]]:
    """Promptga beriladigan ixcham ko'rinish: ``[{role, text, intent?, entities?, ...}]``."""
    out: list[dict[str, Any]] = []
    for t in turns:
        item: dict[str, Any] = {"role": t.role, "text": t.text}
        data = t.intent_json or {}
        if data.get("intent"):
            item["intent"] = data["intent"]
        ents = {k: v for k, v in (data.get("entities") or {}).items() if v not in (None, "")}
        if ents:
            item["entities"] = ents
        for key in ("lead_names", "staff_name", "action_ids"):
            if data.get(key):
                item[key] = data[key]
        out.append(item)
    return out


def last_value(turns: list[OwnerMemory], key: str, *, role: str | None = None) -> Any:
    """Eng yangi qatordan boshlab ``intent_json[key]`` (yoki ``entities[key]``) ni qidiradi."""
    for t in reversed(turns):
        if role and t.role != role:
            continue
        data = t.intent_json or {}
        if data.get(key) not in (None, "", []):
            return data[key]
        ents = data.get("entities") or {}
        if ents.get(key) not in (None, "", []):
            return ents[key]
    return None


def last_user_intent(turns: list[OwnerMemory], *, skip: int = 0) -> dict | None:
    """Oxirgi (``skip`` tasini tashlab) ega niyati — "yana bir marta" uchun."""
    seen = 0
    for t in reversed(turns):
        if t.role != "user" or not (t.intent_json or {}).get("intent"):
            continue
        if seen >= skip:
            return dict(t.intent_json or {})
        seen += 1
    return None
