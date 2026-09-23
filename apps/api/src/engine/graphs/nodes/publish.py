"""Publish node — hozircha stub (Instagram nashri — roadmap 4.3).

Standart: ``script.status`` ni ``approved`` yoki ``scheduled`` qilib saqlaydi.
``state["publish_to_ig"]`` True bo'lsa — ``NotImplementedError`` (4.3 da Chatwoot/Graph API).
"""
from __future__ import annotations

from typing import Any

from engine.models import Script as ScriptRow

from ..state import DayState
from . import _common as c


async def publish(state: DayState) -> dict[str, Any]:
    decision = state.get("decision") or {}
    status = "scheduled" if decision.get("decision") == "schedule" else "approved"
    if state.get("publish_to_ig") and status == "approved":
        raise NotImplementedError("Instagram nashri — roadmap 4.3")
    script_id = c.as_uuid(state.get("script_id"))
    if script_id is not None:
        async with c.session() as s:
            row = await s.get(ScriptRow, script_id)
            if row is not None:
                row.status = status
                hooks = (row.hook_variants or {}).get("hooks") \
                    or (state.get("script") or {}).get("hooks", [])
                row.hook_variants = {"hooks": hooks,
                                     "selected": state.get("selected_hook_idx", 0)}
            await s.commit()
    return {"publish_status": status, "cost_usd": c.run_cost(state)}
