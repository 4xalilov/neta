"""Audio yordamchilari: format aniqlash, davomiylik, ffmpeg orqali konvertatsiya (roadmap 5.10).

- Telegram voice note — OGG/Opus. STT provayderlarining bir qismi (Azure, ba'zi HTTP API'lar)
  WAV/PCM kutadi → ``ogg_to_wav``.
- Jarvis javobi TTS'dan mp3/wav keladi, Telegram ``sendVoice`` esa OGG/Opus talab qiladi →
  ``mp3_to_ogg_opus`` (wav kirishni ham qabul qiladi — ffmpeg formatni o'zi aniqlaydi).

ffmpeg ``asyncio.create_subprocess_exec`` bilan stdin/stdout quvuri orqali ishlaydi (vaqtinchalik
fayl yo'q). Binar ``settings.ffmpeg_bin`` (default ``"ffmpeg"``; api Dockerfile o'rnatadi);
topilmasa ``AudioToolMissing`` — chaqiruvchi (``jarvis.voice``) buni jim o'tkazib, faqat matn
qaytaradi. Testlar ``_ffmpeg_path`` va ``asyncio.create_subprocess_exec`` ni almashtiradi.

``duration_s`` sof Python (ffmpeg shart emas): WAV — ``wave``; OGG — oxirgi sahifaning granule
pozitsiyasi (Opus doim 48 kHz, Vorbis — identifikatsiya sarlavhasidagi sample rate); MP3 —
``tts.mp3_duration`` (mutagen bo'lsa aniq, aks holda bitrate taxmini).
"""
from __future__ import annotations

import asyncio
import shutil
import struct
import wave
from io import BytesIO

from engine.settings import settings

FFMPEG_TIMEOUT_S = 60.0
STT_SAMPLE_RATE = 16_000  # STT uchun yetarli (Whisper/Azure 16 kHz mono kutadi)
OPUS_BITRATE = "32k"  # voice note uchun yetarli, Telegram o'zi ham ~32k ishlatadi


class AudioError(RuntimeError):
    """Audio konvertatsiya xatosi (ffmpeg nol bo'lmagan kod bilan chiqdi va h.k.)."""


class AudioToolMissing(AudioError):
    """ffmpeg topilmadi (``settings.ffmpeg_bin``)."""


# ---------------------------------------------------------------- format aniqlash


def is_ogg(data: bytes) -> bool:
    return data[:4] == b"OggS"


def is_wav(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def is_mp3(data: bytes) -> bool:
    if data[:3] == b"ID3":
        return True
    # MPEG audio frame sync: 11 bit 1 (0xFFE)
    return len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0


def sniff_format(data: bytes) -> str | None:
    """``"ogg" | "wav" | "mp3"`` yoki ``None`` (noma'lum)."""
    if is_ogg(data):
        return "ogg"
    if is_wav(data):
        return "wav"
    if is_mp3(data):
        return "mp3"
    return None


_FMT_ALIASES = {"oga": "ogg", "opus": "ogg", "ogg": "ogg", "wav": "wav", "wave": "wav",
                "mp3": "mp3", "mpeg": "mp3", "m4a": "m4a", "mp4": "m4a", "webm": "webm",
                "flac": "flac"}

MIME_BY_FORMAT = {"ogg": "audio/ogg", "wav": "audio/wav", "mp3": "audio/mp3",
                  "m4a": "audio/aac", "webm": "audio/webm", "flac": "audio/flac"}


def normalize_format(fmt: str | None, data: bytes = b"") -> str:
    """Fayl kengaytmasi/MIME/bo'sh qiymatdan ichki format nomi. Baytlar aniq format ko'rsatsa —
    o'sha ustun (Telegram ``.oga`` yuboradi, bot ``fmt`` bermasligi mumkin)."""
    sniffed = sniff_format(data) if data else None
    if sniffed:
        return sniffed
    key = (fmt or "").lower().strip().lstrip(".")
    key = key.split("/")[-1].split(";")[0]  # "audio/ogg; codecs=opus" -> "ogg"
    return _FMT_ALIASES.get(key, key or "ogg")


# ---------------------------------------------------------------- davomiylik


def _ogg_pages(data: bytes):
    """OGG sahifalari: ``(granule_position, header_type, payload)``."""
    pos = 0
    n = len(data)
    while pos + 27 <= n and data[pos:pos + 4] == b"OggS":
        header_type = data[pos + 5]
        granule = struct.unpack_from("<q", data, pos + 6)[0]
        segments = data[pos + 26]
        table_end = pos + 27 + segments
        if table_end > n:
            break
        body_len = sum(data[pos + 27:table_end])
        payload = data[table_end:table_end + body_len]
        yield granule, header_type, payload
        pos = table_end + body_len


def _ogg_duration(data: bytes) -> float:
    sample_rate = 48_000  # Opus granule doim 48 kHz
    pre_skip = 0
    last_granule = 0
    first = True
    for granule, _htype, payload in _ogg_pages(data):
        if first:
            first = False
            if payload.startswith(b"OpusHead") and len(payload) >= 12:
                pre_skip = struct.unpack_from("<H", payload, 10)[0]
            elif payload[:7] == b"\x01vorbis" and len(payload) >= 16:
                sample_rate = struct.unpack_from("<I", payload, 12)[0] or 44_100
        if granule > 0:
            last_granule = granule
    if last_granule <= 0:
        return 0.0
    return max(last_granule - pre_skip, 0) / float(sample_rate)


def _wav_duration(data: bytes) -> float:
    with wave.open(BytesIO(data), "rb") as f:
        rate = f.getframerate()
        return f.getnframes() / float(rate) if rate else 0.0


def duration_s(data: bytes, fmt: str | None = None) -> float:
    """Audio davomiyligi (s). Aniqlab bo'lmasa ``0.0`` (xato ko'tarmaydi)."""
    fmt = normalize_format(fmt, data)
    try:
        if fmt == "wav":
            return _wav_duration(data)
        if fmt == "ogg":
            return _ogg_duration(data)
        if fmt == "mp3":
            from engine.integrations.tts import mp3_duration

            return mp3_duration(data)
    except Exception:  # noqa: BLE001 — buzilgan fayl: davomiylik faqat xarajat/log uchun
        return 0.0
    return 0.0


# ---------------------------------------------------------------- ffmpeg


def _ffmpeg_path() -> str | None:
    return shutil.which(settings.ffmpeg_bin)


async def _run_ffmpeg(data: bytes, out_args: list[str]) -> bytes:
    """``ffmpeg -i pipe:0 <out_args> pipe:1`` — stdin'dan o'qib stdout'ga yozadi."""
    binary = _ffmpeg_path()
    if not binary:
        raise AudioToolMissing(f"ffmpeg topilmadi: {settings.ffmpeg_bin!r}")
    cmd = [binary, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", "pipe:0",
           *out_args, "pipe:1"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise AudioToolMissing(f"ffmpeg ishga tushmadi: {exc}") from exc
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(data), FFMPEG_TIMEOUT_S)
    except TimeoutError as exc:
        proc.kill()
        raise AudioError(f"ffmpeg {FFMPEG_TIMEOUT_S:.0f}s ichida tugamadi") from exc
    if proc.returncode != 0 or not stdout:
        msg = (stderr or b"").decode("utf-8", "replace").strip()[:300]
        raise AudioError(f"ffmpeg xato (kod {proc.returncode}): {msg}")
    return stdout


async def ogg_to_wav(data: bytes, *, sample_rate: int = STT_SAMPLE_RATE) -> bytes:
    """OGG/Opus (yoki ffmpeg taniydigan boshqa format) → 16-bit PCM mono WAV. WAV bo'lsa o'zi."""
    if is_wav(data):
        return data
    return await _run_ffmpeg(
        data, ["-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", "-f", "wav"]
    )


async def mp3_to_ogg_opus(data: bytes) -> bytes:
    """mp3/wav → OGG/Opus mono 48 kHz (Telegram ``sendVoice``). OGG bo'lsa o'zi qaytadi."""
    if is_ogg(data):
        return data
    return await _run_ffmpeg(
        data,
        ["-vn", "-ac", "1", "-ar", "48000", "-c:a", "libopus", "-b:a", OPUS_BITRATE,
         "-application", "voip", "-f", "ogg"],
    )


to_ogg_opus = mp3_to_ogg_opus  # nom aniqroq bo'lishi uchun (wav kirish ham ishlaydi)
