"""CRM dashboard + Jarvis jurnali + demo-seed testlari (docs/06 "CRM web-sahifa (bosqich 5.8)").

Postgres'siz (sqlite + aiosqlite), ``engine.db.init_models`` + ``httpx.ASGITransport``
(``tests/test_vault.py`` bilan bir xil uslub).
"""

from __future__ import annotations

import uuid
from datetime import datetime

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from engine.api import crm_routes, jarvis_routes
from engine.db import get_session, init_models
from engine.integrations.crm_adapter import InMemoryCRM
from engine.jarvis import supervisor
from engine.jarvis.deps import JarvisDeps
from engine.models.content import Workspace


@pytest_asyncio.fixture
async def sqlite_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_models(bind=engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _notifier():
    notified: list[dict] = []

    async def notify(*, chat_id, kind, payload):
        notified.append({"chat_id": chat_id, "kind": kind, "payload": payload})

    return notify, notified


def _build_app(sqlite_session_factory, deps: JarvisDeps) -> FastAPI:
    app = FastAPI()
    app.include_router(crm_routes.router)

    async def _session():
        async with sqlite_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[jarvis_routes.get_deps] = lambda: deps
    return app


@pytest_asyncio.fixture
async def api_client(sqlite_session_factory):
    deps = JarvisDeps(crm=InMemoryCRM(), session_factory=sqlite_session_factory, notify=_notifier()[0])
    app = _build_app(sqlite_session_factory, deps)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://crm-test") as client:
        yield client


# ------------------------------------------------------------------------- static sahifa


async def test_static_page_and_assets_served(api_client):
    r = await api_client.get("/crm")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "crm.js" in r.text
    assert "chart.umd.js" in r.text

    r_js = await api_client.get("/crm/static/crm.js")
    assert r_js.status_code == 200
    assert "application/javascript" in r_js.headers["content-type"]

    r_css = await api_client.get("/crm/static/crm.css")
    assert r_css.status_code == 200
    assert "text/css" in r_css.headers["content-type"]

    r_chart = await api_client.get("/crm/static/chart.umd.js")
    assert r_chart.status_code == 200
    assert "application/javascript" in r_chart.headers["content-type"]
    assert len(r_chart.content) > 10_000  # vendored, not a stub

    r_missing = await api_client.get("/crm/static/nope.js")
    assert r_missing.status_code == 404


async def test_static_path_traversal_rejected(api_client):
    # "/crm/static/.." dan farqli o'laroq (bu yerda ".." httpx tomonidan mijoz
    # tarafida "/crm" ga normalizatsiya qilinadi — haqiqiy sahifa marshruti, 200
    # qaytaradi), "%2e%2e" server tomonida ".." ga dekodlanadi va bizning
    # ichki tekshiruvimizga (``file_name in {"..", "."}``) yetib boradi.
    r = await api_client.get("/crm/static/%2e%2e")
    assert r.status_code == 404
    r2 = await api_client.get("/crm/static/%2e")
    assert r2.status_code == 404
    r3 = await api_client.get("/crm/static/%2e%2e%2fmain.py")
    assert r3.status_code == 404


# ------------------------------------------------------------------------- demo-seed


async def test_demo_seed_creates_data_and_is_idempotent(api_client):
    r = await api_client.post("/v1/crm/demo-seed")
    assert r.status_code == 200
    body = r.json()
    assert body["skipped"] is False
    assert body["staff"] == 3
    assert body["campaigns"] == 3
    assert body["posts"] == 3
    assert body["leads"] == 40
    assert body["deals"] == 8
    assert body["tasks"] == 12
    assert body["jarvis_actions"] == 15
    assert body["cost_log"] == 24
    workspace_id = body["workspace_id"]

    r2 = await api_client.post("/v1/crm/demo-seed", params={"workspace_id": workspace_id})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["skipped"] is True
    assert body2["leads"] == 40


async def test_demo_seed_disabled_returns_403(api_client, monkeypatch):
    monkeypatch.setattr(crm_routes.settings, "crm_demo_seed_enabled", False)
    r = await api_client.post("/v1/crm/demo-seed")
    assert r.status_code == 403


async def test_demo_seed_unknown_workspace_404(api_client):
    r = await api_client.post("/v1/crm/demo-seed", params={"workspace_id": str(uuid.uuid4())})
    assert r.status_code == 404


# ------------------------------------------------------------------------- dashboard JSON


async def test_dashboard_empty_when_no_workspace(api_client):
    r = await api_client.get("/v1/crm/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert data["workspace_id"] is None
    assert data["kpis"]["leads_total"] == 0
    assert data["kpis_prev"] == data["kpis"]
    assert data["funnel"] == [
        {"stage": "new", "count": 0},
        {"stage": "contacted", "count": 0},
        {"stage": "meeting", "count": 0},
        {"stage": "deal", "count": 0},
        {"stage": "lost", "count": 0},
    ]
    assert data["campaigns"] == []
    assert data["staff"] == []
    assert data["jarvis_actions"] == []
    assert data["pending_actions"] == 0


async def test_dashboard_json_shape_and_consistency(api_client):
    seed = (await api_client.post("/v1/crm/demo-seed")).json()
    workspace_id = seed["workspace_id"]

    r = await api_client.get("/v1/crm/dashboard", params={"workspace_id": workspace_id})
    assert r.status_code == 200
    data = r.json()

    assert data["workspace_id"] == workspace_id
    for key in (
        "kpis", "kpis_prev", "leads_by_day", "funnel", "campaigns", "staff",
        "jarvis_actions", "pending_actions",
    ):
        assert key in data

    kpi_keys = {
        "leads_total", "leads_today", "hot", "warm", "cold", "deals_count", "revenue_uzs",
        "cost_usd", "cost_per_lead_usd", "tasks_open", "tasks_overdue", "reels_published",
    }
    kpis = data["kpis"]
    kpis_prev = data["kpis_prev"]
    assert kpi_keys <= set(kpis)
    assert set(kpis_prev) == set(kpis)  # kpis_prev — kpis bilan bir xil kalitlar

    assert kpis["leads_total"] == 40
    assert kpis["deals_count"] == 6  # demo seed: 6 "won" / 1 "lost" / 1 "open"
    assert kpis["revenue_uzs"] > 0
    assert kpis["tasks_open"] == 9  # 4 muddati o'tgan + 5 kelajakdagi
    assert kpis["tasks_overdue"] == 4
    assert kpis["reels_published"] == 3
    assert kpis["cost_usd"] > 0
    assert kpis["cost_per_lead_usd"] == pytest.approx(kpis["cost_usd"] / kpis["leads_total"], abs=0.01)

    # kpis_prev: oldingi 30 kunlik oyna — demo seed barcha ma'lumotni so'nggi 30 kun
    # ichida yaratadi, shuning uchun oldingi oynada hech narsa yo'q (delta = "yangi").
    assert kpis_prev["leads_total"] == 0
    assert kpis_prev["reels_published"] == 0
    assert kpis_prev["cost_usd"] == 0.0
    assert kpis_prev["deals_count"] == 0

    # funnel: to'liq tartib + yig'indi leads_total'ga teng
    assert [row["stage"] for row in data["funnel"]] == [
        "new", "contacted", "meeting", "deal", "lost",
    ]
    assert sum(row["count"] for row in data["funnel"]) == kpis["leads_total"]

    # leads_by_day: 30 kunlik oyna, har biri date/leads/hot bilan
    assert len(data["leads_by_day"]) == 30
    assert sum(row["leads"] for row in data["leads_by_day"]) == kpis["leads_total"]
    for row in data["leads_by_day"]:
        assert set(row) == {"date", "leads", "hot"}

    # kampaniyalar: 3 ta, ROI hisoblangan, reach post_metrics'dan kelgan
    campaigns = data["campaigns"]
    assert len(campaigns) == 3
    total_campaign_leads = 0
    for c in campaigns:
        for key in ("id", "name", "spend_usd", "leads", "deals", "revenue_uzs", "roi", "post_reach"):
            assert key in c
        assert c["spend_usd"] > 0
        assert c["post_reach"] > 0
        assert isinstance(c["roi"], float)
        total_campaign_leads += c["leads"]
    assert total_campaign_leads <= kpis["leads_total"]
    assert sum(c["deals"] for c in campaigns) <= kpis["deals_count"]

    # xodimlar: 3 ta, vazifalar bilan
    staff = data["staff"]
    assert len(staff) == 3
    for s in staff:
        for key in ("id", "name", "open_tasks", "done_tasks", "overdue", "avg_response_h"):
            assert key in s
    assert sum(s["open_tasks"] for s in staff) == kpis["tasks_open"]
    assert sum(s["overdue"] for s in staff) == kpis["tasks_overdue"]
    # demo seed: har xodimda kamida bitta "done" vazifa bor (12 ta, 3 tasi bajarilgan,
    # 3 xodim orasida bo'linadi) — created_at->updated_at farqi 2-30 soat bo'lgani uchun
    # o'rtacha javob vaqti mazmunli bo'lishi kerak (0 emas).
    assert all(0 < s["avg_response_h"] <= 30 for s in staff if s["done_tasks"] > 0)

    # Jarvis jurnali: 15 ta yozuv (<=30), 4 tasi kutilmoqda
    assert len(data["jarvis_actions"]) == 15
    assert data["pending_actions"] == 4
    pending_in_list = sum(1 for a in data["jarvis_actions"] if a["status"] == "pending")
    assert pending_in_list == 4
    for a in data["jarvis_actions"]:
        for key in ("id", "type", "level", "status", "payload", "created_at", "approved_by", "executed_at"):
            assert key in a
        # har turdagi harakat frontendning inson o'qiydigan xulosasi uchun kerakli
        # maydonlarni o'z ichiga oladi (crm.js ``jarvisTitle``) — raw JSON emas.
        payload = a["payload"]
        if a["type"] == "message_lead":
            assert payload["lead_name"] and payload["reply_text"]
        elif a["type"] == "call_lead":
            assert payload["lead_name"] and payload["reason"]
        elif a["type"] == "assign_task":
            assert payload["staff_name"] and payload["title"] and payload["due_at"]
        elif a["type"] == "escalate_owner":
            assert payload["staff_name"] and payload["title"] and "hours_overdue" in payload
        elif a["type"] == "send_report":
            assert {"leads", "hot", "overdue"} <= set(payload)
    # eng yangisi birinchi
    timestamps = [datetime.fromisoformat(a["created_at"]) for a in data["jarvis_actions"]]
    assert timestamps == sorted(timestamps, reverse=True)
    # matnlar turli qatorlarda farq qiladi (bir xil shablon takrorlanmaydi)
    message_texts = {
        a["payload"]["reply_text"] for a in data["jarvis_actions"] if a["type"] == "message_lead"
    }
    assert len(message_texts) > 1


# ------------------------------------------------------------------------- decision endpoint


async def test_decision_endpoint_pending_to_executed_and_notify_called(sqlite_session_factory):
    notify, notified = _notifier()
    deps = JarvisDeps(crm=InMemoryCRM(), session_factory=sqlite_session_factory, notify=notify)
    app = _build_app(sqlite_session_factory, deps)

    async with sqlite_session_factory() as session:
        ws = Workspace(name="Test Brand", timezone="Asia/Tashkent")
        session.add(ws)
        await session.commit()
        workspace_id = ws.id

    async def _execute(_session):
        return None

    action = await supervisor.propose_action(
        deps,
        workspace_id=workspace_id,
        action_type="message_lead",
        payload={"lead_id": str(uuid.uuid4()), "text": "Salom!"},
        execute=_execute,
    )
    assert action.status == "pending"
    assert len(notified) == 1  # requires_approval -> notify(...) chaqirilgan

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://crm-test") as client:
        r = await client.post(f"/v1/crm/actions/{action.id}/decision", json={"decision": "yes"})
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == str(action.id)
        assert body["status"] == "executed"

    async with sqlite_session_factory() as session:
        from engine.models.crm import JarvisAction

        refreshed = await session.get(JarvisAction, action.id)
        assert refreshed.status == "executed"
        assert refreshed.executed_at is not None


async def test_decision_endpoint_no_cancels_pending_action(sqlite_session_factory):
    notify, _notified = _notifier()
    deps = JarvisDeps(crm=InMemoryCRM(), session_factory=sqlite_session_factory, notify=notify)
    app = _build_app(sqlite_session_factory, deps)

    async with sqlite_session_factory() as session:
        ws = Workspace(name="Test Brand", timezone="Asia/Tashkent")
        session.add(ws)
        await session.commit()
        workspace_id = ws.id

    async def _execute(_session):
        return None

    action = await supervisor.propose_action(
        deps, workspace_id=workspace_id, action_type="call_lead",
        payload={"lead_id": str(uuid.uuid4())}, execute=_execute,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://crm-test") as client:
        r = await client.post(f"/v1/crm/actions/{action.id}/decision", json={"decision": "no"})
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"


async def test_decision_endpoint_bad_decision_422(api_client):
    r = await api_client.post(
        f"/v1/crm/actions/{uuid.uuid4()}/decision", json={"decision": "maybe"}
    )
    assert r.status_code == 422


async def test_decision_endpoint_unknown_action_404(api_client):
    r = await api_client.post(
        f"/v1/crm/actions/{uuid.uuid4()}/decision", json={"decision": "yes"}
    )
    assert r.status_code == 404
