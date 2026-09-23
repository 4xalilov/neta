"""STT adapter: bir nechta provayder bitta interfeys orqali (roadmap 5.10 "ovozli boshqaruv").

Ega Telegram'da gapiradi (OGG/Opus voice note) → ``transcribe(audio, fmt)`` → matn → Jarvis
niyat tahlili (``engine.jarvis.intents``). Tuzilishi ``engine.integrations.tts`` bilan bir xil:
``settings.stt_provider`` asosiy, xato bo'lsa ``settings.stt_fallback``; natija matni
``engine.uz.normalize.normalize_apostrophes`` orqali ichki standartga (oʻ/gʻ U+02BB) keltiriladi;
xarajat ``cost_tracker.log_media(kind="stt")``.

Provayderlar:
- ``gemini`` — ``engine.llm`` audio yo'li (``tier="draft"``, model Gemini bo'lishi SHART).
- ``whisper`` — lokal ``faster-whisper`` (CPU int8, ``language="uz"``), ixtiyoriy
  ``pip install -e ".[stt-local]"``.
- ``aisha`` — Aisha AI (uzbekvoice muallifi). ENDPOINT TAXMIN, tekshirilmagan.
- ``uzbekvoice`` — uzbekvoice.ai STT API (https://uzbekvoice.ai/en-US/developers/api/stt).
  URL/maydonlar hujjat sahifasiga qarab yozilgan, lekin haqiqiy kalit bilan TEKSHIRILMAGAN.
- ``azure`` — Azure Speech ``uz-UZ`` (``azure-cognitiveservices-speech``, lazy import).
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, ClassVar, Protocol

import httpx

from engine import cost_tracker, llm
from engine.integrations import audio as audio_mod
from engine.integrations.tts import WordTiming
from engine.settings import settings
from engine.uz.normalize import normalize_apostrophes

logger = logging.getLogger(__name__)

__all__ = [
    "UZBEKVOICE_STT_URL",
    "AishaSTT",
    "AzureSTT",
    "GeminiSTT",
    "STTError",
    "STTProvider",
    "STTResult",
    "UzbekvoiceSTT",
    "WhisperSTT",
    "WordTiming",
    "get_stt",
    "transcribe",
]

# PLACEHOLDER: Gemini audio kirishi aslida token bo'yicha narxlanadi (~32 token/s audio,
# gemini-2.5-flash audio input narxi alohida). Aniq narx tasdiqlanmaguncha soniyasiga
# $0.0001 deb hisoblaymiz (1 daqiqalik buyruq ≈ $0.006). TEKSHIRILMAGAN.
GEMINI_AUDIO_USD_PER_S = 0.0001
# Azure Speech STT standard: ~$1 / audio soati (2026 ommaviy narx, taxminiy).
AZURE_STT_USD_PER_S = 1.0 / 3600

# uzbekvoice.ai hujjatidagi STT endpoint (https://uzbekvoice.ai/en-US/developers/api/stt).
# TEKSHIRILMAGAN: haqiqiy kalit bilan sinab ko'rilmagan — URL/maydon nomlari o'zgargan bo'lishi
# mumkin. So'rov: multipart ``file`` + ``Authorization: <key>`` sarlavhasi; javob
# ``{"result": {"text": "..."}}``.
UZBEKVOICE_STT_URL = "https://uzbekvoice.ai/api/v1/stt"

GEMINI_STT_SYSTEM = (
    "You are a speech-to-text engine for Uzbek business owners (Tashkent). "
    "Transcribe the audio verbatim in Uzbek LATIN script (oʻ, gʻ with apostrophes), "
    "even if the speaker mixes in Russian words — write Russian loanwords in Latin "
    "(zakaz, skidka, klient). Keep numbers, times and amounts as digits (15:00, 3 ta, "
    "200 ming). Add normal punctuation. Do not translate, summarise or answer the speaker. "
    "Return ONLY the transcript text, nothing else. If there is no speech, return an empty string."
)
GEMINI_STT_USER = "Transcribe this voice message (Uzbek Latin, numbers as digits, punctuation)."


class STTError(RuntimeError):
    """STT provayder xatosi yoki mos kelmaydigan sozlama."""


@dataclass
class STTResult:
    text: str
    language: str = "uz"
    confidence: float | None = None  # 0–1; provayder bermasa None
    words: list[WordTiming] | None = None
    provider: str = ""
    usd: float = 0.0
    duration_s: float = 0.0
    # True — xarajat allaqachon boshqa joyda yozilgan (Gemini: ``llm.complete`` token logi),
    # ``transcribe`` ikkinchi marta ``log_media`` qilmasin.
    cost_logged: bool = field(default=False, repr=False)


class STTProvider(Protocol):
    name: str

    async def transcribe(self, audio: bytes, fmt: str, *, workspace_id: str = "") -> STTResult:
        ...


# ---------------------------------------------------------------- provayderlar


class GeminiSTT:
    """Gemini multimodal (audio → matn) ``engine.llm`` orqali, ``tier="draft"``.

    Xarajat: ``llm.complete`` token narxini o'zi yozadi (``node="stt.gemini"``). Token narxi
    0 bo'lsa (usage yo'q) — ``GEMINI_AUDIO_USD_PER_S`` placeholder bilan taxmin qilinadi.
    """

    name = "gemini"

    async def transcribe(self, audio: bytes, fmt: str, *, workspace_id: str = "") -> STTResult:
        model = settings.llm_draft_model
        if not model.startswith("gemini"):
            raise STTError(
                f"GeminiSTT: draft tier modeli Gemini bo'lishi kerak (hozir {model!r})"
            )
        fmt = audio_mod.normalize_format(fmt, audio)
        mime = audio_mod.MIME_BY_FORMAT.get(fmt, "audio/ogg")
        res = await llm.complete(
            "draft", GEMINI_STT_SYSTEM, GEMINI_STT_USER,
            audio=audio, audio_mime=mime, temperature=0.0, max_tokens=1024,
            node="stt.gemini", workspace_id=workspace_id,
        )
        text = res.text.strip().strip('"').strip("«»").strip()
        dur = audio_mod.duration_s(audio, fmt)
        usd = res.usd if res.usd > 0 else dur * GEMINI_AUDIO_USD_PER_S
        return STTResult(text=text, language="uz", confidence=None, words=None,
                         provider=self.name, usd=usd, duration_s=dur,
                         cost_logged=res.usd > 0)


class WhisperSTT:
    """Lokal faster-whisper (CPU, int8). Model bir marta yuklanadi (klass darajasida kesh)."""

    name = "whisper"
    _models: ClassVar[dict[str, Any]] = {}

    def _model(self) -> Any:
        key = settings.whisper_model
        if key not in self._models:
            try:
                from faster_whisper import WhisperModel  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - ixtiyoriy guruh
                raise STTError(
                    "faster-whisper o'rnatilmagan: pip install -e '.[stt-local]'"
                ) from exc
            self._models[key] = WhisperModel(key, device="cpu", compute_type="int8")
        return self._models[key]

    async def transcribe(self, audio: bytes, fmt: str, *, workspace_id: str = "") -> STTResult:
        def _run() -> STTResult:
            model = self._model()
            segments, info = model.transcribe(
                BytesIO(audio), language="uz", word_timestamps=True, vad_filter=True,
                beam_size=5,
            )
            texts: list[str] = []
            words: list[WordTiming] = []
            logprobs: list[float] = []
            for seg in segments:
                texts.append(seg.text.strip())
                logprobs.append(float(getattr(seg, "avg_logprob", 0.0)))
                for w in getattr(seg, "words", None) or []:
                    words.append(WordTiming(word=w.word.strip(), start_s=w.start, end_s=w.end))
            confidence = (
                math.exp(sum(logprobs) / len(logprobs)) if logprobs else None
            )
            return STTResult(
                text=" ".join(t for t in texts if t), language="uz",
                confidence=round(confidence, 3) if confidence is not None else None,
                words=words or None, provider=self.name, usd=0.0,
                duration_s=float(getattr(info, "duration", 0.0) or 0.0),
            )

        return await asyncio.to_thread(_run)


def _text_from_json(data: Any) -> str:
    """``{"text"}`` / ``{"result": {"text"}}`` / ``{"result": "..."}`` — qaysi biri kelsa."""
    if isinstance(data, dict):
        if isinstance(data.get("text"), str):
            return data["text"]
        result = data.get("result")
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and isinstance(result.get("text"), str):
            return result["text"]
    raise STTError(f"STT javobida matn topilmadi: {str(data)[:200]}")


class AishaSTT:
    """Aisha AI STT. DIQQAT: ``{aisha_url}/api/v1/stt`` — TAXMIN (TTS adapteridagi kabi),
    aisha.group hujjatlari bilan tasdiqlanmagan. So'rov: multipart ``audio`` + ``x-api-key``."""

    name = "aisha"
    _ENDPOINT = "/api/v1/stt"  # TAXMIN — tekshirilmagan

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def transcribe(self, audio: bytes, fmt: str, *, workspace_id: str = "") -> STTResult:
        fmt = audio_mod.normalize_format(fmt, audio)
        mime = audio_mod.MIME_BY_FORMAT.get(fmt, "application/octet-stream")
        async with httpx.AsyncClient(
            base_url=settings.aisha_url, transport=self._transport, timeout=60.0,
            headers={"x-api-key": settings.aisha_api_key},
        ) as client:
            resp = await client.post(
                self._ENDPOINT, files={"audio": (f"voice.{fmt}", audio, mime)},
                data={"language": "uz"},
            )
            resp.raise_for_status()
            text = _text_from_json(resp.json())
        return STTResult(text=text, provider=self.name,
                         duration_s=audio_mod.duration_s(audio, fmt),
                         usd=0.0)  # TODO: UZS narx tasdiqlanganda


class UzbekvoiceSTT:
    """uzbekvoice.ai STT API (``UZBEKVOICE_STT_URL``). TEKSHIRILMAGAN — hujjatga qarab yozilgan."""

    name = "uzbekvoice"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def transcribe(self, audio: bytes, fmt: str, *, workspace_id: str = "") -> STTResult:
        if not settings.uzbekvoice_api_key:
            raise STTError("UZBEKVOICE_API_KEY sozlanmagan")
        fmt = audio_mod.normalize_format(fmt, audio)
        mime = audio_mod.MIME_BY_FORMAT.get(fmt, "application/octet-stream")
        async with httpx.AsyncClient(transport=self._transport, timeout=90.0) as client:
            resp = await client.post(
                UZBEKVOICE_STT_URL,
                headers={"Authorization": settings.uzbekvoice_api_key},
                files={"file": (f"voice.{fmt}", audio, mime)},
                data={"return_offsets": "false", "run_diarization": "false",
                      "language": "uz", "blocking": "true"},
            )
            resp.raise_for_status()
            text = _text_from_json(resp.json())
        return STTResult(text=text, provider=self.name,
                         duration_s=audio_mod.duration_s(audio, fmt),
                         usd=0.0)  # TODO: narx (UZS) tasdiqlanganda


class AzureSTT:
    """Azure Speech ``uz-UZ`` (bitta qisqa buyruq — ``recognize_once``). WAV PCM kerak →
    OGG bo'lsa ``audio.ogg_to_wav`` (ffmpeg)."""

    name = "azure"

    async def transcribe(self, audio: bytes, fmt: str, *, workspace_id: str = "") -> STTResult:
        import azure.cognitiveservices.speech as speechsdk

        wav = await audio_mod.ogg_to_wav(audio)
        dur = audio_mod.duration_s(wav, "wav")

        def _run() -> Any:
            speech_config = speechsdk.SpeechConfig(
                subscription=settings.azure_speech_key, region=settings.azure_speech_region
            )
            speech_config.speech_recognition_language = "uz-UZ"
            stream = speechsdk.audio.PushAudioInputStream()
            stream.write(wav[44:])  # RIFF sarlavhasiz PCM (16 kHz mono 16-bit)
            stream.close()
            audio_config = speechsdk.audio.AudioConfig(stream=stream)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config, audio_config=audio_config
            )
            return recognizer.recognize_once_async().get()

        result = await asyncio.to_thread(_run)
        if result.reason != speechsdk.ResultReason.RecognizedSpeech:
            raise STTError(f"Azure STT: {result.reason}")
        return STTResult(text=result.text, provider=self.name, duration_s=dur,
                         usd=dur * AZURE_STT_USD_PER_S)


# ---------------------------------------------------------------- registry / factory

_PROVIDERS: dict[str, type] = {
    "gemini": GeminiSTT,
    "whisper": WhisperSTT,
    "aisha": AishaSTT,
    "uzbekvoice": UzbekvoiceSTT,
    "azure": AzureSTT,
}


def get_stt(name: str | None = None) -> STTProvider:
    key = (name or settings.stt_provider).lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        raise ValueError(f"noma'lum STT provayder: {key!r} (mavjud: {sorted(_PROVIDERS)})")
    return cls()


# ---------------------------------------------------------------- top-level API


async def transcribe(audio: bytes, fmt: str | None = None, *, workspace_id: str = "",
                     provider: str | None = None) -> STTResult:
    """Ovoz → matn: asosiy provayder → xato bo'lsa zaxira → apostrof normalizatsiyasi → xarajat."""
    if not audio:
        raise STTError("bo'sh audio")
    fmt = audio_mod.normalize_format(fmt, audio)
    primary_name = provider or settings.stt_provider
    fallback_name = settings.stt_fallback

    try:
        result = await get_stt(primary_name).transcribe(audio, fmt, workspace_id=workspace_id)
    except Exception:
        logger.warning("stt: %r provayder xato berdi, %r ga o'tildi", primary_name,
                       fallback_name, exc_info=True)
        if not fallback_name or fallback_name == primary_name:
            raise
        result = await get_stt(fallback_name).transcribe(audio, fmt, workspace_id=workspace_id)

    result.text = normalize_apostrophes(result.text.strip())
    if not result.duration_s:
        result.duration_s = audio_mod.duration_s(audio, fmt)

    if not result.cost_logged:
        await cost_tracker.log_media(
            workspace_id, "stt", result.provider, result.usd,
            {"duration_s": result.duration_s, "chars": len(result.text), "format": fmt},
            kind="stt",
        )
        result.cost_logged = True
    return result
