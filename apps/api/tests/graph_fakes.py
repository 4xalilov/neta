"""DaySubgraph / worker / API testlari uchun umumiy fake'lar (tarmoqsiz, Postgres'siz).

Test modullari uni pytest plugin sifatida yuklaydi (to'g'ridan-to'g'ri import qilmaydi —
aks holda assert rewrite ogohlantirishi chiqadi)::

    pytest_plugins = ["graph_fakes"]

Fixture'lar: ``sqlite_db``, ``workspace``, ``fake_llm``, ``fake_media``, ``graph_env``,
``fakes`` (shu modulning o'zi: ``fakes.initial_state(...)``, ``fakes.script_json(...)``).
"""
from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from engine import cost_tracker, db, llm, render_queue
from engine.integrations import images, storage, tts
from engine.models import BrandProfile, Workspace
from engine.settings import settings

BRAND = {
    "name": "Neta Coffee",
    "pronoun": "siz",
    "address_form": "siz",
    "register": "neutral",
    "banned_words": ["arzon"],
    "accent": "#FACC15",
    "bg": "#0B0F19",
    "font": "Plus Jakarta Sans",
}


def script_json(version: int) -> dict[str, Any]:
    return {
        "hooks": [f"Nega qahvangiz achchiq? v{version}", "3 ta xato", "Hamma deydi, lekin"],
        "body": f"Qahvani to'g'ri damlash sirlari. Versiya {version}.",
        "cta": "Obuna bo'ling!",
        "tts_text": "Nega qahvangiz achchiq? O'n besh foiz chegirma. Obuna bo'ling!",
        "display_text": "Nega qahvangiz achchiq? 15% chegirma. Obuna bo'ling!",
        "scenes": [
            {"img_prompt": "coffee cup on a table", "duration_s": 4, "subtitle": "Nega achchiq?"},
            {"img_prompt": "barista pouring milk", "duration_s": 5, "subtitle": "15% chegirma"},
            {"img_prompt": "happy customer", "duration_s": 4, "subtitle": "Obuna bo'ling!"},
        ],
    }


@dataclass
class FakeLLM:
    """Promptni system matnidagi ``# Rol: ...`` sarlavhasidan aniqlaydi.

    ``scores[i]`` — i-writer chaqirig'idan keyingi kritik ballari (uchala kritik bir xil,
    yoki ``{"uz": 9, "brand": 7, "hook": 9}`` dict).
    """

    scores: list[Any] = field(default_factory=lambda: [9])
    vision: dict[str, Any] = field(default_factory=lambda: {"pass": True, "issues": []})
    calls: list[tuple[str, str]] = field(default_factory=list)
    writer_calls: int = 0

    def _score(self, critic: str) -> int:
        idx = min(max(self.writer_calls - 1, 0), len(self.scores) - 1)
        s = self.scores[idx]
        return s[critic] if isinstance(s, dict) else s

    def __call__(self, tier: str, system: str, user: str) -> dict[str, Any]:
        head = system.splitlines()[0] if system else ""
        if "Writer" in head:
            self.writer_calls += 1
            self.calls.append(("writer", tier))
            return script_json(self.writer_calls)
        for critic, marker in (("uz", "UzCritic"), ("brand", "BrandCritic"),
                               ("hook", "HookCritic")):
            if marker in head:
                self.calls.append((critic, tier))
                out: dict[str, Any] = {"score": self._score(critic),
                                       "reasons": [f"{critic} sabab"],
                                       "fixes": [f"{critic} tuzatish"]}
                if critic == "hook":
                    out["best_hook_idx"] = 1
                return out
        if "VisionQA" in head:
            self.calls.append(("vision", tier))
            return self.vision
        raise AssertionError(f"noma'lum prompt: {head!r}")


async def fake_image(prompt: str, **kw: Any) -> images.ImageResult:
    n = uuid.uuid4().hex[:8]
    ws = kw.get("workspace_id", "")
    return images.ImageResult(uri=f"s3://assets/ws/{ws}/image/{n}.jpg",
                              url=f"https://fal.test/{n}.jpg", width=1080, height=1920,
                              seed=1, usd=0.003, model="fal-ai/flux/schnell")


async def fake_synthesize(text: str, **kw: Any) -> tts.TTSResult:
    words = tts.estimate_word_timings(text, 6.0)
    await cost_tracker.log_media(kw.get("workspace_id", ""), "tts", "fake", 0.01)
    return tts.TTSResult(audio=b"ID3fake", format="mp3", sample_rate=24000, duration_s=6.0,
                         words=words, provider="fake", voice="v", usd=0.01, chars=len(text))


async def fake_put_bytes(key: str, data: bytes, content_type: str) -> str:
    return f"s3://{settings.s3_bucket}/{key}"


@pytest_asyncio.fixture
async def sqlite_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await db.init_models(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db, "async_session", maker)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def workspace(sqlite_db) -> str:
    async with sqlite_db() as s:
        ws = Workspace(name="Test", owner_tg_id=42)
        s.add(ws)
        await s.flush()
        s.add(BrandProfile(workspace_id=ws.id, data=dict(BRAND)))
        await s.commit()
        return str(ws.id)


@pytest.fixture
def fake_llm():
    fake = FakeLLM()
    llm.set_fake(fake)
    yield fake
    llm.clear_fake()


@pytest.fixture
def fake_media(monkeypatch):
    images.set_fake_generator(fake_image)
    monkeypatch.setattr(tts, "synthesize", fake_synthesize)
    monkeypatch.setattr(storage, "put_bytes", fake_put_bytes)
    monkeypatch.setattr(settings, "render_poll_interval_s", 0.0)
    queue = render_queue.set_fake_queue()
    yield queue
    images.clear_fake_generator()
    render_queue.clear_fake_queue()


@pytest_asyncio.fixture
async def graph_env(sqlite_db, workspace, fake_llm, fake_media):
    """Hammasi tayyor: sqlite, workspace, fake LLM/TTS/FLUX/render navbati."""
    return {"db": sqlite_db, "workspace_id": workspace, "llm": fake_llm, "queue": fake_media,
            "fakes": sys.modules[__name__]}


@pytest.fixture
def fakes():
    """Yordamchi funksiyalar uchun modulning o'zi."""
    return sys.modules[__name__]


def initial_state(workspace_id: str, **kw: Any) -> dict[str, Any]:
    import time

    state = {
        "workspace_id": workspace_id,
        "brief": "Qahvaxonamiz uchun 15% chegirma haqida Reels",
        "day": 0,
        "plan_item": {"aida": "attention", "format": "reels"},
        "brand_profile": dict(BRAND),
        "taste": ["RAD — sabab: juda uzun: ..."],
        "references": [],
        "iteration": 0,
        "started_at": time.time(),
    }
    state.update(kw)
    return state


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
