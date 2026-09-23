"""TTS adapter: bir nechta provayder bitta interfeys orqali (bosqich 1.2).

Qaror va nomzodlar: docs/09-tts-research.md. O'zbek matn qoidalari: docs/05-uzbek-language.md.
Provayder tanlash — ``settings.tts_provider``; xato bo'lsa ``settings.tts_fallback`` ga o'tadi.
TTS'ga yuboriladigan matn va subtitr matni bir manbadan (``script.tts_text``), shuning uchun
bu modul faqat sof matn oladi va uni ``engine.uz.normalize.to_tts_text`` orqali o'zi normalizatsiya
qiladi — chaqiruvchi tomon qayta normalizatsiya qilmasin.

Xarajat ``engine.cost_tracker.log_media`` orqali yoziladi (mavjud bo'lmasa jim o'tkazib yuboriladi —
cost_tracker boshqa vazifada yozilmoqda).
"""
from __future__ import annotations

import logging
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

import httpx

from engine import cost_tracker
from engine.settings import settings
from engine.uz.normalize import to_tts_text

logger = logging.getLogger(__name__)


# ---------- ma'lumot turlari ----------


@dataclass
class WordTiming:
    word: str
    start_s: float
    end_s: float


@dataclass
class TTSResult:
    audio: bytes
    format: str  # "mp3" | "wav"
    sample_rate: int
    duration_s: float
    words: list[WordTiming]
    provider: str
    voice: str
    usd: float
    chars: int


class TTSProvider(Protocol):
    name: str

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0
    ) -> TTSResult: ...


# ---------- yordamchi funksiyalar ----------

_PAUSE_CHARS = set(".,!?;:—-")
_MP3_ESTIMATE_BITRATE_BPS = 48_000  # edge-tts/aisha odatda 48kbps mono mp3 beradi


def estimate_word_timings(text: str, duration_s: float) -> list[WordTiming]:
    """So'z-timing proporsional taxmin (belgi soni + tinish belgisi uchun kichik pauza og'irligi).

    Provayder o'z timing'ini bermaganda ishlatiladi (masalan Navoiy/Aisha).
    """
    words = text.split()
    if not words or duration_s <= 0:
        return []
    weights: list[int] = []
    for w in words:
        weight = len(w)
        if w and w[-1] in _PAUSE_CHARS:
            weight += 2  # tinish belgisidan keyingi pauza
        weights.append(max(weight, 1))
    total = sum(weights)
    out: list[WordTiming] = []
    t = 0.0
    for w, wt in zip(words, weights):
        dur = duration_s * wt / total
        out.append(WordTiming(word=w, start_s=t, end_s=t + dur))
        t += dur
    out[-1] = WordTiming(word=out[-1].word, start_s=out[-1].start_s, end_s=duration_s)
    return out


def wav_duration(data: bytes) -> float:
    with wave.open(BytesIO(data), "rb") as f:
        rate = f.getframerate()
        return f.getnframes() / float(rate) if rate else 0.0


def _wav_sample_rate(data: bytes) -> int:
    with wave.open(BytesIO(data), "rb") as f:
        return f.getframerate()


def mp3_duration(data: bytes) -> float:
    """Mumkin bo'lsa ``mutagen`` orqali aniq, aks holda 48kbps taxmin (mutagen deps'ga qo'shilmagan)."""
    try:
        from mutagen.mp3 import MP3  # type: ignore[import-not-found]

        return float(MP3(BytesIO(data)).info.length)
    except Exception:  # noqa: BLE001 — mutagen yo'q yoki parslay olmadi: taxminga o'tamiz
        bits = len(data) * 8
        return bits / _MP3_ESTIMATE_BITRATE_BPS


def _speed_to_rate(speed: float) -> str:
    """1.0 → "+0%", 1.1 → "+10%", 0.9 → "-10%" (edge-tts/SSML prosody uslubi)."""
    pct = round((speed - 1.0) * 100)
    return f"{pct:+d}%"


def _escape_ssml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def words_to_subtitle_json(
    words: list[WordTiming], display_text: str | None = None
) -> list[dict[str, Any]]:
    """Timing'larni ko'rsatiladigan matn so'zlariga moslaydi (Remotion ``scenes[].words``).

    So'z soni bir xil bo'lsa — to'g'ridan-to'g'ri ``zip``. Farq qilsa (masalan tts_text'da
    "o'n besh foiz", display_text'da "15%") — umumiy davomiylik ichida belgi soniga proporsional
    qayta taqsimlanadi.
    """
    if not words:
        return []
    if display_text is None:
        return [{"w": w.word, "start": w.start_s, "end": w.end_s} for w in words]
    display_words = display_text.split()
    if not display_words:
        return []
    if len(display_words) == len(words):
        return [
            {"w": dw, "start": w.start_s, "end": w.end_s}
            for dw, w in zip(display_words, words)
        ]
    start, end = words[0].start_s, words[-1].end_s
    total = max(end - start, 0.0)
    weights = [max(len(dw), 1) for dw in display_words]
    wsum = sum(weights)
    out: list[dict[str, Any]] = []
    t = start
    for dw, wt in zip(display_words, weights):
        dur = total * wt / wsum if wsum else 0.0
        out.append({"w": dw, "start": t, "end": t + dur})
        t += dur
    out[-1]["end"] = end
    return out


# ---------- provayderlar ----------


class EdgeTTS:
    """Bepul, kalitsiz (norasmiy Azure ovozlari). So'z-timing beradi. docs/09-tts-research.md #5."""

    name = "edge"

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0
    ) -> TTSResult:
        import edge_tts

        voice = voice or settings.tts_voice
        communicate = edge_tts.Communicate(
            text, voice, rate=_speed_to_rate(speed), boundary="WordBoundary"
        )
        audio = bytearray()
        words: list[WordTiming] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                dur = chunk["duration"] / 10_000_000
                words.append(WordTiming(word=chunk["text"], start_s=start, end_s=start + dur))
        audio_bytes = bytes(audio)
        duration = words[-1].end_s if words else mp3_duration(audio_bytes)
        return TTSResult(
            audio=audio_bytes,
            format="mp3",
            sample_rate=24000,
            duration_s=duration,
            words=words,
            provider=self.name,
            voice=voice,
            usd=0.0,
            chars=len(text),
        )


class AzureTTS:
    """Rasmiy Azure Speech, so'z-timing beradi. ~$16/1M belgi. docs/09-tts-research.md #6."""

    name = "azure"
    _PRICE_USD_PER_CHAR = 16.0 / 1_000_000

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0
    ) -> TTSResult:
        import asyncio

        import azure.cognitiveservices.speech as speechsdk

        voice = voice or settings.tts_voice
        ssml = (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="uz-UZ">'
            f'<voice name="{voice}">'
            f'<prosody rate="{_speed_to_rate(speed)}">{_escape_ssml(text)}</prosody>'
            "</voice></speak>"
        )
        words: list[WordTiming] = []

        def _run() -> Any:
            speech_config = speechsdk.SpeechConfig(
                subscription=settings.azure_speech_key, region=settings.azure_speech_region
            )
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
            )
            speech_config.request_word_level_timestamps()
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

            def _on_boundary(evt: Any) -> None:
                if evt.boundary_type == speechsdk.SpeechSynthesisBoundaryType.Word:
                    start = evt.audio_offset / 10_000_000
                    dur = evt.duration.total_seconds() if evt.duration else 0.0
                    words.append(WordTiming(word=evt.text, start_s=start, end_s=start + dur))

            synthesizer.synthesis_word_boundary.connect(_on_boundary)
            return synthesizer.speak_ssml_async(ssml).get()

        result = await asyncio.to_thread(_run)
        audio = bytes(result.audio_data)
        duration = words[-1].end_s if words else wav_duration(audio)
        chars = len(text)
        return TTSResult(
            audio=audio,
            format="wav",
            sample_rate=24000,
            duration_s=duration,
            words=words,
            provider=self.name,
            voice=voice,
            usd=chars * self._PRICE_USD_PER_CHAR,
            chars=chars,
        )


class NavoiyTTS:
    """O'z serverimizda self-host (infra/tts/, HTTP /synthesize). docs/09-tts-research.md #1.

    Word-timing bermaydi — ``estimate_word_timings`` bilan taxmin qilinadi.
    """

    name = "navoiy"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport  # faqat testlar uchun (httpx.MockTransport)

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0
    ) -> TTSResult:
        voice = voice or settings.tts_voice
        async with httpx.AsyncClient(
            base_url=settings.navoiy_url, transport=self._transport, timeout=60.0
        ) as client:
            resp = await client.post(
                "/synthesize", json={"text": text, "voice": voice, "speed": speed}
            )
            resp.raise_for_status()
            audio = resp.content
        duration = wav_duration(audio)
        return TTSResult(
            audio=audio,
            format="wav",
            sample_rate=_wav_sample_rate(audio),
            duration_s=duration,
            words=estimate_word_timings(text, duration),
            provider=self.name,
            voice=voice,
            usd=0.0,
            chars=len(text),
        )


class AishaTTS:
    """Aisha AI API (uzbekvoice muallifi), eng tabiiy o'zbek urg'u. docs/09-tts-research.md #7.

    DIQQAT: endpoint shakli (path, so'rov/javob JSON'i) TAXMIN — aisha.group rasmiy
    hujjatlariga qarab tekshirilishi va kerak bo'lsa yangilanishi kerak
    (https://aisha.group/en/tts-uzbek , https://aisha.group/en/pricing).
    Word-timing bermaydi deb faraz qilingan — ``estimate_word_timings`` bilan taxmin qilinadi.
    """

    name = "aisha"
    _ENDPOINT = "/api/v1/tts"  # TAXMIN — aisha.group hujjatlari bilan tasdiqlanmagan

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport  # faqat testlar uchun (httpx.MockTransport)

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0
    ) -> TTSResult:
        voice = voice or settings.tts_voice
        headers = {"x-api-key": settings.aisha_api_key}
        async with httpx.AsyncClient(
            base_url=settings.aisha_url, transport=self._transport, timeout=60.0, headers=headers
        ) as client:
            resp = await client.post(
                self._ENDPOINT, json={"text": text, "voice": voice, "format": "mp3"}
            )
            resp.raise_for_status()
            audio = resp.content
        duration = mp3_duration(audio)
        return TTSResult(
            audio=audio,
            format="mp3",
            sample_rate=24000,
            duration_s=duration,
            words=estimate_word_timings(text, duration),
            provider=self.name,
            voice=voice,
            usd=0.0,  # TODO: UZS narx tasdiqlanganda hisoblansin (docs/09-tts-research.md)
            chars=len(text),
        )


class GoogleTTS:
    """Hali tanlanmagan (docs/09-tts-research.md — Azure/Navoiy/Aisha yetarli). Faqat ro'yxatdan o'tgan."""

    name = "google"

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0
    ) -> TTSResult:
        raise NotImplementedError("bosqich 1.2: keyinroq")


class ElevenLabsTTS:
    """Hali tanlanmagan. Faqat ro'yxatdan o'tgan."""

    name = "elevenlabs"

    async def synthesize(
        self, text: str, *, voice: str | None = None, speed: float = 1.0
    ) -> TTSResult:
        raise NotImplementedError("bosqich 1.2: keyinroq")


# ---------- registry / factory ----------

_PROVIDERS: dict[str, type[TTSProvider]] = {
    "edge": EdgeTTS,
    "azure": AzureTTS,
    "navoiy": NavoiyTTS,
    "aisha": AishaTTS,
    "google": GoogleTTS,
    "elevenlabs": ElevenLabsTTS,
}


def get_provider(name: str | None = None) -> TTSProvider:
    key = (name or settings.tts_provider).lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise ValueError(f"noma'lum TTS provayder: {key!r} (mavjud: {sorted(_PROVIDERS)})")
    return cls()


# ---------- top-level API ----------


async def synthesize(
    text: str,
    *,
    voice: str | None = None,
    speed: float = 1.0,
    workspace_id: str = "",
    node: str = "tts",
) -> TTSResult:
    """Matnni ovozga o'giradi: normalizatsiya → asosiy provayder → xato bo'lsa zaxira → xarajat yozuvi."""
    tts_text = to_tts_text(text)
    primary_name = settings.tts_provider
    fallback_name = settings.tts_fallback

    provider = get_provider(primary_name)
    try:
        result = await provider.synthesize(tts_text, voice=voice, speed=speed)
    except Exception:
        logger.warning(
            "tts: %r provayder xato berdi, %r ga o'tildi", primary_name, fallback_name,
            exc_info=True,
        )
        if not fallback_name or fallback_name == primary_name:
            raise
        fallback = get_provider(fallback_name)
        result = await fallback.synthesize(tts_text, voice=voice, speed=speed)

    log_media = getattr(cost_tracker, "log_media", None)
    if log_media is not None:
        await log_media(
            workspace_id,
            node,
            result.provider,
            result.usd,
            {"voice": result.voice, "chars": result.chars, "duration_s": result.duration_s},
        )
    return result


async def synthesize_to_file(text: str, path: str | Path, **kw: Any) -> TTSResult:
    result = await synthesize(text, **kw)
    Path(path).write_bytes(result.audio)
    return result
