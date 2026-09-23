"""``cost_tracker`` uchun DB sink: har yozuv ``cost_log`` jadvaliga qator bo'lib tushadi.

API (lifespan) va arq worker (on_startup) ``install()`` ni chaqiradi. ``workspace_id``
uuid bo'lmagan yozuvlar (masalan workspace'siz test chaqiriqlari) DB'ga yozilmaydi.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from engine import cost_tracker, db

logger = logging.getLogger(__name__)


async def db_sink(entry: dict[str, Any]) -> None:
    try:
        ws_id = uuid.UUID(str(entry.get("workspace_id") or ""))
    except ValueError:
        return
    from engine.models import CostLog

    node = entry.get("node") or entry.get("kind") or ""
    async with db.async_session() as s:
        s.add(CostLog(
            workspace_id=ws_id, node=str(node)[:100],
            provider=str(entry.get("provider") or "")[:50],
            tokens_in=int(entry.get("tokens_in") or 0),
            tokens_out=int(entry.get("tokens_out") or 0),
            usd=float(entry.get("usd") or 0.0),
        ))
        await s.commit()


def install() -> None:
    cost_tracker.set_sink(db_sink)


def uninstall() -> None:
    cost_tracker.set_sink(None)
