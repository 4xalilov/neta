"""Kritik nodlar (roadmap 2.1, 2.2): UzCritic ∥ BrandCritic ∥ HookCritic → collect.

Har kritik alohida async node, ``{"reviews": [CriticReview]}`` qaytaradi — ``reviews``
reduceri ro'yxatlarni qo'shadi (fan-out: writer → 3 kritik → collect).
``collect`` — join nodi: ``critic_review`` jadvaliga yozadi, eng yaxshi versiyani
(``best_script``/``best_score`` — kritiklar MINIMUM bali bo'yicha) saqlaydi va halqa
tugaganda (o'tdi yoki ``MAX_ITER``) ``script`` ni eng yaxshisiga almashtiradi.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

from engine import llm
from engine.agents import prompt_loader
from engine.models import CriticReview as CriticReviewRow
from engine.models import Script as ScriptRow

from ..state import CriticReview, DayState
from . import _common as c

logger = logging.getLogger(__name__)

MAX_ITER = 3
PASS_SCORE = 8


class ReviewModel(BaseModel):
    score: int = 0
    reasons: list[str] = Field(default_factory=list)
    fixes: list[str] = Field(default_factory=list)
    best_hook_idx: int | None = None

    @field_validator("score", mode="before")
    @classmethod
    def _clamp_score(cls, v: Any) -> int:
        try:
            return max(0, min(10, round(float(v))))
        except (TypeError, ValueError):
            return 0

    @field_validator("reasons", "fixes", mode="before")
    @classmethod
    def _as_str_list(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [x if isinstance(x, str) else c.dumps(x) for x in v]


def _allowed_loanwords(brand: dict) -> str:
    words = brand.get("allowed_loanwords") or brand.get("allowed_russian") or []
    if isinstance(words, str):
        return words
    return ", ".join(words) if words else "yo'q (hech qanday ruscha/jargon so'z ruxsat etilmagan)"


def _address_form(brand: dict) -> str:
    form = brand.get("address_form") or brand.get("pronoun") or "siz"
    return f'"{form}"'


async def _review(state: DayState, critic: str, prompt_name: str) -> CriticReview:
    brand = state.get("brand_profile") or {}
    script = state.get("script") or {}
    system = prompt_loader.render(
        prompt_name,
        brand_profile=brand,
        taste=state.get("taste") or [],
        references=state.get("references") or [],
        plan_item=state.get("plan_item") or {},
        script=script,
        address_form=_address_form(brand),
        allowed_loanwords=_allowed_loanwords(brand),
    )
    user = "Ssenariyni rubrika bo'yicha baholab, faqat JSON qaytar."
    data = await llm.complete_json("critic", system, user, node=f"{critic}_critic",
                                   workspace_id=state.get("workspace_id", ""))
    model = ReviewModel.model_validate(data)
    review: CriticReview = {
        "critic": critic,
        "score": model.score,
        "reasons": model.reasons,
        "fixes": model.fixes,
        "iteration": state.get("iteration", 0),
    }
    if critic == "hook":
        n_hooks = len(script.get("hooks") or []) or 1
        idx = model.best_hook_idx if model.best_hook_idx is not None else 0
        review["best_hook_idx"] = max(0, min(n_hooks - 1, idx))
    return review


async def uz_critic(state: DayState) -> dict[str, Any]:
    return {"reviews": [await _review(state, "uz", "uz_critic")]}


async def brand_critic(state: DayState) -> dict[str, Any]:
    return {"reviews": [await _review(state, "brand", "brand_critic")]}


async def hook_critic(state: DayState) -> dict[str, Any]:
    return {"reviews": [await _review(state, "hook", "hook_critic")]}


def min_score(reviews: list[CriticReview]) -> int:
    return min((r.get("score", 0) for r in reviews), default=0)


async def _persist(state: DayState, reviews: list[CriticReview], final: dict | None) -> None:
    script_id = c.as_uuid(state.get("script_id"))
    if script_id is None:
        return
    async with c.session() as s:
        for r in reviews:
            s.add(CriticReviewRow(
                script_id=script_id, critic=r.get("critic", ""), score=r.get("score", 0),
                reasons={"reasons": r.get("reasons", []), "fixes": r.get("fixes", []),
                         "iteration": r.get("iteration"),
                         "best_hook_idx": r.get("best_hook_idx")},
            ))
        row = await s.get(ScriptRow, script_id)
        if row is not None:
            row.score = min_score(reviews)
            if final is not None:
                best = final["script"]
                row.hook_variants = {"hooks": best["hooks"], "selected": final["hook_idx"]}
                row.body = best["body"]
                row.cta = best["cta"]
                row.tts_text = best["tts_text"]
                row.subtitle_json = {
                    "display_text": best["display_text"],
                    "scenes": [sc.get("subtitle", "") for sc in best["scenes"]],
                }
                row.score = final["score"]
                row.status = "ready"
        await s.commit()


async def collect(state: DayState) -> dict[str, Any]:
    reviews = list(state.get("reviews") or [])
    score = min_score(reviews)
    iteration = state.get("iteration", 0)
    update: dict[str, Any] = {"review_history": reviews}

    best_score = state.get("best_score", -1)
    if best_score is None or score > best_score or not state.get("best_script"):
        hook = next((r for r in reviews if r.get("critic") == "hook"), {})
        update.update({
            "best_script": state.get("script"),
            "best_score": score,
            "best_reviews": reviews,
            "best_hook_idx": hook.get("best_hook_idx", 0),
        })

    passed = bool(reviews) and score >= PASS_SCORE
    final: dict | None = None
    if passed or iteration >= MAX_ITER:
        best = update.get("best_script") or state.get("best_script") or state.get("script")
        best_sc = update.get("best_score", state.get("best_score", score))
        hook_idx = update.get("best_hook_idx", state.get("best_hook_idx", 0))
        update["script"] = best
        update["script_ready"] = True
        final = {"script": best, "score": best_sc, "hook_idx": hook_idx}
        if not passed:
            msg = (f"Kritiklar {MAX_ITER} iteratsiyada {PASS_SCORE} ballga yetmadi; "
                   f"eng yaxshi versiya ({best_sc}/10) bilan davom etildi.")
            logger.warning("collect: %s", msg)
            update["errors"] = [msg]
    await _persist(state, reviews, final)
    return update
