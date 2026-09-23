"""``engine.jarvis.voice`` + ``/v1/voice/*`` (roadmap 5.10) — tarmoqsiz: fake LLM (kalit-so'z),
fake STT provayder, fake TTS, ffmpeg subprocess mock, sqlite."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import arq
import fakeredis
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from engine import jobs, llm
from engine.api.jarvis_routes import get_deps as get_jarvis_deps
from engine.db import init_models
from engine.integrations import audio as audio_mod
from engine.integrations import chatwoot, storage, stt, tts
from engine.integrations.crm_adapter import InMemoryCRM
from engine.jarvis import owner_memory, voice
from engine.jarvis.deps import JarvisDeps
from engine.models import (
    BrandProfile,
    JarvisAction,
    Lead,
    OwnerMemory,
    Staff,
    Task,
    Workspace,
)
from engine.settings import settings

TZ = ZoneInfo("Asia/Tashkent")
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=TZ)  # = 07:00 UTC, chorshanba
OWNER = 777


# ---------------------------------------------------------------- fake LLM (kalit-so'z)


def _intent(name, conf=0.95, **entities):
    return {"intent": name, "confidence": conf, "entities": entities,
            "clarify_question": None, "reply_hint": None}


def keyword_llm(tier, system, user):
    t = user.lower().replace("ʻ", "'").replace("ʼ", "'")
    if "hammasiga ha" in t:
        return _intent("approve_all")
    if t in ("ha", "ha, yubor"):
        return _intent("approve")
    if t.startswith("yo'q"):
        return _intent("reject")
    if "issiq lidlarga yoz" in t:
        return _intent("message_lead", temperature="issiq")
    if "malikaga yoz" in t:
        return _intent("message_lead", lead_name="Malikaga", message_text="Salom!")
    if "unga qo'ng'iroq" in t:
        return _intent("call_lead", 0.85)
    if "hisobot" in t:
        return _intent("daily_report", period="today" if "bugungi" in t else "yesterday")
    if "azizga ayt" in t:
        return _intent("assign_task", staff_name="Azizga", task_title="zakazni yopish",
                       due_text="ertaga 3 gacha")
    if "eslat" in t:
        return _intent("remind_staff", staff_name="Aziz")
    if "nechta lid" in t:
        return _intent("query_leads", period="today")
    if "vazifa" in t and "qancha" in t:
        return _intent("query_tasks")
    if "reels" in t:
        return _intent("create_brief", workspace_name="fitnes klub", count=3,
                       brief_text="fitnes klub uchun 3 ta Reels")
    if "o't" in t:
        return _intent("select_workspace", workspace_name="Olimp")
    if "ovoz" in t:
        return _intent("update_settings", setting_key="voice", setting_value="Sardor")
    if "salom" in t:
        return {**_intent("smalltalk"), "reply_hint": "Salom! Men shu yerdaman."}
    return {"intent": "unknown", "confidence": 0.3,
            "clarify_question": "Aniqroq aytib bera olasizmi?"}


# ---------------------------------------------------------------- fixtures


class TranscriptSTT:
    """Fake STT: audio baytlari = transkript (UTF-8)."""

    name = "fake"

    async def transcribe(self, audio, fmt, *, workspace_id=""):
        return stt.STTResult(text=audio.decode("utf-8"), provider=self.name, usd=0.001,
                             duration_s=2.0)


async def fake_tts(text, **kw):
    return tts.TTSResult(audio=b"ID3fake-mp3", format="mp3", sample_rate=24000,
                         duration_s=2.0, words=[], provider="fake", voice=kw.get("voice") or "v",
                         usd=0.0, chars=len(text))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    llm.set_fake(keyword_llm)
    monkeypatch.setitem(stt._PROVIDERS, "fake", TranscriptSTT)
    monkeypatch.setattr(settings, "stt_provider", "fake")
    monkeypatch.setattr(settings, "stt_fallback", "fake")
    monkeypatch.setattr(settings, "voice_reply", True)
    monkeypatch.setattr(tts, "synthesize", fake_tts)
    monkeypatch.setattr(audio_mod, "_ffmpeg_path", lambda: None)  # default: ffmpeg yo'q

    async def no_chatwoot(*a, **kw):
        raise AssertionError("chatwoot'ga yozilmasligi kerak")

    monkeypatch.setattr(chatwoot, "reply", no_chatwoot)
    yield
    llm.clear_fake()


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'voice.db'}")
    await init_models(bind=engine)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def world(db):
    async with db() as s:
        ws = Workspace(name="Qahva uyi", owner_tg_id=OWNER, timezone="Asia/Tashkent")
        ws2 = Workspace(name="Fitnes klub Olimp", owner_tg_id=OWNER, timezone="Asia/Tashkent")
        s.add_all([ws, ws2])
        await s.flush()
        s.add(BrandProfile(workspace_id=ws.id, data={"pronoun": "siz", "voice": "madina"}))
        aziz = Staff(workspace_id=ws.id, name="Aziz", tg_id=555)
        dilnoza = Staff(workspace_id=ws.id, name="Dilnoza", tg_id=556)
        s.add_all([aziz, dilnoza])
        today = datetime(2026, 9, 23, 6, 0, tzinfo=UTC)
        yesterday = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
        leads = [
            Lead(workspace_id=ws.id, source="ig_dm", name="Malika", temperature="hot",
                 score=90, created_at=today),
            Lead(workspace_id=ws.id, source="ig_dm", name="Sardor Aliyev", temperature="hot",
                 score=80, created_at=today),
            Lead(workspace_id=ws.id, source="site", name="Jasur", temperature="cold",
                 score=10, created_at=yesterday),
        ]
        s.add_all(leads)
        await s.commit()
        return SimpleNamespace(
            ws=ws.id, ws2=ws2.id, aziz=aziz.id, dilnoza=dilnoza.id,
            malika=leads[0].id, sardor=leads[1].id, jasur=leads[2].id,
        )


@pytest.fixture
def notified():
    return []


@pytest.fixture
def deps(db, notified):
    async def notify(*, chat_id, kind, payload):
        notified.append({"chat_id": chat_id, "kind": kind, "payload": payload})

    return JarvisDeps(crm=InMemoryCRM(), session_factory=db, notify=notify, now=lambda: NOW)


async def say(deps, text=None, *, audio=None, ws=None, chat_id=OWNER):
    return await voice.handle_owner_utterance(
        deps, chat_id=chat_id, workspace_id=ws, text=text, audio=audio, audio_fmt="ogg",
        now=NOW,
    )


async def _actions(db, **where):
    async with db() as s:
        stmt = select(JarvisAction)
        for k, v in where.items():
            stmt = stmt.where(getattr(JarvisAction, k) == v)
        return list(await s.scalars(stmt))


# ---------------------------------------------------------------- oqimlar


async def test_assign_task_via_voice_creates_task_and_notifies_staff(deps, db, world, notified):
    reply = await say(deps, audio=b"Azizga ayt, zakazni ertaga 3 gacha yopsin",
                      ws=world.ws)
    assert reply.transcript.startswith("Azizga ayt") and reply.stt_provider == "fake"
    assert reply.intent.intent == "assign_task" and not reply.needs_confirmation
    assert "Aziz" in reply.reply_text and "ertaga 15:00" in reply.reply_text

    async with db() as s:
        tasks = list(await s.scalars(select(Task)))
    assert len(tasks) == 1 and tasks[0].staff_id == world.aziz
    assert tasks[0].title == "zakazni yopish"
    due = tasks[0].due_at.replace(tzinfo=UTC) if tasks[0].due_at.tzinfo is None else tasks[0].due_at
    assert due == datetime(2026, 9, 24, 10, 0, tzinfo=UTC)  # 15:00 Toshkent

    task_msgs = [n for n in notified if n["kind"] == "task"]
    assert task_msgs and task_msgs[0]["chat_id"] == 555
    assert task_msgs[0]["payload"]["title"] == "zakazni yopish"
    (action,) = await _actions(db, type="assign_task")
    assert action.status == "executed" and reply.actions[0]["task_id"] == str(tasks[0].id)
    assert reply.reply_audio == b"ID3fake-mp3" and reply.reply_audio_fmt == "mp3"  # ffmpeg yo'q
    assert deps.crm._tasks  # Twenty'ga ham yozildi (InMemoryCRM)

    async with db() as s:
        rows = await owner_memory.recent(s, OWNER, 10)
    assert [r.role for r in rows] == ["user", "jarvis"]
    assert rows[0].intent_json["intent"] == "assign_task"
    assert rows[1].intent_json["staff_name"] == "Aziz"


async def test_message_lead_goes_through_policy_gate(deps, db, world, notified):
    reply = await say(deps, "issiq lidlarga yoz", ws=world.ws)
    assert reply.needs_confirmation
    assert reply.reply_text.startswith("2 ta issiq lidga xabar tayyor")
    pending = await _actions(db, type="message_lead")
    assert len(pending) == 2 and {a.status for a in pending} == {"pending"}
    approvals = [n for n in notified if n["kind"] == "approval"]
    assert len(approvals) == 2 and approvals[0]["chat_id"] == "owner"
    assert "yozaymi" in approvals[0]["payload"]["description"]

    # "ha" — oxirgi Jarvis javobidagi ikkala harakat tasdiqlanadi
    reply = await say(deps, "ha", ws=world.ws)
    assert reply.intent.intent == "approve"
    assert reply.reply_text == "Tasdiqlandi: 2 ta harakat bajarildi."
    assert {a.status for a in await _actions(db, type="message_lead")} == {"executed"}

    reply = await say(deps, "ha", ws=world.ws)
    assert reply.reply_text == "Tasdiq kutayotgan harakat yo'q."


async def test_approve_all_and_reject_via_voice(deps, db, world):
    await say(deps, "issiq lidlarga yoz", ws=world.ws)
    reply = await say(deps, "hammasiga ha", ws=world.ws)
    assert reply.intent.intent == "approve_all"
    assert reply.reply_text == "Hammasi tasdiqlandi: 2 ta harakat bajarildi."
    assert {a.status for a in await _actions(db)} == {"executed"}

    await say(deps, "Malikaga yoz", ws=world.ws)
    reply = await say(deps, "yo'q, kerakmas", ws=world.ws)
    assert reply.reply_text == "Bekor qilindi: 1 ta harakat."
    cancelled = await _actions(db, status="cancelled")
    assert len(cancelled) == 1 and cancelled[0].payload["lead_id"] == str(world.malika)


async def test_owner_memory_reference_resolution(deps, db, world, notified):
    await say(deps, "Malikaga yoz", ws=world.ws)
    reply = await say(deps, "unga qo'ng'iroq qil", ws=world.ws)
    assert reply.intent.intent == "call_lead"
    assert reply.intent.entities.lead_ids == [str(world.malika)]
    assert reply.needs_confirmation and "Malika" in reply.reply_text
    (call,) = await _actions(db, type="call_lead")
    assert call.status == "pending" and call.payload["lead_id"] == str(world.malika)


async def test_daily_report_reply(deps, world):
    reply = await say(deps, "kechagi hisobotni ayt", ws=world.ws)
    assert reply.intent.intent == "daily_report"
    assert reply.reply_text.startswith("Kecha: 1 lid")
    reply = await say(deps, "bugungi hisobot", ws=world.ws)
    assert reply.reply_text.startswith("Bugun: 2 lid (2 issiq)")


async def test_query_leads_and_tasks(deps, db, world):
    reply = await say(deps, "bugun nechta lid keldi", ws=world.ws)
    assert reply.reply_text == "Bugun 2 lid: 2 issiq."
    async with db() as s:
        s.add(Task(workspace_id=world.ws, staff_id=world.aziz, title="eski",
                   due_at=datetime(2026, 9, 22, 6, 0, tzinfo=UTC)))
        s.add(Task(workspace_id=world.ws, staff_id=world.dilnoza, title="yangi",
                   due_at=datetime(2026, 9, 30, 6, 0, tzinfo=UTC)))
        await s.commit()
    reply = await say(deps, "qancha vazifa bor", ws=world.ws)
    assert reply.reply_text == "2 ochiq vazifa, 1 tasi muddati o'tgan (Aziz 1)."


async def test_remind_staff(deps, db, world, notified):
    async with db() as s:
        s.add(Task(workspace_id=world.ws, staff_id=world.aziz, title="otchyot",
                   due_at=(NOW - timedelta(hours=3)).astimezone(UTC)))
        await s.commit()
    reply = await say(deps, "Azizga eslat", ws=world.ws)
    assert reply.reply_text == "Azizga eslatdim: 1 ta ochiq vazifa, 1 tasi muddati o'tgan."
    reminders = [n for n in notified if n["kind"] == "reminder"]
    assert reminders[0]["chat_id"] == 555 and reminders[0]["payload"]["titles"] == ["otchyot"]
    async with db() as s:
        (task,) = list(await s.scalars(select(Task)))
    assert task.reminders_sent == 1


async def test_create_brief_returns_enqueue_and_switches_workspace(deps, world):
    reply = await say(deps, "fitnes klub uchun 3 ta reels tayyorla", ws=world.ws)
    assert reply.intent.intent == "create_brief"
    assert reply.enqueue_brief == "fitnes klub uchun 3 ta Reels"
    assert reply.workspace_id == str(world.ws2)
    assert "Fitnes klub Olimp" in reply.reply_text


async def test_select_workspace_persists_in_memory(deps, db, world):
    reply = await say(deps, "Olimpga o't", ws=world.ws)
    assert reply.workspace_id == str(world.ws2) and "Fitnes klub Olimp" in reply.reply_text
    # workspace_id berilmasa — xotiradagi faol mijoz
    reply = await say(deps, "bugun nechta lid keldi")
    assert reply.workspace_id == str(world.ws2) and reply.reply_text == "Bugun lid yo'q."


async def test_update_settings(deps, db, world):
    reply = await say(deps, "ovozni Sardorga o'zgartir", ws=world.ws)
    assert reply.reply_text == "Sozlama saqlandi: ovoz — Sardor."
    async with db() as s:
        bp = (await s.scalars(select(BrandProfile).where(BrandProfile.workspace_id == world.ws)))
        data = next(iter(bp)).data
    assert data["voice"] == "sardor" and data["tts_voice"] == "uz-UZ-SardorNeural"


async def test_low_confidence_clarifies_without_actions(deps, db, world):
    reply = await say(deps, "anavi narsani qil", ws=world.ws)
    assert reply.clarify and reply.reply_text == "Aniqroq aytib bera olasizmi?"
    assert reply.actions == [] and await _actions(db) == []
    assert reply.reply_audio is not None  # savol ham ovoz bilan


async def test_smalltalk_no_workspace_and_stt_failure(deps, db, world, monkeypatch):
    reply = await say(deps, "salom", ws=world.ws)
    assert reply.reply_text == "Salom! Men shu yerdaman."

    reply = await say(deps, "bugun nechta lid keldi", chat_id=999)
    assert reply.reply_text == voice.NO_WORKSPACE_REPLY

    class Broken:
        name = "broken"

        async def transcribe(self, *a, **kw):
            raise RuntimeError("stt yo'q")

    monkeypatch.setitem(stt._PROVIDERS, "fake", Broken)
    reply = await say(deps, audio=b"OggS...", ws=world.ws)
    assert reply.reply_text == voice.STT_FAILED_REPLY and reply.transcript == ""


async def test_voice_reply_ogg_via_ffmpeg_and_tts_failure(deps, world, monkeypatch):
    monkeypatch.setattr(audio_mod, "_ffmpeg_path", lambda: "/usr/bin/ffmpeg")

    class Proc:
        returncode = 0

        async def communicate(self, data):
            assert data == b"ID3fake-mp3"
            return b"OggS-voice", b""

    async def fake_exec(*cmd, **kw):
        assert "libopus" in cmd
        return Proc()

    import asyncio

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    reply = await say(deps, "salom", ws=world.ws)
    assert reply.reply_audio == b"OggS-voice" and reply.reply_audio_fmt == "ogg"

    async def broken_tts(text, **kw):
        raise RuntimeError("tts yo'q")

    monkeypatch.setattr(tts, "synthesize", broken_tts)
    reply = await say(deps, "salom", ws=world.ws)
    assert reply.reply_audio is None and reply.reply_text

    monkeypatch.setattr(settings, "voice_reply", False)
    reply = await say(deps, "salom", ws=world.ws)
    assert reply.reply_audio is None


# ---------------------------------------------------------------- HTTP marshrut


@pytest.fixture
async def client(deps, world, monkeypatch):
    from engine.main import app

    app.dependency_overrides[get_jarvis_deps] = lambda: deps
    pool = AsyncMock()
    monkeypatch.setattr(arq, "create_pool", AsyncMock(return_value=pool))
    jobs.set_redis(fakeredis.FakeAsyncRedis(decode_responses=True))
    stored: dict[str, bytes] = {}

    async def put_bytes(key, data, content_type):
        stored[key] = data
        return f"s3://{settings.s3_bucket}/{key}"

    monkeypatch.setattr(storage, "put_bytes", put_bytes)
    app.state.arq = None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as c:
        c.pool = pool  # type: ignore[attr-defined]
        c.stored = stored  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()
    app.state.arq = None
    jobs.set_redis(None)


async def test_route_text_command(client, world):
    r = await client.post("/v1/voice/command", data={
        "text": "Azizga ayt, zakazni ertaga 3 gacha yopsin", "chat_id": str(OWNER),
        "workspace_id": str(world.ws)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "assign_task" and body["confidence"] == 0.95
    assert body["transcript"].startswith("Azizga") and body["needs_confirmation"] is False
    assert body["entities"]["staff_name"] == "Aziz"
    assert body["audio_url"].endswith(".mp3") and body["audio_b64"] is None
    assert body["audio_fmt"] == "mp3" and body["job_id"] is None
    assert body["workspace_id"] == str(world.ws)
    assert list(client.stored.values()) == [b"ID3fake-mp3"]
    assert any(k.startswith(f"ws/{world.ws}/audio/") for k in client.stored)


async def test_route_audio_command_and_storage_fallback(client, world, monkeypatch):
    async def broken_put(*a, **kw):
        raise ConnectionError("minio yo'q")

    monkeypatch.setattr(storage, "put_bytes", broken_put)
    files = {"audio": ("voice.oga", b"issiq lidlarga yoz", "audio/ogg")}
    r = await client.post("/v1/voice/command", files=files,
                          data={"chat_id": str(OWNER), "workspace_id": str(world.ws)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["transcript"] == "issiq lidlarga yoz" and body["stt_provider"] == "fake"
    assert body["intent"] == "message_lead" and body["needs_confirmation"] is True
    assert len(body["actions"]) == 2 and body["actions"][0]["status"] == "pending"
    assert body["audio_url"] is None
    assert base64.b64decode(body["audio_b64"]) == b"ID3fake-mp3"


async def test_route_create_brief_enqueues_job(client, world):
    r = await client.post("/v1/voice/command", data={
        "text": "fitnes klub uchun 3 ta reels tayyorla", "chat_id": str(OWNER)})
    body = r.json()
    assert body["intent"] == "create_brief" and body["job_id"]
    assert body["workspace_id"] == str(world.ws2)
    args = client.pool.enqueue_job.await_args
    assert args.args[0] == "run_brief" and args.args[1] == str(world.ws2)
    assert args.args[2] == "fitnes klub uchun 3 ta Reels"
    job = await jobs.get(body["job_id"])
    assert job["status"] == "queued"


async def test_route_validation_and_history(client, world):
    r = await client.post("/v1/voice/command", data={"chat_id": str(OWNER)})
    assert r.status_code == 422
    r = await client.post("/v1/voice/command", data={"text": "salom", "workspace_id": "bad"})
    assert r.status_code == 404

    await client.post("/v1/voice/command", data={"text": "salom", "chat_id": str(OWNER),
                                                 "workspace_id": str(world.ws)})
    r = await client.get("/v1/voice/history", params={"chat_id": OWNER, "n": 5})
    assert r.status_code == 200
    rows = r.json()
    assert [x["role"] for x in rows] == ["user", "jarvis"]
    assert rows[0]["text"] == "salom" and rows[0]["intent"] == "smalltalk"
    assert rows[1]["workspace_id"] == str(world.ws)


async def test_owner_memory_helpers(db, world):
    async with db() as s:
        for i in range(4):
            await owner_memory.remember(s, chat_id=1, role="user" if i % 2 == 0 else "jarvis",
                                        text=f"t{i}", workspace_id=world.ws,
                                        intent={"intent": "message_lead",
                                                "entities": {"lead_name": f"L{i}"}})
        await s.commit()
        rows = await owner_memory.recent(s, 1, 3)
        assert [r.text for r in rows] == ["t1", "t2", "t3"]
        assert await owner_memory.recent(s, 1, 0) == []
        assert owner_memory.last_value(rows, "lead_name") == "L3"
        assert owner_memory.last_value(rows, "lead_name", role="user") == "L2"
        assert owner_memory.last_user_intent(rows)["entities"]["lead_name"] == "L2"
        turns = owner_memory.as_prompt_turns(rows)
        assert turns[-1] == {"role": "jarvis", "text": "t3", "intent": "message_lead",
                             "entities": {"lead_name": "L3"}}
        with pytest.raises(ValueError):
            await owner_memory.remember(s, chat_id=1, role="bot", text="x")
        n = len(list(await s.scalars(select(OwnerMemory))))
        assert n == 4
    assert isinstance(uuid.uuid4(), uuid.UUID)
