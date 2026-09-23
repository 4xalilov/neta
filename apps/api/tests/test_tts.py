"""engine.integrations.tts testlari. Tarmoq yo'q — hamma provayder mock bilan."""
import json
import wave
from io import BytesIO
from itertools import pairwise

import httpx
import pytest

from engine import cost_tracker
from engine.integrations import tts
from engine.settings import settings


def _make_wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


# ---------- EdgeTTS ----------


class _FakeCommunicate:
    """edge_tts.Communicate o'rnini bosadi: audio + WordBoundary chunk'lar beradi."""

    def __init__(self, text, voice, *, rate="+0%", boundary="WordBoundary", **kw):
        self.text = text
        self.voice = voice
        self.boundary = boundary

    async def stream(self):
        yield {"type": "audio", "data": b"\x00\x01\x02\x03"}
        # offset/duration 100ns (10_000_000 = 1s) birligida keladi
        yield {"type": "WordBoundary", "offset": 0, "duration": 5_000_000, "text": "Salom"}
        yield {"type": "audio", "data": b"\x04\x05"}
        yield {"type": "WordBoundary", "offset": 5_000_000, "duration": 3_000_000, "text": "dunyo"}


async def test_edge_tts_word_timings(monkeypatch):
    import edge_tts

    monkeypatch.setattr(edge_tts, "Communicate", _FakeCommunicate)
    provider = tts.EdgeTTS()
    result = await provider.synthesize("Salom dunyo", voice="uz-UZ-MadinaNeural")

    assert result.provider == "edge"
    assert result.format == "mp3"
    assert result.audio == b"\x00\x01\x02\x03\x04\x05"
    assert len(result.words) == 2
    assert result.words[0] == tts.WordTiming(word="Salom", start_s=0.0, end_s=0.5)
    assert result.words[1] == tts.WordTiming(word="dunyo", start_s=0.5, end_s=0.8)
    assert result.duration_s == pytest.approx(0.8)
    assert result.usd == 0.0
    assert result.chars == len("Salom dunyo")


# ---------- fallback ----------


class _FailingProvider:
    name = "primary_fake"

    async def synthesize(self, text, *, voice=None, speed=1.0):
        raise RuntimeError("primary_fake tarmoq xatosi")


class _OkProvider:
    name = "fallback_fake"

    async def synthesize(self, text, *, voice=None, speed=1.0):
        return tts.TTSResult(
            audio=b"ok",
            format="wav",
            sample_rate=16000,
            duration_s=1.0,
            words=[],
            provider=self.name,
            voice=voice or "v",
            usd=0.01,
            chars=len(text),
        )


async def test_synthesize_falls_back_on_primary_error(monkeypatch):
    monkeypatch.setattr(
        tts, "_PROVIDERS", {"primary_fake": _FailingProvider, "fallback_fake": _OkProvider}
    )
    monkeypatch.setattr(settings, "tts_provider", "primary_fake")
    monkeypatch.setattr(settings, "tts_fallback", "fallback_fake")

    before = len(cost_tracker.RECENT)
    result = await tts.synthesize("salom dunyo", workspace_id="ws1", node="tts")

    assert result.provider == "fallback_fake"
    assert len(cost_tracker.RECENT) == before + 1
    entry = cost_tracker.RECENT[-1]
    assert entry["workspace_id"] == "ws1"
    assert entry["provider"] == "fallback_fake"
    assert entry["kind"] == "media"


async def test_synthesize_reraises_when_no_fallback(monkeypatch):
    monkeypatch.setattr(tts, "_PROVIDERS", {"primary_fake": _FailingProvider})
    monkeypatch.setattr(settings, "tts_provider", "primary_fake")
    monkeypatch.setattr(settings, "tts_fallback", "primary_fake")

    with pytest.raises(RuntimeError):
        await tts.synthesize("salom")


# ---------- estimate_word_timings ----------


def test_estimate_word_timings_sums_and_monotonic():
    words = tts.estimate_word_timings("Salom dunyo, bugun kun issiq.", 3.0)
    assert words
    assert words[0].start_s == 0.0
    assert words[-1].end_s == pytest.approx(3.0)
    prev_end = 0.0
    for w in words:
        assert w.start_s >= prev_end - 1e-9
        assert w.end_s >= w.start_s
        prev_end = w.end_s


def test_estimate_word_timings_empty():
    assert tts.estimate_word_timings("", 3.0) == []
    assert tts.estimate_word_timings("salom", 0.0) == []


# ---------- words_to_subtitle_json ----------


def test_words_to_subtitle_json_same_count():
    words = [tts.WordTiming("Salom", 0.0, 0.5), tts.WordTiming("dunyo", 0.5, 1.0)]
    out = tts.words_to_subtitle_json(words, "Salom dunyo")
    assert out == [
        {"w": "Salom", "start": 0.0, "end": 0.5},
        {"w": "dunyo", "start": 0.5, "end": 1.0},
    ]


def test_words_to_subtitle_json_remap_different_count():
    # tts_text: "o'n besh foiz" (3 so'z) -> display_text: "15% chegirma bor" (3 so'z, lekin
    # boshqa so'zlanish) — soni farq qiladigan real holatni simulyatsiya qilamiz.
    words = [
        tts.WordTiming("bu", 0.0, 0.2),
        tts.WordTiming("yerda", 0.2, 0.5),
        tts.WordTiming("chegirma", 0.5, 1.0),
    ]
    out = tts.words_to_subtitle_json(words, "chegirma bor")
    assert len(out) == 2
    assert out[0]["start"] == 0.0
    assert out[-1]["end"] == pytest.approx(1.0)
    for a, b in pairwise(out):
        assert b["start"] >= a["start"]


def test_words_to_subtitle_json_no_display_text():
    words = [tts.WordTiming("Salom", 0.0, 0.5)]
    assert tts.words_to_subtitle_json(words, None) == [{"w": "Salom", "start": 0.0, "end": 0.5}]


def test_words_to_subtitle_json_empty():
    assert tts.words_to_subtitle_json([], "salom") == []


# ---------- NavoiyTTS (httpx.MockTransport) ----------


async def test_navoiy_tts_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/synthesize"
        payload = json.loads(request.content)
        assert payload["text"] == "Salom dunyo"
        assert payload["voice"]
        return httpx.Response(200, content=_make_wav(seconds=1.0, rate=16000))

    provider = tts.NavoiyTTS(transport=httpx.MockTransport(handler))
    result = await provider.synthesize("Salom dunyo")

    assert result.provider == "navoiy"
    assert result.format == "wav"
    assert result.sample_rate == 16000
    assert result.duration_s == pytest.approx(1.0)
    assert result.words  # estimate_word_timings orqali to'ldirilgan
    assert result.words[-1].end_s == pytest.approx(1.0)
    assert result.usd == 0.0


async def test_aisha_tts_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == tts.AishaTTS._ENDPOINT
        assert request.headers["x-api-key"] == settings.aisha_api_key
        payload = json.loads(request.content)
        assert payload["format"] == "mp3"
        return httpx.Response(200, content=b"\x00" * 6000)

    provider = tts.AishaTTS(transport=httpx.MockTransport(handler))
    result = await provider.synthesize("Salom dunyo")

    assert result.provider == "aisha"
    assert result.format == "mp3"
    assert result.words


# ---------- registry ----------


def test_registry_names():
    for name in ["edge", "azure", "navoiy", "aisha", "google", "elevenlabs"]:
        provider = tts.get_provider(name)
        assert provider.name == name


def test_registry_unknown_raises():
    with pytest.raises(ValueError):
        tts.get_provider("noma-mavjud")


async def test_google_stub_raises():
    with pytest.raises(NotImplementedError):
        await tts.get_provider("google").synthesize("salom")


async def test_elevenlabs_stub_raises():
    with pytest.raises(NotImplementedError):
        await tts.get_provider("elevenlabs").synthesize("salom")
