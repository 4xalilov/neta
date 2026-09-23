from typing import TypedDict


class Scene(TypedDict):
    img_prompt: str
    duration_s: float
    subtitle: str


class Script(TypedDict):
    hooks: list[str]
    body: str
    cta: str
    tts_text: str
    display_text: str
    scenes: list[Scene]


class CriticReview(TypedDict):
    critic: str
    score: int
    reasons: list[str]
    fixes: list[str]


class DayState(TypedDict, total=False):
    workspace_id: str
    day: int
    plan_item: dict          # AIDA bosqichi, format, hook turi
    brand_profile: dict
    taste: list[str]         # taste_memory top-k
    references: list[dict]   # referens strukturalar
    script: Script
    reviews: list[CriticReview]
    iteration: int
    audio_uri: str
    image_uris: list[str]
    depth_uris: list[str]
    video_uri: str
    vision_qa: dict
    approved: bool
    cost_usd: float
