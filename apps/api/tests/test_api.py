"""``/v1`` API (bot kontrakti) — sqlite + fakeredis + mock arq pool."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import arq
import fakeredis
import httpx
import pytest
from sqlalchemy import select

from engine import jobs
from engine.api.jarvis_routes import get_deps as get_jarvis_deps
from engine.db import get_session
from engine.integrations.crm_adapter import InMemoryCRM
from engine.jarvis import supervisor
from engine.jarvis.deps import JarvisDeps
from engine.main import app
from engine.models import ContentPlan, JarvisAction, Script, Staff, Task, TasteMemory

pytest_plugins = ["graph_fakes"]  # sqlite_db, graph_env, fake_llm, ... fixture'lari


@pytest.fixture
async def client(sqlite_db, monkeypatch):
    async def _session():
        async with sqlite_db() as s:
            yield s

    app.dependency_overrides[get_session] = _session

    notified: list[dict] = []

    async def _notify(*, chat_id, kind, payload):
        notified.append({"chat_id": chat_id, "kind": kind, "payload": payload})

    # ``JarvisDeps.session_factory`` — bir xil sqlite DB (``sqlite_db``), shunda
    # ``jarvis_decision`` endpointi va test o'zi bir xil jadvallarni ko'radi.
    jarvis_deps = JarvisDeps(crm=InMemoryCRM(), session_factory=sqlite_db, notify=_notify)
    app.dependency_overrides[get_jarvis_deps] = lambda: jarvis_deps

    pool = AsyncMock()
    create_pool = AsyncMock(return_value=pool)
    monkeypatch.setattr(arq, "create_pool", create_pool)
    jobs.set_redis(fakeredis.FakeAsyncRedis(decode_responses=True))
    app.state.arq = None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as c:
        c.pool = pool  # type: ignore[attr-defined]
        c.create_pool = create_pool  # type: ignore[attr-defined]
        c.db = sqlite_db  # type: ignore[attr-defined]
        c.jarvis_deps = jarvis_deps  # type: ignore[attr-defined]
        c.notified = notified  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()
    app.state.arq = None
    jobs.set_redis(None)


async def _workspace(client) -> dict:
    r = await client.post("/v1/workspaces", json={"owner_tg_id": 777, "name": "Qahva"})
    assert r.status_code == 200
    return r.json()


async def _script(client, ws_id: str) -> str:
    async with client.db() as s:
        plan = ContentPlan(workspace_id=uuid.UUID(ws_id),
                           week_start=__import__("datetime").date(2026, 9, 21),
                           status="adhoc", aida_json={"brief": "eski brif"})
        s.add(plan)
        await s.flush()
        row = Script(workspace_id=uuid.UUID(ws_id), plan_id=plan.id, day=0,
                     hook_variants={"hooks": ["a", "b", "c"], "selected": 0},
                     body="body", cta="cta", status="ready")
        s.add(row)
        await s.commit()
        return str(row.id)


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_workspace_create_get_and_brand_profile(client):
    r = await client.get("/v1/workspaces", params={"owner_tg_id": 777})
    assert r.status_code == 404

    ws = await _workspace(client)
    assert ws["name"] == "Qahva" and ws["owner_tg_id"] == 777
    assert ws["brand_profile"]["pronoun"] == "siz"
    # idempotent
    again = await _workspace(client)
    assert again["id"] == ws["id"]

    r = await client.get("/v1/workspaces", params={"owner_tg_id": 777})
    assert r.status_code == 200 and r.json()["id"] == ws["id"]

    r = await client.patch(f"/v1/workspaces/{ws['id']}/brand-profile",
                           json={"pronoun": "sen", "voice": "sardor"})
    assert r.status_code == 200
    profile = r.json()
    assert profile["pronoun"] == "sen" and profile["address_form"] == "sen"
    assert profile["tts_voice"] == "uz-UZ-SardorNeural" and profile["register"] == "neutral"
    r = await client.get(f"/v1/workspaces/{ws['id']}")
    assert r.json()["brand_profile"]["pronoun"] == "sen"

    r = await client.patch(f"/v1/workspaces/{uuid.uuid4()}/brand-profile", json={"x": 1})
    assert r.status_code == 404


async def test_create_brief_enqueues_and_job_status(client):
    ws = await _workspace(client)
    r = await client.post("/v1/briefs", json={"workspace_id": ws["id"], "text": " 15% chegirma "})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    client.create_pool.assert_awaited_once()
    client.pool.enqueue_job.assert_awaited_once_with(
        "run_brief", ws["id"], "15% chegirma", job_id, None, _job_id=job_id)

    r = await client.get(f"/v1/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued" and body["stage"] == "queued" and body["progress"] == 0
    assert body["result"]["workspace_id"] == ws["id"]

    await jobs.update(job_id, status="running", stage="render", script_id="s-1")
    body = (await client.get(f"/v1/jobs/{job_id}")).json()
    assert body["stage"] == "render" and body["progress"] == 70
    assert body["result"]["script_id"] == "s-1"

    assert (await client.get("/v1/jobs/nope")).status_code == 404
    r = await client.post("/v1/briefs", json={"workspace_id": str(uuid.uuid4()), "text": "x"})
    assert r.status_code == 404


async def test_script_approve_and_video_approve(client):
    ws = await _workspace(client)
    script_id = await _script(client, ws["id"])
    job_id = "job-1"
    await jobs.create(job_id, workspace_id=ws["id"], chat_id=777)
    await jobs.update(job_id, status="running", stage="render", script_id=script_id)

    r = await client.post(f"/v1/scripts/{script_id}/approve", json={"hook_idx": 2})
    assert r.status_code == 200
    assert r.json()["selected_hook_idx"] == 2 and r.json()["job_id"] == job_id
    assert (await jobs.get(job_id))["hook_idx"] == "2"

    # video hali tayyor emas
    r = await client.post(f"/v1/scripts/{script_id}/video-approve", json={"action": "publish"})
    assert r.status_code == 409

    await jobs.update(job_id, status="done", stage="awaiting_approval")
    r = await client.post(f"/v1/scripts/{script_id}/video-approve", json={"action": "schedule"})
    assert r.status_code == 200 and r.json()["ok"] is True
    client.pool.enqueue_job.assert_awaited_with(
        "resume_brief", job_id, {"decision": "schedule", "hook_idx": 2, "reason": ""})

    r = await client.post(f"/v1/scripts/{script_id}/approve", json={"hook_idx": 5})
    assert r.status_code == 422
    assert (await client.post(f"/v1/scripts/{uuid.uuid4()}/approve", json={})).status_code == 404


async def test_script_reject_paths(client):
    ws = await _workspace(client)
    script_id = await _script(client, ws["id"])
    job_id = "job-2"
    await jobs.create(job_id, workspace_id=ws["id"], chat_id=777)

    # graf ishlayapti → qaror navbatga
    await jobs.update(job_id, status="running", stage="asset_gen", script_id=script_id)
    r = await client.post(f"/v1/scripts/{script_id}/reject", json={"reason": "uzun"})
    assert r.json()["detail"] == "pending"
    assert await jobs.pop_pending_decision(job_id) == \
        {"decision": "reject", "reason": "uzun", "hook_idx": 0}

    # interrupt'da → resume_brief
    await jobs.update(job_id, status="done", stage="awaiting_approval")
    r = await client.post(f"/v1/scripts/{script_id}/reject", json={"reason": "uzun"})
    assert r.json()["detail"] == "resumed"
    client.pool.enqueue_job.assert_awaited_with(
        "resume_brief", job_id, {"decision": "reject", "reason": "uzun", "hook_idx": 0})

    # graf tugagan → to'g'ridan-to'g'ri taste_memory; "🔄 Qayta" → yangi job
    await jobs.update(job_id, stage="published")
    r = await client.post(f"/v1/scripts/{script_id}/reject",
                          json={"reason": "qayta yozish so'raldi"})
    body = r.json()
    assert body["detail"] == "recorded" and body["job_id"]
    client.pool.enqueue_job.assert_awaited_with(
        "run_brief", ws["id"], "eski brif", body["job_id"], None, _job_id=body["job_id"])
    async with client.db() as s:
        taste = (await s.execute(select(TasteMemory))).scalar_one()
        assert taste.kind == "rejected" and taste.reason == "qayta yozish so'raldi"
        assert (await s.get(Script, uuid.UUID(script_id))).status == "rejected"


async def test_daily_report(client):
    ws = await _workspace(client)
    r = await client.get(f"/v1/workspaces/{ws['id']}/daily-report")
    assert r.status_code == 200
    rep = r.json()
    assert rep["leads"] == 0 and rep["hot"] == 0 and rep["overdue"] == 0
    assert rep["cost_usd"] == 0.0


async def _noop(session) -> None:
    return None


async def test_jarvis_decision_yes_no_wired_to_supervisor(client):
    """``POST .../decision`` -> ``engine.jarvis.supervisor.decide`` (Task B): harakat
    qatori ``pending`` -> ``executed``/``cancelled`` ga o'tadi, notify chaqirilgan bo'ladi."""
    ws = await _workspace(client)
    ws_id = uuid.UUID(ws["id"])

    a1 = await supervisor.propose_action(
        client.jarvis_deps, workspace_id=ws_id, action_type="message_lead",
        payload={"lead_id": "l1"}, execute=_noop,
    )
    assert a1.status == "pending"
    assert client.notified[-1]["kind"] == "approval"  # propose_action o'zi ega/notify qiladi

    r = await client.post(f"/v1/jarvis-actions/{a1.id}/decision", json={"decision": "yes"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["detail"] == "executed"
    async with client.db() as s:
        row = await s.get(JarvisAction, a1.id)
        assert row.status == "executed" and row.executed_at is not None

    a2 = await supervisor.propose_action(
        client.jarvis_deps, workspace_id=ws_id, action_type="message_lead",
        payload={"lead_id": "l2"}, execute=_noop,
    )
    r = await client.post(f"/v1/jarvis-actions/{a2.id}/decision", json={"decision": "no"})
    assert r.status_code == 200 and r.json()["detail"] == "cancelled"
    async with client.db() as s:
        row = await s.get(JarvisAction, a2.id)
        assert row.status == "cancelled"

    r = await client.post(f"/v1/jarvis-actions/{uuid.uuid4()}/decision", json={"decision": "yes"})
    assert r.status_code == 404
    r = await client.post("/v1/jarvis-actions/garbage/decision", json={"decision": "yes"})
    assert r.status_code == 404
    r = await client.post(f"/v1/jarvis-actions/{a2.id}/decision", json={"decision": "maybe"})
    assert r.status_code == 422


async def test_jarvis_decision_edit_stores_edit_text_and_executes(client, monkeypatch):
    """``decision="edit"`` + ``comment`` -> ``supervisor.decide(..., edit_text=comment)``:
    ``message_lead`` bajaruvchisi shu matnni Chatwoot'ga yuboradi."""
    import engine.integrations.chatwoot as chatwoot_module

    sent: list[tuple[Any, str]] = []

    async def fake_reply(conversation_id, text):
        sent.append((conversation_id, text))

    monkeypatch.setattr(chatwoot_module, "reply", fake_reply)

    ws = await _workspace(client)
    action = await supervisor.propose_action(
        client.jarvis_deps, workspace_id=uuid.UUID(ws["id"]), action_type="message_lead",
        payload={"lead_id": "l3", "conversation_id": 42, "text": "eski matn"}, execute=_noop,
    )

    r = await client.post(f"/v1/jarvis-actions/{action.id}/decision",
                          json={"decision": "edit", "comment": "Yangi tahrirlangan matn"})
    assert r.status_code == 200 and r.json()["detail"] == "executed"
    assert sent == [(42, "Yangi tahrirlangan matn")]
    async with client.db() as s:
        row = await s.get(JarvisAction, action.id)
        assert row.status == "executed"
        assert row.payload["reply_text"] == "Yangi tahrirlangan matn"


async def test_jarvis_decision_report_all_batch_approves_pending(client):
    """"✉️ Hammasiga yoz" (``report:<ws>:all``, decision=yes) -> ``supervisor.batch_approve``:
    workspace'dagi barcha ``pending`` harakatlar ``executed`` ga o'tadi."""
    ws = await _workspace(client)
    ws_id = uuid.UUID(ws["id"])
    a1 = await supervisor.propose_action(
        client.jarvis_deps, workspace_id=ws_id, action_type="message_lead",
        payload={"lead_id": "l1"}, execute=_noop,
    )
    a2 = await supervisor.propose_action(
        client.jarvis_deps, workspace_id=ws_id, action_type="message_lead",
        payload={"lead_id": "l2"}, execute=_noop,
    )

    r = await client.post(f"/v1/jarvis-actions/report:{ws['id']}:all/decision",
                          json={"decision": "yes"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["detail"] == "approved"

    async with client.db() as s:
        rows = {row.id: row for row in (await s.execute(select(JarvisAction))).scalars()}
        assert rows[a1.id].status == "executed"
        assert rows[a2.id].status == "executed"

    r = await client.post(f"/v1/jarvis-actions/report:{uuid.uuid4()}:all/decision",
                          json={"decision": "yes"})
    assert r.status_code == 404
    r = await client.post(f"/v1/jarvis-actions/report:{ws['id']}:bogus/decision",
                          json={"decision": "yes"})
    assert r.status_code == 404


async def test_jarvis_decision_report_remind_reminds_overdue_staff(client):
    """"👤 Xodimga eslat" (``report:<ws>:remind``) -> muddati o'tgan ochiq vazifalar uchun
    ``remind_staff`` harakati yaratilib avtonom bajariladi, notify chaqiriladi (Task B)."""
    ws = await _workspace(client)
    ws_id = uuid.UUID(ws["id"])
    async with client.db() as s:
        staff = Staff(workspace_id=ws_id, name="Aziz", tg_id=555)
        s.add(staff)
        await s.flush()
        overdue = Task(workspace_id=ws_id, staff_id=staff.id, title="Qo'ng'iroq qiling",
                       due_at=datetime.now(UTC) - timedelta(hours=2), status="open")
        not_overdue = Task(workspace_id=ws_id, staff_id=staff.id, title="Ertaga",
                           due_at=datetime.now(UTC) + timedelta(hours=2), status="open")
        s.add_all([overdue, not_overdue])
        await s.commit()
        overdue_id, not_overdue_id = overdue.id, not_overdue.id

    r = await client.post(f"/v1/jarvis-actions/report:{ws['id']}:remind/decision",
                          json={"decision": "yes"})
    assert r.status_code == 200
    assert r.json()["detail"] == "approved"
    assert any(n["kind"] == "reminder" for n in client.notified)

    async with client.db() as s:
        actions = (await s.execute(
            select(JarvisAction).where(JarvisAction.type == "remind_staff")
        )).scalars().all()
        assert len(actions) == 1 and actions[0].status == "executed"
        assert (await s.get(Task, overdue_id)).reminders_sent == 1
        assert (await s.get(Task, not_overdue_id)).reminders_sent == 0

    # "no"/"edit" report qarorlari — hech narsa bajarilmaydi (bot faqat "yes" yuboradi)
    r = await client.post(f"/v1/jarvis-actions/report:{ws['id']}:remind/decision",
                          json={"decision": "no"})
    assert r.status_code == 200 and r.json()["detail"] == "no"


async def test_cost_sink_writes_cost_log(sqlite_db):
    from engine import cost_sink, cost_tracker
    from engine.models import CostLog, Workspace

    async with sqlite_db() as s:
        ws = Workspace(name="c", owner_tg_id=1)
        s.add(ws)
        await s.commit()
    cost_sink.install()
    try:
        await cost_tracker.log(str(ws.id), "writer", "fake", "gemini-2.5-flash", 10, 5, 0.001)
        await cost_tracker.log("", "writer", "fake", "gemini-2.5-flash", 10, 5, 0.001)
    finally:
        cost_sink.uninstall()
    async with sqlite_db() as s:
        rows = (await s.execute(select(CostLog))).scalars().all()
        assert len(rows) == 1 and rows[0].node == "writer" and rows[0].tokens_in == 10
