"""Writer node (roadmap 1.1, 2.2): brif/reja + brend + did + kritik izohlari → Script JSON.

- 0-iteratsiya — ``draft`` tier (Flash/Haiku), 1+ — ``critic`` tier (Sonnet) (docs/04).
- Javob pydantic bilan tekshiriladi; yaroqsiz bo'lsa xato matni bilan 1 marta qayta so'raladi.
- ``tts_text`` → ``uz.to_tts_text``, ``display_text`` → ``uz.to_display_text`` (bo'lmasa apostrof).
- ``iteration`` +1, ``reviews`` tozalanadi (``None`` sentinel, qarang ``state.merge_reviews``).
- ``script`` jadvaliga yoziladi (birinchi marta yaratiladi, keyin yangilanadi); brif uchun
  ``content_plan`` yo'q bo'lsa ``status="adhoc"`` reja yaratiladi (``script.plan_id`` majburiy).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from engine import llm
from engine.agents import prompt_loader
from engine.models import ContentPlan
from engine.models import Script as ScriptRow

from ..state import CriticReview, DayState, Script
from . import _common as c

logger = logging.getLogger(__name__)

CRITIC_LABELS = {"uz": "UzCritic", "brand": "BrandCritic", "hook": "HookCritic"}


class SceneModel(BaseModel):
    img_prompt: str = Field(min_length=1)
    duration_s: float = Field(ge=3, le=8)
    subtitle: str = ""


class ScriptModel(BaseModel):
    hooks: list[str] = Field(min_length=3, max_length=3)
    body: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    tts_text: str = Field(min_length=1)
    display_text: str = Field(min_length=1)
    scenes: list[SceneModel] = Field(min_length=3, max_length=6)


def address_form(brand: dict) -> str:
    form = brand.get("address_form") or brand.get("pronoun") or "siz"
    return f'"{form}"'


def format_previous_reviews(state: DayState) -> str:
    reviews: list[CriticReview] = list(state.get("reviews") or [])
    if not reviews or not state.get("script"):
        return "Bu birinchi iteratsiya — kritik izohlari yo'q."
    lines = ["Avvalgi ssenariy:", c.dumps(state["script"]), "", "Kritiklar bahosi:"]
    for r in reviews:
        label = CRITIC_LABELS.get(r.get("critic", ""), r.get("critic", ""))
        lines.append(f"- {label}: {r.get('score', 0)}/10")
        for reason in r.get("reasons") or []:
            lines.append(f"  sabab: {reason}")
        for fix in r.get("fixes") or []:
            lines.append(f"  tuzatish: {fix}")
    return "\n".join(lines)


def build_prompt(state: DayState) -> str:
    brand = state.get("brand_profile") or {}
    return prompt_loader.render(
        "writer",
        brief=state.get("brief") or "",
        plan_item=state.get("plan_item") or {},
        brand_profile=brand,
        taste=state.get("taste") or [],
        references=state.get("references") or [],
        previous_reviews=format_previous_reviews(state),
        address_form=address_form(brand),
    )


def validate_script(data: dict[str, Any]) -> Script:
    model = ScriptModel.model_validate(data)
    out = model.model_dump()
    out["tts_text"] = c.tts_text(out["tts_text"])
    out["display_text"] = c.display_text(out["display_text"])
    out["hooks"] = [c.display_text(h) for h in out["hooks"]]
    for scene in out["scenes"]:
        scene["subtitle"] = c.display_text(scene.get("subtitle") or "")
    return out  # type: ignore[return-value]


async def _generate(state: DayState, iteration: int) -> Script:
    tier: llm.Tier = "draft" if iteration == 0 else "critic"
    system = build_prompt(state)
    user = f"Brif: {state.get('brief') or '—'}\nSsenariyni JSON ko'rinishida yoz."
    ws = state.get("workspace_id", "")
    data = await llm.complete_json(tier, system, user, node="writer", workspace_id=ws,
                                   max_tokens=3000)
    try:
        return validate_script(data)
    except ValidationError as exc:
        logger.warning("writer: yaroqsiz ssenariy, qayta so'ralmoqda: %s", exc)
        retry_user = (
            f"{user}\n\nAvvalgi javobing sxemaga mos emas edi: {exc.errors(include_url=False)}\n"
            "Aynan 3 hook, 3–6 sahna, har sahna duration_s 3–8 bo'lsin."
        )
        data = await llm.complete_json(tier, system, retry_user, node="writer",
                                       workspace_id=ws, max_tokens=3000)
        return validate_script(data)


async def _persist(state: DayState, script: Script, iteration: int) -> tuple[str, str]:
    ws_id = c.as_uuid(state.get("workspace_id"))
    if ws_id is None:
        raise ValueError(f"workspace_id uuid emas: {state.get('workspace_id')!r}")
    async with c.session() as s:
        plan_id = c.as_uuid(state.get("plan_id"))
        if plan_id is None:
            plan = ContentPlan(
                workspace_id=ws_id, week_start=datetime.now(UTC).date(), status="adhoc",
                aida_json={"brief": state.get("brief", ""),
                           "plan_item": state.get("plan_item") or {}},
            )
            s.add(plan)
            await s.flush()
            plan_id = plan.id
        row = None
        script_id = c.as_uuid(state.get("script_id"))
        if script_id is not None:
            row = await s.get(ScriptRow, script_id)
        if row is None:
            row = ScriptRow(workspace_id=ws_id, plan_id=plan_id, day=state.get("day", 0))
            s.add(row)
        row.hook_variants = {"hooks": script["hooks"], "selected": 0}
        row.body = script["body"]
        row.cta = script["cta"]
        row.tts_text = script["tts_text"]
        row.subtitle_json = {
            "display_text": script["display_text"],
            "scenes": [sc.get("subtitle", "") for sc in script["scenes"]],
        }
        row.iteration = iteration
        row.status = "draft"
        await s.commit()
        return str(row.id), str(plan_id)


async def writer(state: DayState) -> dict[str, Any]:
    iteration = state.get("iteration", 0)
    script = await _generate(state, iteration)
    script_id, plan_id = await _persist(state, script, iteration + 1)
    return {
        "script": script,
        "script_id": script_id,
        "plan_id": plan_id,
        "iteration": iteration + 1,
        "reviews": None,  # joriy iteratsiya baholarini tozalash
        "script_ready": False,
    }
