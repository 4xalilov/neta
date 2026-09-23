"""``engine.integrations.{audio,stt}`` + ``llm`` audio yo'li + ``evals/stt_bench`` (tarmoqsiz)."""
from __future__ import annotations

import asyncio
import io
import json
import struct
import sys
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import httpx
import pytest

from engine import cost_tracker, llm
from engine.integrations import audio as audio_mod
from engine.integrations import stt
from engine.settings import settings

REPO = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------- namunaviy audio


def make_wav(seconds: float = 1.0, rate: int = 16_000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def _ogg_page(payload: bytes, granule: int, seq: int, header_type: int = 0) -> bytes:
    segs = []
    rest = len(payload)
    while rest >= 255:
        segs.append(255)
        rest -= 255
    segs.append(rest)
    header = b"OggS" + bytes([0, header_type]) + struct.pack("<qIII", granule, 1, seq, 0)
    return header + bytes([len(segs)]) + bytes(segs) + payload


def make_ogg_opus(seconds: float = 2.0, pre_skip: int = 312) -> bytes:
    head = b"OpusHead" + bytes([1, 1]) + struct.pack("<HIhB", pre_skip, 48_000, 0, 0)
    tags = b"OpusTags" + struct.pack("<I", 0) + struct.pack("<I", 0)
    return (_ogg_page(head, 0, 0, header_type=2) + _ogg_page(tags, 0, 1)
            + _ogg_page(b"\x00" * 300, 48_000, 2)
            + _ogg_page(b"\x00" * 300, int(seconds * 48_000) + pre_skip, 3, header_type=4))


# ---------------------------------------------------------------- audio: sniff/duration


def test_sniff_and_normalize_format():
    wav, ogg = make_wav(), make_ogg_opus()
    assert audio_mod.is_wav(wav) and not audio_mod.is_ogg(wav)
    assert audio_mod.is_ogg(ogg) and audio_mod.sniff_format(ogg) == "ogg"
    assert audio_mod.is_mp3(b"ID3\x04rest") and audio_mod.is_mp3(b"\xff\xfb\x90\x00")
    assert audio_mod.sniff_format(b"hello") is None
    assert audio_mod.normalize_format("oga") == "ogg"
    assert audio_mod.normalize_format("audio/ogg; codecs=opus") == "ogg"
    assert audio_mod.normalize_format(".MP3") == "mp3"
    assert audio_mod.normalize_format(None) == "ogg"
    assert audio_mod.normalize_format("mp3", wav) == "wav"  # baytlar ustun


def test_duration():
    assert audio_mod.duration_s(make_wav(1.5), "wav") == pytest.approx(1.5)
    assert audio_mod.duration_s(make_ogg_opus(2.0), "ogg") == pytest.approx(2.0)
    assert audio_mod.duration_s(make_ogg_opus(3.0), None) == pytest.approx(3.0)
    assert audio_mod.duration_s(b"garbage", "wav") == 0.0
    assert audio_mod.duration_s(b"\x00" * 6000, "mp3") > 0  # bitrate taxmini


# ---------------------------------------------------------------- audio: ffmpeg (mock)


class _FakeProc:
    def __init__(self, out: bytes, code: int = 0, err: bytes = b"") -> None:
        self._out, self._err, self.returncode = out, err, code
        self.stdin_data: bytes | None = None

    async def communicate(self, data: bytes):
        self.stdin_data = data
        return self._out, self._err

    def kill(self) -> None:  # pragma: no cover
        pass


@pytest.fixture
def ffmpeg(monkeypatch):
    calls: list[dict] = []
    state = {"out": b"OggS-converted", "code": 0}
    monkeypatch.setattr(audio_mod, "_ffmpeg_path", lambda: "/usr/bin/ffmpeg")

    async def fake_exec(*cmd, **kw):
        proc = _FakeProc(state["out"], state["code"], b"boom")
        calls.append({"cmd": list(cmd), "kw": kw, "proc": proc})
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return SimpleNamespace(calls=calls, state=state)


async def test_mp3_to_ogg_opus_runs_ffmpeg(ffmpeg):
    out = await audio_mod.mp3_to_ogg_opus(b"ID3mp3data")
    assert out == b"OggS-converted"
    cmd = ffmpeg.calls[0]["cmd"]
    assert cmd[0] == "/usr/bin/ffmpeg" and "libopus" in cmd and cmd[-1] == "pipe:1"
    assert ffmpeg.calls[0]["proc"].stdin_data == b"ID3mp3data"
    # OGG kirish — konvertatsiyasiz
    assert await audio_mod.mp3_to_ogg_opus(b"OggSxx") == b"OggSxx"
    assert len(ffmpeg.calls) == 1


async def test_ogg_to_wav_and_errors(ffmpeg):
    ffmpeg.state["out"] = make_wav(0.5)
    wav = await audio_mod.ogg_to_wav(make_ogg_opus())
    assert audio_mod.is_wav(wav)
    assert "pcm_s16le" in ffmpeg.calls[0]["cmd"] and "16000" in ffmpeg.calls[0]["cmd"]
    same = make_wav()
    assert await audio_mod.ogg_to_wav(same) is same

    ffmpeg.state["code"] = 1
    with pytest.raises(audio_mod.AudioError, match="boom"):
        await audio_mod.ogg_to_wav(make_ogg_opus())


async def test_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(audio_mod, "_ffmpeg_path", lambda: None)
    with pytest.raises(audio_mod.AudioToolMissing):
        await audio_mod.mp3_to_ogg_opus(b"ID3x")

    async def not_found(*a, **kw):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(audio_mod, "_ffmpeg_path", lambda: "/nope/ffmpeg")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", not_found)
    with pytest.raises(audio_mod.AudioToolMissing):
        await audio_mod.ogg_to_wav(b"OggS")


# ---------------------------------------------------------------- stt.transcribe


class FakeSTT:
    name = "fake"
    text = "Azizga ayt, zakazni ertaga 3 gacha yopsin, o'sha ma'lumot bilan"
    calls: ClassVar[list] = []

    async def transcribe(self, audio, fmt, *, workspace_id=""):
        FakeSTT.calls.append((audio, fmt, workspace_id))
        return stt.STTResult(text=f"  {self.text}  ", provider=self.name, usd=0.002,
                             confidence=0.9)


class BrokenSTT:
    name = "broken"

    async def transcribe(self, audio, fmt, *, workspace_id=""):
        raise RuntimeError("provayder o'chiq")


@pytest.fixture
def stt_fakes(monkeypatch):
    monkeypatch.setitem(stt._PROVIDERS, "fake", FakeSTT)
    monkeypatch.setitem(stt._PROVIDERS, "broken", BrokenSTT)
    monkeypatch.setattr(settings, "stt_provider", "fake")
    monkeypatch.setattr(settings, "stt_fallback", "fake")
    FakeSTT.calls = []
    cost_tracker.RECENT.clear()
    yield
    cost_tracker.RECENT.clear()


async def test_transcribe_normalizes_and_logs_cost(stt_fakes):
    ogg = make_ogg_opus(2.0)
    res = await stt.transcribe(ogg, "oga", workspace_id="ws-1")
    assert res.text.startswith("Azizga ayt")
    assert "oʻsha" in res.text and "maʼlumot" in res.text  # normalize_apostrophes
    assert res.duration_s == pytest.approx(2.0)  # provayder bermadi → audio'dan
    assert FakeSTT.calls[0][1] == "ogg" and FakeSTT.calls[0][2] == "ws-1"
    entry = next(e for e in cost_tracker.RECENT if e["kind"] == "stt")
    assert entry["provider"] == "fake" and entry["usd"] == 0.002
    assert entry["workspace_id"] == "ws-1" and entry["meta"]["duration_s"] == pytest.approx(2.0)


async def test_transcribe_fallback(stt_fakes, monkeypatch):
    monkeypatch.setattr(settings, "stt_provider", "broken")
    res = await stt.transcribe(make_wav(), "wav")
    assert res.provider == "fake"

    monkeypatch.setattr(settings, "stt_fallback", "broken")
    with pytest.raises(RuntimeError, match="o'chiq"):
        await stt.transcribe(make_wav(), "wav")
    with pytest.raises(stt.STTError):
        await stt.transcribe(b"", "wav")
    with pytest.raises(ValueError):
        stt.get_stt("nope")


async def test_gemini_stt_uses_llm_audio_path(stt_fakes, monkeypatch):
    seen = []

    def fake(tier, system, user):
        seen.append((tier, system))
        return "Dilnozaga eslat, otchyot kerak."

    llm.set_fake(fake)
    try:
        monkeypatch.setattr(settings, "llm_draft_model", "gemini-2.5-flash")
        res = await stt.transcribe(make_ogg_opus(), "ogg", workspace_id="ws", provider="gemini")
    finally:
        llm.clear_fake()
    assert res.text == "Dilnozaga eslat, otchyot kerak." and res.provider == "gemini"
    assert seen[0][0] == "draft" and "Uzbek LATIN" in seen[0][1]
    # llm token logi bor → stt log_media ikkinchi marta yozilmaydi
    assert [e["node"] for e in cost_tracker.RECENT] == ["stt.gemini"]
    assert res.usd > 0


async def test_gemini_stt_requires_gemini_model(monkeypatch):
    monkeypatch.setattr(settings, "llm_draft_model", "claude-sonnet-5")
    with pytest.raises(stt.STTError, match="Gemini"):
        await stt.GeminiSTT().transcribe(make_ogg_opus(), "ogg")
    with pytest.raises(llm.LLMError, match="audio"):
        await llm.complete("draft", "s", "u", audio=b"OggS")


async def test_llm_gemini_audio_part(monkeypatch):
    captured = {}

    class _Models:
        async def generate_content(self, *, model, contents, config):
            captured.update(model=model, contents=contents, config=config)
            return SimpleNamespace(text="salom dunyo", usage_metadata=None)

    client = SimpleNamespace(aio=SimpleNamespace(models=_Models()))
    monkeypatch.setattr(llm, "_gemini_client", lambda: client)
    monkeypatch.setattr(settings, "llm_draft_model", "gemini-2.5-flash")
    llm.clear_fake()
    res = await llm.complete("draft", "sys", "transcribe", audio=b"OggSdata",
                             audio_mime="audio/ogg", node="stt.gemini")
    assert res.text == "salom dunyo"
    part = captured["contents"][0]
    assert part.inline_data.mime_type == "audio/ogg" and part.inline_data.data == b"OggSdata"
    assert captured["contents"][-1] == "transcribe"


async def test_uzbekvoice_stt_multipart(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.content
        return httpx.Response(200, json={"result": {"text": "Salom, ertaga uchrashamiz"}})

    monkeypatch.setattr(settings, "uzbekvoice_api_key", "KEY123")
    provider = stt.UzbekvoiceSTT(transport=httpx.MockTransport(handler))
    res = await provider.transcribe(make_ogg_opus(), "ogg")
    assert res.text == "Salom, ertaga uchrashamiz" and res.provider == "uzbekvoice"
    assert seen["url"] == stt.UZBEKVOICE_STT_URL and seen["auth"] == "KEY123"
    assert b'name="file"' in seen["body"] and b"audio/ogg" in seen["body"]

    monkeypatch.setattr(settings, "uzbekvoice_api_key", "")
    with pytest.raises(stt.STTError):
        await provider.transcribe(make_ogg_opus(), "ogg")


async def test_aisha_stt_guess_endpoint(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/stt"
        assert request.headers["x-api-key"] == "AK"
        return httpx.Response(200, json={"text": "hisobotni yubor"})

    monkeypatch.setattr(settings, "aisha_api_key", "AK")
    res = await stt.AishaSTT(transport=httpx.MockTransport(handler)).transcribe(make_wav(), "wav")
    assert res.text == "hisobotni yubor" and res.duration_s == pytest.approx(1.0)

    def bad(request):
        return httpx.Response(200, json={"foo": 1})

    with pytest.raises(stt.STTError):
        await stt.AishaSTT(transport=httpx.MockTransport(bad)).transcribe(make_wav(), "wav")


# ---------------------------------------------------------------- evals/stt_bench


@pytest.fixture
def bench(monkeypatch):
    monkeypatch.syspath_prepend(str(REPO))
    sys.modules.pop("evals.stt_bench", None)
    import evals.stt_bench as mod

    return mod


def test_stt_test_md_has_50_commands(bench):
    cmds = bench.load_commands()
    assert [c.n for c in cmds] == list(range(1, 51))
    from engine.jarvis.intents import INTENTS

    assert {c.intent for c in cmds} <= set(INTENTS)
    assert len({c.intent for c in cmds}) >= 12
    first = cmds[0]
    assert first.intent == "assign_task" and first.entities["staff_name"] == "Aziz"
    assert json.dumps(first.entities)


def test_wer(bench):
    assert bench.wer("Azizga ayt, zakazni yopsin", "azizga ayt zakazni yopsin") == 0.0
    assert bench.wer("a b c", "a x c") == pytest.approx(1 / 3)
    assert bench.wer("a b c", "a c") == pytest.approx(1 / 3)
    assert bench.wer("o‘sha 15:00", "oʻsha 15:00") == 0.0
    assert bench.wer("", "") == 0.0 and bench.wer("", "x") == 1.0


async def test_stt_bench_fake_mode(bench, tmp_path):
    rows = await bench.run([], tmp_path, fake=True, with_intents=True)
    assert len(rows) == 50 and all(r["wer"] == 0.0 for r in rows)
    text = (tmp_path / "results.md").read_text(encoding="utf-8")
    assert "| fake | 50 | 0 | 0.0 | 50/50 |" in text
    assert llm._fake is None  # fake LLM tozalangan
