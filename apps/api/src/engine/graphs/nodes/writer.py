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
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from engine import llm
from engine.agents import prompt_loader
from engine.models import ContentPlan
from engine.models import Script as ScriptRow

from ..state import CriticReview, DayState, Script
from . import _common as c

logger = logging.getLogger(__name__)

CRITIC_LABELS = {"uz": "UzCritic", "brand": "BrandCritic", "hook": "HookCritic"}

# Motion-dizayn enum'lari — apps/render/src/motion/**/names.ts va docs/11 bilan sinxron.
ALLOWED_STYLES = {"bold", "minimal", "neon", "editorial", "corporate", "hype", "luxury"}
ALLOWED_TEXT_ANIMS = {
    "WordPop", "CharCascade", "MaskWipe", "TypeWriter", "SlideMask", "Glitch", "Counter",
    "Highlighter", "Split3D", "Scramble", "Kinetic", "Outline2Fill", "BounceIn", "BlurFocus",
}
ALLOWED_TRANSITIONS = {
    "fade", "slide", "wipe", "flip", "iris", "clockWipe", "zoomPunch", "whipPan",
    "glitchCut", "maskCircle", "slice", "none",
}
ALLOWED_CAPTION_PRESETS = {"karaoke", "boxHighlight", "pillGlass", "bigWord", "lineByLine"}
ALLOWED_KEN_BURNS = {"in", "out", "left", "right", "none"}

DEFAULT_STYLE = "bold"
_KEN_BURNS_CYCLE = ("in", "out", "left", "right")


def _lenient_enum(value: Any, allowed: set[str], field: str) -> str | None:
    """Noma'lum/bo'sh qiymatni ``None``ga o'tkazadi (render tarafidagi ``lenientEnum`` bilan
    bir xil tolerantlik) — sxema yiqilmaydi, faqat ogohlantirish yoziladi."""
    if value is None or value == "":
        return None
    if isinstance(value, str) and value in allowed:
        return value
    logger.warning("writer: noma'lum %s qiymati %r — None ga o'rnatildi", field, value)
    return None


class SceneModel(BaseModel):
    img_prompt: str = Field(min_length=1)
    duration_s: float = Field(ge=3, le=8)
    subtitle: str = ""
    title: str | None = None
    text_anim: str | None = None
    transition: str | None = None
    fx: list[str] = Field(default_factory=list)
    ken_burns: str | None = None

    @field_validator("text_anim", mode="before")
    @classmethod
    def _check_text_anim(cls, v: Any) -> str | None:
        return _lenient_enum(v, ALLOWED_TEXT_ANIMS, "text_anim")

    @field_validator("transition", mode="before")
    @classmethod
    def _check_transition(cls, v: Any) -> str | None:
        return _lenient_enum(v, ALLOWED_TRANSITIONS, "transition")

    @field_validator("ken_burns", mode="before")
    @classmethod
    def _check_ken_burns(cls, v: Any) -> str | None:
        return _lenient_enum(v, ALLOWED_KEN_BURNS, "ken_burns")

    @field_validator("fx", mode="before")
    @classmethod
    def _check_fx(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [x for x in v if isinstance(x, str) and x]


class ScriptModel(BaseModel):
    hooks: list[str] = Field(min_length=3, max_length=3)
    body: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    tts_text: str = Field(min_length=1)
    display_text: str = Field(min_length=1)
    scenes: list[SceneModel] = Field(min_length=3, max_length=6)
    style: str | None = None
    hook_text: str | None = None
    caption_preset: str | None = None

    @field_validator("style", mode="before")
    @classmethod
    def _check_style(cls, v: Any) -> str | None:
        return _lenient_enum(v, ALLOWED_STYLES, "style")

    @field_validator("caption_preset", mode="before")
    @classmethod
    def _check_caption_preset(cls, v: Any) -> str | None:
        return _lenient_enum(v, ALLOWED_CAPTION_PRESETS, "caption_preset")


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
    if out.get("hook_text"):
        out["hook_text"] = c.display_text(out["hook_text"])
    for scene in out["scenes"]:
        scene["subtitle"] = c.display_text(scene.get("subtitle") or "")
        if scene.get("title"):
            scene["title"] = c.display_text(scene["title"])
    return out  # type: ignore[return-value]


_WORD_STRIP_RE = " .,!?:;\"'()«»"


def _star_longest_word(words: list[str]) -> str:
    """Berilgan so'zlar orasidan eng uzunini ``*...*`` bilan belgilaydi (birinchisi teng bo'lsa)."""
    if not words:
        return ""
    idx = max(range(len(words)), key=lambda i: len(words[i].strip(_WORD_STRIP_RE)))
    out = list(words)
    out[idx] = f"*{out[idx]}*"
    return " ".join(out)


def _default_hook_text(hook: str) -> str | None:
    words = hook.split()[:6]
    if not words:
        return None
    return _star_longest_word(words)


_DIGIT_RE = re.compile(r"\d")


def _default_text_anim(scene: dict[str, Any], index: int, total: int) -> str:
    if index == 0:
        return "WordPop"
    if index == total - 1:
        return "BounceIn"
    text = f"{scene.get('title') or ''} {scene.get('subtitle') or ''}"
    if _DIGIT_RE.search(text):
        return "Counter"
    return "BlurFocus"


def apply_default_motion(script: Script, brand_profile: dict | None,
                         best_hook_idx: int = 0) -> Script:
    """LLM motion-maydonlarini bo'sh qoldirgan bo'lsa, deterministik standartlarni
    to'ldiradi (docs/11 "Writer qanday tanlaydi"). Render props har doim to'liq bo'lishi
    uchun ``asset_gen`` bu funksiyani props qurishdan oldin chaqiradi."""
    brand = brand_profile or {}
    out: dict[str, Any] = dict(script)

    if not out.get("style"):
        style = brand.get("style")
        out["style"] = style if style in ALLOWED_STYLES else DEFAULT_STYLE

    if not out.get("hook_text"):
        hooks = out.get("hooks") or []
        idx = best_hook_idx if hooks and 0 <= best_hook_idx < len(hooks) else 0
        out["hook_text"] = _default_hook_text(hooks[idx]) if hooks else None

    scenes = [dict(sc) for sc in out.get("scenes") or []]
    n = len(scenes)
    for i, sc in enumerate(scenes):
        if not sc.get("text_anim"):
            sc["text_anim"] = _default_text_anim(sc, i, n)
        if not sc.get("transition"):
            sc["transition"] = "zoomPunch" if i == 1 else "fade"
        if not sc.get("ken_burns"):
            sc["ken_burns"] = _KEN_BURNS_CYCLE[i % len(_KEN_BURNS_CYCLE)]
    out["scenes"] = scenes
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
