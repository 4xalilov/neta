"""Approval node (roadmap 4.2): LangGraph ``interrupt()`` — ega Telegram'da tasdiqlaydi.

Interrupt payload — ssenariy qisqacha + video URL + xarajat + VisionQA (worker uni
``tg:notify`` ga ``kind="video"`` qilib yuboradi). Resume qiymati::

    {"decision": "approve" | "reject" | "schedule", "hook_idx": int, "reason": str}

Diqqat: node resume paytida BOSHIDAN qayta ishlaydi — barcha yon ta'sirlar (DB yozuvi)
``interrupt()`` dan KEYIN. Tasdiq ham, rad ham ``taste_memory`` ga yoziladi (docs/01:
"har tasdiq/rad 'nega' izohi bilan"); embedding keyin (3.4) to'ldiriladi.
"""
from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from engine.models import Script as ScriptRow
from engine.models import TasteMemory, TasteMemoryKind

from ..state import DayState
from . import _common as c

DECISIONS = ("approve", "reject", "schedule")


def interrupt_payload(state: DayState) -> dict[str, Any]:
    script = state.get("script") or {}
    scores = {r.get("critic", ""): r.get("score", 0) for r in state.get("best_reviews") or []}
    return {
        "type": "video_approval",
        "script_id": state.get("script_id"),
        "hooks": script.get("hooks", []),
        "best_hook_idx": state.get("best_hook_idx", 0),
        "body": script.get("body", ""),
        "cta": script.get("cta", ""),
        "scores": scores,
        "best_score": state.get("best_score"),
        "video_url": state.get("video_url"),
        "duration_s": state.get("audio_duration_s"),
        "cost_usd": c.run_cost(state) or state.get("cost_usd", 0.0),
        "vision_qa": state.get("vision_qa") or {},
        "errors": list(state.get("errors") or []),
    }


def parse_decision(value: Any, default_hook: int = 0) -> dict[str, Any]:
    if isinstance(value, str):
        value = {"decision": value}
    if not isinstance(value, dict):
        value = {}
    decision = str(value.get("decision") or "reject").lower()
    if decision in ("publish", "yes", "ok"):
        decision = "approve"
    if decision not in DECISIONS:
        decision = "reject"
    try:
        hook_idx = int(value.get("hook_idx", default_hook))
    except (TypeError, ValueError):
        hook_idx = default_hook
    return {"decision": decision, "hook_idx": hook_idx,
            "reason": str(value.get("reason") or "").strip()}


async def _write_taste(state: DayState, decision: dict[str, Any]) -> None:
    ws_id = c.as_uuid(state.get("workspace_id"))
    script = state.get("script") or {}
    hooks = script.get("hooks") or [""]
    hook = hooks[min(decision["hook_idx"], len(hooks) - 1)] if hooks else ""
    text = f"Hook: {hook}\nBody: {script.get('body', '')}\nCTA: {script.get('cta', '')}"
    kind = TasteMemoryKind.REJECTED if decision["decision"] == "reject" \
        else TasteMemoryKind.APPROVED
    async with c.session() as s:
        s.add(TasteMemory(workspace_id=ws_id, kind=kind, text=text,
                          reason=decision["reason"] or None))
        script_id = c.as_uuid(state.get("script_id"))
        if decision["decision"] == "reject" and script_id is not None:
            row = await s.get(ScriptRow, script_id)
            if row is not None:
                row.status = "rejected"
        await s.commit()


async def approval(state: DayState) -> dict[str, Any]:
    raw = interrupt(interrupt_payload(state))
    decision = parse_decision(raw, state.get("best_hook_idx", 0))
    await _write_taste(state, decision)
    return {
        "decision": decision,
        "approved": decision["decision"] != "reject",
        "selected_hook_idx": decision["hook_idx"],
        "publish_status": "rejected" if decision["decision"] == "reject" else "",
    }


def route_after_approval(state: DayState) -> str:
    return "publish" if state.get("approved") else "__end__"
