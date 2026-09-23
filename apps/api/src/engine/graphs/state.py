"""DaySubgraph holati (LangGraph ``StateGraph(DayState)``).

Holat faqat oddiy dict/list/str/son qiymatlardan iborat — Postgres checkpointer
(``langgraph-checkpoint-postgres``) uni serializatsiya qila olishi uchun.

``reviews`` reduceri (``merge_reviews``):
- kritik nodlar ``{"reviews": [review]}`` qaytaradi — ro'yxatlar qo'shiladi
  (3 kritik parallel ishlaydi, fan-out);
- writer har iteratsiya boshida ``{"reviews": None}`` qaytaradi — ro'yxat tozalanadi
  (``None`` sentinel). Shu tariqa ``reviews`` doimo faqat JORIY iteratsiya baholari.
Barcha iteratsiyalar tarixi ``review_history`` da (``operator.add``).
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class Scene(TypedDict, total=False):
    img_prompt: str
    duration_s: float
    subtitle: str
    # --- motion-dizayn (docs/11, apps/render/src/props.ts sceneSchema)
    title: str | None
    text_anim: str | None
    transition: str | None
    fx: list[str]
    ken_burns: str | None


class Script(TypedDict):
    hooks: list[str]
    body: str
    cta: str
    tts_text: str
    display_text: str
    scenes: list[Scene]
    # --- motion-dizayn (docs/11, apps/render/src/props.ts reelsPropsSchema)
    style: str | None
    hook_text: str | None
    caption_preset: str | None


class CriticReview(TypedDict, total=False):
    critic: str              # "uz" | "brand" | "hook"
    score: int               # 0–10
    reasons: list[str]
    fixes: list[str]
    best_hook_idx: int       # faqat hook kritik
    iteration: int


def merge_reviews(left: list | None, right: list | None) -> list:
    """``None`` → tozalash (writer yangi iteratsiya boshlaganda), aks holda qo'shish."""
    if right is None:
        return []
    return list(left or []) + list(right)


class DayState(TypedDict, total=False):
    # --- kirish
    workspace_id: str
    thread_id: str
    brief: str
    day: int
    plan_id: str             # content_plan.id (brif uchun avtomatik "adhoc" reja)
    plan_item: dict          # AIDA bosqichi, format, hook turi, parallax: bool
    brand_profile: dict
    taste: list[str]         # taste_memory top-k
    references: list[dict]   # referens strukturalar
    started_at: float        # run boshlangan vaqt (time.time()) — xarajat hisobi uchun
    publish_to_ig: bool      # True bo'lsa publish nodi IG'ga chiqaradi (4.3, hali yo'q)

    # --- writer ↔ critics halqasi
    script: Script
    script_id: str
    iteration: int
    reviews: Annotated[list[CriticReview], merge_reviews]
    review_history: Annotated[list[CriticReview], operator.add]
    best_script: Script
    best_score: int
    best_reviews: list[CriticReview]
    best_hook_idx: int
    script_ready: bool

    # --- aktivlar va render
    audio_uri: str
    audio_url: str
    audio_duration_s: float
    image_uris: list[str]
    depth_uris: list[str]
    composition: str         # "ReelsBasic" | "ReelsParallax"
    props: dict[str, Any]    # Remotion props (apps/render/src/props.ts)
    render_job_id: str
    video_uri: str
    video_url: str
    vision_qa: dict

    # --- tasdiq / nashr
    decision: dict           # interrupt() dan qaytgan qaror
    approved: bool
    selected_hook_idx: int
    publish_status: str      # approved | scheduled | rejected

    cost_usd: float
    errors: Annotated[list[str], operator.add]
