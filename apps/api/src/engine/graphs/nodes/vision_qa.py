"""VisionQA node (roadmap 2.5 — skelet).

Hozircha videodan kadr ajratilmaydi (api konteynerida ffmpeg yo'q): vision modelga
SAHNA RASMLARI (props.scenes[].imageUrl) beriladi. TODO(2.5): kadr ajratish render
workerga ko'chadi (render tugagach 6 kadr png → MinIO ``frame``), bu node esa o'sha
kadr URL'larini oladi.
"""
from __future__ import annotations

import logging
from typing import Any

from engine import llm
from engine.agents import prompt_loader

from ..state import DayState
from . import _common as c

logger = logging.getLogger(__name__)

MAX_FRAMES = 6


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    issues = []
    for item in data.get("issues") or []:
        if isinstance(item, dict):
            issue = str(item.get("issue") or "").strip()
            if not issue:
                continue
            try:
                frame = int(item.get("frame", 0))
            except (TypeError, ValueError):
                frame = 0
            issues.append({"frame": frame, "issue": issue})
        elif isinstance(item, str) and item.strip():
            issues.append({"frame": 0, "issue": item.strip()})
    passed = data.get("pass")
    if not isinstance(passed, bool):
        passed = not issues
    return {"pass": passed, "issues": issues}


async def vision_qa(state: DayState) -> dict[str, Any]:
    scenes = (state.get("props") or {}).get("scenes") or []
    frames = [sc["imageUrl"] for sc in scenes if sc.get("imageUrl")][:MAX_FRAMES]
    if not frames:
        return {"vision_qa": {"pass": True, "issues": [], "skipped": True}}
    script = state.get("script") or {}
    system = prompt_loader.render(
        "vision_qa",
        brand_profile=state.get("brand_profile") or {},
        script={"hooks": script.get("hooks"), "cta": script.get("cta"),
                "scenes": [sc.get("img_prompt") for sc in script.get("scenes") or []]},
    )
    user = f"{len(frames)} ta kadr (0..{len(frames) - 1}) ketma-ket berildi. Faqat JSON qaytar."
    try:
        data = await llm.complete_json("vision", system, user, node="vision_qa",
                                       workspace_id=state.get("workspace_id", ""),
                                       images=frames)
        result = _normalize(data)
    except llm.LLMError as exc:  # QA xatosi videoni to'xtatmasin — egaga ogohlantirish
        logger.warning("vision_qa: %s", exc)
        return {"vision_qa": {"pass": True, "issues": [], "error": str(exc)},
                "errors": [f"VisionQA ishlamadi: {exc}"]}
    return {"vision_qa": result, "cost_usd": c.run_cost(state)}
