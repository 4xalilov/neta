"""``/v1`` API (bot kontrakti) — sqlite + fakeredis + mock arq pool."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import arq
import fakeredis
import httpx
import pytest
from sqlalchemy import select

from engine import jobs
from engine.db import get_session
from engine.main import app
from engine.models import ContentPlan, JarvisAction, Script, TasteMemory

pytest_plugins = ["graph_fakes"]  # sqlite_db, graph_env, fake_llm, ... fixture'lari


@pytest.fixture
async def client(sqlite_db, monkeypatch):
    async def _session():
        async with sqlite_db() as s:
            yield s

    app.dependency_overrides[get_session] = _session
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


async def test_daily_report_and_jarvis_decision(client):
    ws = await _workspace(client)
    r = await client.get(f"/v1/workspaces/{ws['id']}/daily-report")
    assert r.status_code == 200
    rep = r.json()
    assert rep["leads"] == 0 and rep["hot"] == 0 and rep["overdue"] == 0
    assert rep["cost_usd"] == 0.0

    r = await client.post(f"/v1/jarvis-actions/report:{ws['id']}:all/decision",
                          json={"decision": "yes"})
    assert r.status_code == 200 and r.json()["detail"] == "approved"
    async with client.db() as s:
        action = (await s.execute(select(JarvisAction))).scalar_one()
        assert action.type == "report_all" and action.status == "approved"
        action_id = str(action.id)

    r = await client.post(f"/v1/jarvis-actions/{action_id}/decision", json={"decision": "no"})
    assert r.json()["detail"] == "rejected"
    r = await client.post("/v1/jarvis-actions/garbage/decision", json={"decision": "yes"})
    assert r.status_code == 404
    r = await client.post(f"/v1/jarvis-actions/{action_id}/decision", json={"decision": "maybe"})
    assert r.status_code == 422


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
