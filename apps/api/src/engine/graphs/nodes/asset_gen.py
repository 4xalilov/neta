"""AssetGen node (roadmap 1.7, 2.4): TTS ∥ FLUX (har sahna) ∥ (ixtiyoriy) Depth → Remotion props.

Props shakli ``apps/render/src/props.ts`` (``reelsPropsSchema``) ga mos::

    {"audioUrl", "cta", "style", "hookText", "captionPreset",
     "scenes": [{"imageUrl", "depthUrl"?, "durationS", "words", "subtitle",
                 "title", "textAnim", "transition", "fx", "kenBurns"}],
     "brand": {"font", "color", "accent", "bg", "surface", "logoUrl"}}

``words`` vaqtlari KOMPOZITSIYA boshiga nisbatan (sahnaga emas). Sahna davomiyliklari
ovoz davomiyligiga proporsional moslanadi (``fit_scene_durations``), so'zlar esa shu
chegaralar bo'yicha sahnalarga bo'linadi (``split_words_by_scenes``).

Motion-dizayn maydonlari (``style``/``hookText``/``captionPreset`` va sahna
``title``/``textAnim``/``transition``/``fx``/``kenBurns``) Writer'dan keladi; ``writer.
apply_default_motion`` LLM bo'sh qoldirgan qiymatlarni deterministik standartlar bilan
to'ldiradi, shu sababli props har doim to'liq bo'ladi (docs/11-motion-library.md).
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from engine.integrations import images, storage, tts
from engine.models import Asset
from engine.settings import settings

from ..state import DayState
from . import _common as c
from .writer import apply_default_motion

logger = logging.getLogger(__name__)

TAIL_S = 0.5  # ovoz tugagach CTA ko'rinib turishi uchun
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_AUDIO_CT = {"mp3": "audio/mpeg", "wav": "audio/wav"}


def fit_scene_durations(durations: list[float], total_s: float) -> list[float]:
    """Sahna davomiyliklarini nisbatini saqlab ``total_s`` ga moslaydi (total ≤ 0 → o'zgarmaydi)."""
    s = sum(durations)
    if total_s <= 0 or s <= 0:
        return [float(d) for d in durations]
    return [round(d * total_s / s, 3) for d in durations]


def split_words_by_scenes(words: list[dict[str, Any]],
                          durations: list[float]) -> list[list[dict[str, Any]]]:
    """So'zlarni sahna chegaralari (davomiylik yig'indisi) bo'yicha taqsimlaydi.

    So'z o'rtasi (start+end)/2 qaysi sahna oralig'iga tushsa — o'sha sahnaga.
    Oxirgi chegaradan keyingi so'zlar oxirgi sahnaga. Vaqtlar absolyut qoladi.
    """
    out: list[list[dict[str, Any]]] = [[] for _ in durations]
    if not durations:
        return out
    bounds: list[float] = []
    t = 0.0
    for d in durations:
        t += d
        bounds.append(t)
    idx = 0
    for w in sorted(words, key=lambda x: x.get("start", 0.0)):
        mid = (w.get("start", 0.0) + w.get("end", w.get("start", 0.0))) / 2
        while idx < len(bounds) - 1 and mid >= bounds[idx]:
            idx += 1
        out[idx].append(w)
    return out


def brand_props(brand: dict) -> dict[str, Any]:
    """brand_profile → Remotion ``brand`` (faqat to'g'ri qiymatlar; qolgani props.ts default)."""
    out: dict[str, Any] = {}
    if isinstance(brand.get("font"), str) and brand["font"]:
        out["font"] = brand["font"]
    for key, sources in (("color", ("color", "text_color", "text")),
                         ("accent", ("subtitle_color", "accent")),
                         ("bg", ("bg",)), ("surface", ("surface",))):
        for src in sources:
            val = brand.get(src)
            if isinstance(val, str) and _HEX_RE.match(val):
                out[key] = val
                break
    logo = brand.get("logoUrl") or brand.get("logo_url")
    if isinstance(logo, str) and logo:
        out["logoUrl"] = logo
    return out


async def _tts(state: DayState, text: str) -> tuple[tts.TTSResult, str]:
    brand = state.get("brand_profile") or {}
    voice = brand.get("tts_voice")  # masalan "uz-UZ-MadinaNeural"; yo'q bo'lsa settings
    ws = state.get("workspace_id", "")
    result = await tts.synthesize(text, voice=voice, workspace_id=ws, node="tts")
    fmt = result.format if result.format in _AUDIO_CT else "mp3"
    uri = await storage.put_bytes(storage.key_for(ws, "audio", fmt), result.audio, _AUDIO_CT[fmt])
    return result, uri


async def _image(state: DayState, prompt: str) -> images.ImageResult:
    brand = state.get("brand_profile") or {}
    return await images.generate_image(
        images.reels_prompt(prompt, brand), tier=settings.flux_draft_tier,  # type: ignore[arg-type]
        workspace_id=state.get("workspace_id", ""), node="flux",
    )


async def _persist(state: DayState, audio_uri: str, audio_meta: dict,
                   image_uris: list[str], depth_uris: list[str]) -> None:
    script_id = c.as_uuid(state.get("script_id"))
    if script_id is None:
        return
    async with c.session() as s:
        s.add(Asset(script_id=script_id, kind="audio", uri=audio_uri, meta=audio_meta))
        for i, uri in enumerate(image_uris):
            s.add(Asset(script_id=script_id, kind="image", uri=uri, meta={"scene": i}))
        for i, uri in enumerate(depth_uris):
            if uri:
                s.add(Asset(script_id=script_id, kind="depth", uri=uri, meta={"scene": i}))
        await s.commit()


async def asset_gen(state: DayState) -> dict[str, Any]:
    raw_script = state.get("best_script") or state["script"]
    script = apply_default_motion(raw_script, state.get("brand_profile"),
                                  state.get("best_hook_idx", 0))
    scenes = script["scenes"]
    plan_item = state.get("plan_item") or {}
    parallax = bool(plan_item.get("parallax"))

    (tts_result, audio_uri), *imgs = await asyncio.gather(
        _tts(state, script["tts_text"]),
        *(_image(state, sc["img_prompt"]) for sc in scenes),
    )
    image_results: list[images.ImageResult] = list(imgs)

    depth_uris: list[str] = []
    if parallax:
        depths = await asyncio.gather(
            *(images.depth_map(img.url, workspace_id=state.get("workspace_id", ""))
              for img in image_results),
            return_exceptions=True,
        )
        for d in depths:
            if isinstance(d, BaseException):
                logger.warning("asset_gen: depth map xato: %s", d)
                depth_uris.append("")
            else:
                depth_uris.append(d.uri)

    words = tts.words_to_subtitle_json(tts_result.words, script.get("display_text"))
    audio_total = tts_result.duration_s + TAIL_S if tts_result.duration_s > 0 else 0.0
    durations = fit_scene_durations([float(sc["duration_s"]) for sc in scenes], audio_total)
    words_by_scene = split_words_by_scenes(words, durations)

    props_scenes: list[dict[str, Any]] = []
    for i, sc in enumerate(scenes):
        item: dict[str, Any] = {
            "imageUrl": storage.public_url(image_results[i].uri),
            "durationS": durations[i],
            "words": words_by_scene[i],
            "subtitle": sc.get("subtitle") or None,
            "title": sc.get("title") or None,
            "textAnim": sc.get("text_anim") or None,
            "transition": sc.get("transition") or None,
            "fx": sc.get("fx") or None,
            "kenBurns": sc.get("ken_burns") or None,
        }
        if parallax and i < len(depth_uris) and depth_uris[i]:
            item["depthUrl"] = storage.public_url(depth_uris[i])
        props_scenes.append(item)

    audio_url = storage.public_url(audio_uri)
    props = {
        "audioUrl": audio_url,
        "cta": script.get("cta"),
        "scenes": props_scenes,
        "brand": brand_props(state.get("brand_profile") or {}),
        "style": script.get("style"),
        "hookText": script.get("hook_text"),
        "captionPreset": script.get("caption_preset"),
    }
    image_uris = [r.uri for r in image_results]
    await _persist(state, audio_uri,
                   {"provider": tts_result.provider, "voice": tts_result.voice,
                    "duration_s": tts_result.duration_s, "format": tts_result.format},
                   image_uris, depth_uris)
    return {
        "audio_uri": audio_uri,
        "audio_url": audio_url,
        "audio_duration_s": tts_result.duration_s,
        "image_uris": image_uris,
        "depth_uris": depth_uris,
        "composition": "ReelsParallax" if parallax and any(depth_uris) else "ReelsBasic",
        "props": props,
        "cost_usd": c.run_cost(state),
    }
