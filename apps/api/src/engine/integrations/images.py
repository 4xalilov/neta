"""FLUX (fal.ai) orqali rasm generatsiyasi + Depth Anything orqali chuqurlik xaritasi.

Qoralama — ``schnell`` (tez/arzon), tasdiqlangan — ``dev``/``pro`` (docs/01, docs/03 1.4).
Natija darhol MinIO'ga (``engine.integrations.storage``) yuklanadi va xarajat
``engine.cost_tracker.log_media`` orqali qayd etiladi (mavjud bo'lsa).

``set_fake_generator`` / ``clear_fake_generator`` — graf testlarida tarmoqqa chiqmasdan
``generate_image``ni almashtirish uchun.
"""
from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

import fal_client

from engine import cost_tracker
from engine.integrations.storage import download_to_storage, key_for
from engine.settings import settings

Tier = Literal["schnell", "dev", "pro"]

# fal.ai FLUX modellari (https://fal.ai/models, tekshirilgan 2026-09-23).
MODELS: dict[Tier, str] = {
    "schnell": "fal-ai/flux/schnell",
    "dev": "fal-ai/flux/dev",
    "pro": "fal-ai/flux-pro/v1.1",
}

# Bitta rasm narxi, $ — fal.ai ommaviy narxlari, holat 2026-09-23 (docs/01: xarajat nishoni).
PRICES: dict[Tier, float] = {
    "schnell": 0.003,
    "dev": 0.025,
    "pro": 0.04,
}

# Depth Anything v2 preprocessor model id (fal.ai/models katalogi, tekshirilgan 2026-09-23).
DEPTH_MODEL = "fal-ai/image-preprocessors/depth-anything/v2"
DEPTH_PRICE_USD = 0.01  # taxminiy narx; real invoysga qarab keyin moslanadi

NEGATIVE_PROMPT = (
    "text, watermark, logo, subtitles, blurry, low quality, distorted face, "
    "extra limbs, cropped, out of frame, duplicate, jpeg artifacts"
)


@dataclass
class ImageResult:
    uri: str
    url: str
    width: int
    height: int
    seed: int | None
    usd: float
    model: str


@dataclass
class DepthResult:
    uri: str
    url: str
    usd: float


FakeGenerator = Callable[..., Awaitable[ImageResult]]
_fake_generator: FakeGenerator | None = None


def set_fake_generator(fn: FakeGenerator) -> None:
    """Graf testlarida ``generate_image``ni tarmoqsiz stub bilan almashtiradi."""
    global _fake_generator
    _fake_generator = fn


def clear_fake_generator() -> None:
    global _fake_generator
    _fake_generator = None


def reels_prompt(scene_prompt: str, brand: dict) -> str:
    """Sahna prompti + brend uslub ko'rsatmalari (docs/08 rang tokenlari)."""
    bg = brand.get("bg", "#0B0F19")
    accent = brand.get("accent", "#FACC15")
    primary = brand.get("primary", "#6366F1")
    return (
        f"{scene_prompt}, brand mood board colors {bg} deep background, "
        f"{primary} and {accent} accent lighting, "
        "vertical 9:16, cinematic, no text, no watermark"
    )


def _sync_fal_key() -> None:
    if settings.fal_key:
        os.environ["FAL_KEY"] = settings.fal_key


async def generate_image(
    prompt: str,
    *,
    tier: Tier = "schnell",
    width: int = 1080,
    height: int = 1920,
    seed: int | None = None,
    workspace_id: str = "",
    node: str = "flux",
) -> ImageResult:
    if _fake_generator is not None:
        return await _fake_generator(
            prompt,
            tier=tier,
            width=width,
            height=height,
            seed=seed,
            workspace_id=workspace_id,
            node=node,
        )

    _sync_fal_key()
    model = MODELS[tier]
    arguments: dict = {
        "prompt": prompt,
        "image_size": {"width": width, "height": height},
        "negative_prompt": NEGATIVE_PROMPT,
    }
    if seed is not None:
        arguments["seed"] = seed

    result = await fal_client.run_async(model, arguments=arguments)
    images = result.get("images") or []
    if not images:
        raise RuntimeError(f"FLUX ({model}) rasm qaytarmadi: {result}")
    img = images[0]
    usd = PRICES[tier]

    uri = await download_to_storage(
        img["url"], key_for(workspace_id, "image", "jpg"), content_type="image/jpeg"
    )

    log_media = getattr(cost_tracker, "log_media", None)
    if log_media is not None:
        await log_media(
            workspace_id, node, "fal", usd, meta={"model": model, "kind": "image"}
        )

    return ImageResult(
        uri=uri,
        url=img["url"],
        width=img.get("width", width),
        height=img.get("height", height),
        seed=result.get("seed", seed),
        usd=usd,
        model=model,
    )


async def depth_map(image_url: str, *, workspace_id: str = "") -> DepthResult:
    _sync_fal_key()
    result = await fal_client.run_async(DEPTH_MODEL, arguments={"image_url": image_url})
    depth = result.get("image") or (result.get("images") or [None])[0] or {}
    depth_url = depth.get("url")
    if not depth_url:
        raise RuntimeError(f"Depth Anything ({DEPTH_MODEL}) rasm qaytarmadi: {result}")

    uri = await download_to_storage(
        depth_url, key_for(workspace_id, "depth", "png"), content_type="image/png"
    )

    log_media = getattr(cost_tracker, "log_media", None)
    if log_media is not None:
        await log_media(
            workspace_id, "depth", "fal", DEPTH_PRICE_USD,
            meta={"model": DEPTH_MODEL, "kind": "depth"},
        )

    return DepthResult(uri=uri, url=depth_url, usd=DEPTH_PRICE_USD)
