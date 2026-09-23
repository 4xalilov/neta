"""``engine.jarvis`` (supervisor/policy/lead_scorer/task_manager/reporter) + ``jarvis_routes``
testlari. Tarmoq yo'q: LLM ``llm.set_fake``, HTTP ``httpx.MockTransport``/``ASGITransport``,
DB sqlite (``engine.db.init_models``).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from engine import llm
from engine.api import jarvis_routes
from engine.db import init_models
from engine.integrations.crm_adapter import InMemoryCRM, Lead
from engine.jarvis import lead_scorer, supervisor, task_manager
from engine.jarvis.deps import JarvisDeps
from engine.jarvis.policy import Level, level_for
from engine.models.content import Workspace
from engine.models.crm import JarvisAction, Staff, Task


@pytest.fixture(autouse=True)
def _fake_llm():
    llm.set_fake(
        lambda tier, system, user: {
            "temperature": "hot", "score": 77, "reason": "IG DM, telefon bor", "next_step": "yozish"
        }
    )
    yield
    llm.clear_fake()


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_models(bind=engine)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def workspace_id(session_factory) -> uuid.UUID:
    async with session_factory() as session:
        ws = Workspace(name="Test Brand", timezone="Asia/Tashkent")
        session.add(ws)
        await session.commit()
        return ws.id


@pytest.fixture
async def staff_id(session_factory, workspace_id) -> uuid.UUID:
    async with session_factory() as session:
        staff = Staff(workspace_id=workspace_id, name="Aziz", tg_id=555)
        session.add(staff)
        await session.commit()
        return staff.id


def _notifier():
    notified = []

    async def notify(*, chat_id, kind, payload):
        notified.append({"chat_id": chat_id, "kind": kind, "payload": payload})

    return notify, notified


def _deps(session_factory, *, crm=None, notify=None, now=None) -> JarvisDeps:
    kw = {}
    if now is not None:
        kw["now"] = now
    return JarvisDeps(
        crm=crm or InMemoryCRM(), session_factory=session_factory,
        notify=notify or _notifier()[0], **kw,
    )


# ---------------------------------------------------------------- policy


def test_policy_levels():
    assert level_for("message_lead") == Level.REQUIRES_APPROVAL
    assert level_for("assign_task") == Level.AUTONOMOUS
    assert level_for("unknown_action") == Level.REQUIRES_APPROVAL  # xavfsiz standart


# ---------------------------------------------------------------- lead_scorer


async def test_lead_scorer_writes_to_crm():
    crm = InMemoryCRM()
    lead_id = await crm.create_lead(
        Lead(id="", name="Ali", phone="+998901234567", source="ig_dm", campaign_id=None,
            temperature="warm", stage="new", assigned_to=None)
    )
    result = await lead_scorer.score_lead(crm, lead_id, workspace_id="ws-1")
    assert result["temperature"] == "hot" and result["score"] == 77

    lead = await crm.get_lead(lead_id)
    assert lead.temperature == "hot" and lead.score == 77


async def test_lead_scorer_missing_lead_raises():
    with pytest.raises(ValueError):
        await lead_scorer.score_lead(InMemoryCRM(), "no-such-id")


# ---------------------------------------------------------------- supervisor: policy gate


async def test_propose_action_message_lead_is_pending_and_notifies(session_factory, workspace_id):
    notify, notified = _notifier()
    deps = _deps(session_factory, notify=notify)

    async def execute(session):
        raise AssertionError("requires_approval harakat darhol bajarilmasligi kerak")

    action = await supervisor.propose_action(
        deps, workspace_id=workspace_id, action_type="message_lead",
        payload={"lead_id": "lead-1"}, execute=execute,
    )
    assert action.status == "pending"
    assert action.level == "requires_approval"
    assert len(notified) == 1
    assert notified[0]["kind"] == "approval"
    assert notified[0]["payload"]["type"] == "message_lead"


async def test_propose_action_assign_task_executes_autonomously(session_factory, workspace_id):
    notify, notified = _notifier()
    deps = _deps(session_factory, notify=notify)

    executed = []

    async def execute(session):
        executed.append(True)

    action = await supervisor.propose_action(
        deps, workspace_id=workspace_id, action_type="assign_task",
        payload={"staff_id": "staff-1"}, execute=execute,
    )
    assert action.status == "executed"
    assert action.level == "autonomous"
    assert action.executed_at is not None
    assert executed == [True]
    assert notified == []  # avtonom harakat egadan tasdiq so'ramaydi


# ---------------------------------------------------------------- supervisor: lead.created event


async def test_handle_event_lead_created_scores_and_proposes_message(session_factory, workspace_id):
    crm = InMemoryCRM()
    lead_id = await crm.create_lead(
        Lead(id="", name="Vali", phone="+998907654321", source="ig_dm", campaign_id=None,
            temperature="warm", stage="new", assigned_to=None)
    )
    notify, notified = _notifier()
    deps = _deps(session_factory, crm=crm, notify=notify)

    action = await supervisor.handle_event(
        {"type": "lead.created", "workspace_id": str(workspace_id), "lead_id": lead_id,
         "name": "Vali", "phone": "+998907654321", "source": "ig_dm", "conversation_id": 10,
         "text": "Salom"},
        deps,
    )
    assert action.type == "message_lead" and action.status == "pending"
    assert action.payload["temperature"] == "hot"
    assert len(notified) == 1


# ---------------------------------------------------------------- supervisor: decide / batch


async def test_decide_yes_executes_pending_change_deal(session_factory, workspace_id):
    crm = InMemoryCRM()
    lead_id = await crm.create_lead(
        Lead(id="", name="Ali", phone=None, source="site", campaign_id=None,
            temperature="warm", stage="new", assigned_to=None)
    )
    deps = _deps(session_factory, crm=crm)

    async def noop(session):
        return None

    action = await supervisor.propose_action(
        deps, workspace_id=workspace_id, action_type="change_deal",
        payload={"lead_id": lead_id, "stage": "deal"}, execute=noop,
    )
    assert action.status == "pending"

    decided = await supervisor.decide(deps, action.id, "yes")
    assert decided.status == "executed"
    assert (await crm.get_lead(lead_id)).stage == "deal"


async def test_decide_no_cancels(session_factory, workspace_id):
    deps = _deps(session_factory)

    async def noop(session):
        return None

    action = await supervisor.propose_action(
        deps, workspace_id=workspace_id, action_type="message_lead",
        payload={"lead_id": "l1"}, execute=noop,
    )
    decided = await supervisor.decide(deps, action.id, "no")
    assert decided.status == "cancelled"


async def test_batch_approve_all_pending(session_factory, workspace_id):
    deps = _deps(session_factory)

    async def noop(session):
        return None

    a1 = await supervisor.propose_action(
        deps, workspace_id=workspace_id, action_type="message_lead",
        payload={"lead_id": "l1"}, execute=noop,
    )
    a2 = await supervisor.propose_action(
        deps, workspace_id=workspace_id, action_type="message_lead",
        payload={"lead_id": "l2"}, execute=noop,
    )
    results = await supervisor.batch_approve(deps, workspace_id)
    assert {r.id for r in results} == {a1.id, a2.id}
    assert all(r.status == "executed" for r in results)


# ---------------------------------------------------------------- task_manager + eskalatsiya


def test_default_deadline_by_temperature():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert task_manager.default_deadline(now, "hot") == now + timedelta(hours=2)
    assert task_manager.default_deadline(now, "warm") == now + timedelta(hours=24)
    assert task_manager.default_deadline(now, "cold") == now + timedelta(hours=72)


async def test_overdue_task_reminder_then_escalation(session_factory, workspace_id, staff_id):
    async with session_factory() as session:
        now0 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        task = await task_manager.create_task(
            session, workspace_id=workspace_id, staff_id=staff_id, title="Uchrashuv belgilang",
            due_at=now0,
        )
        task_id = task.id
        await session.commit()

    notify, notified = _notifier()

    # 1 soat o'tdi -> eslatma kerak
    t1 = now0 + timedelta(hours=1, minutes=1)
    deps1 = _deps(session_factory, notify=notify, now=lambda: t1)
    async with session_factory() as session:
        due = await task_manager.reminders_due(session, t1)
        assert [t.id for t in due] == [task_id]
        assert await task_manager.escalations_due(session, t1) == []

    action = await supervisor.handle_event(
        {"type": "task.overdue", "task_id": str(task_id), "escalate": False}, deps1
    )
    assert action.type == "remind_staff" and action.status == "executed"
    assert notified[-1]["kind"] == "reminder"

    async with session_factory() as session:
        t = await session.get(Task, task_id)
        assert t.reminders_sent == 1

    # yana 1 soat o'tdi (jami 2 soat, reminders_sent hali 1) -> яна eslatma
    t2 = now0 + timedelta(hours=2, minutes=1)
    deps2 = _deps(session_factory, notify=notify, now=lambda: t2)
    async with session_factory() as session:
        due2 = await task_manager.reminders_due(session, t2)
        assert [t.id for t in due2] == [task_id]

    await supervisor.handle_event(
        {"type": "task.overdue", "task_id": str(task_id), "escalate": False}, deps2
    )
    async with session_factory() as session:
        t = await session.get(Task, task_id)
        assert t.reminders_sent == 2

    # endi eskalatsiya chegarasiga yetdi
    async with session_factory() as session:
        esc_due = await task_manager.escalations_due(session, t2)
        assert [t.id for t in esc_due] == [task_id]
        assert await task_manager.reminders_due(session, t2) == []  # reminders_sent >= chegaradan

    action2 = await supervisor.handle_event(
        {"type": "task.overdue", "task_id": str(task_id), "escalate": True}, deps2
    )
    assert action2.type == "escalate_owner" and action2.status == "executed"
    assert notified[-1]["kind"] == "escalation"
    assert notified[-1]["chat_id"] == supervisor.OWNER_CHAT_KEY

    async with session_factory() as session:
        t = await session.get(Task, task_id)
        assert t.escalated_at is not None


# ---------------------------------------------------------------- staff.reply / owner.command


async def test_staff_reply_completes_task(session_factory, workspace_id, staff_id):
    async with session_factory() as session:
        task = await task_manager.create_task(
            session, workspace_id=workspace_id, staff_id=staff_id, title="Qo'ng'iroq qiling",
            due_at=datetime.now(UTC),
        )
        task_id = task.id
        await session.commit()

    deps = _deps(session_factory)
    await supervisor.handle_event(
        {"type": "staff.reply", "staff_id": str(staff_id), "task_id": str(task_id),
         "text": "bajarildi", "chat_id": 555},
        deps,
    )
    async with session_factory() as session:
        t = await session.get(Task, task_id)
        assert t.status == "done"


async def test_owner_command_batch_approve(session_factory, workspace_id):
    deps = _deps(session_factory)

    async def noop(session):
        return None

    action = await supervisor.propose_action(
        deps, workspace_id=workspace_id, action_type="message_lead",
        payload={"lead_id": "l1"}, execute=noop,
    )
    await supervisor.handle_event(
        {"type": "owner.command", "workspace_id": str(workspace_id), "text": "hammasiga ha"},
        deps,
    )
    async with session_factory() as session:
        row = await session.get(JarvisAction, action.id)
        assert row.status == "executed"


# ---------------------------------------------------------------- reporter


async def test_daily_report_text(session_factory, workspace_id):
    async with session_factory() as session:
        result = await supervisor.reporter.build_daily_report(session, workspace_id=workspace_id)
    assert "lid" in result.text
    assert result.audio is None


# ---------------------------------------------------------------- HTTP marshrut (jarvis_routes)


@pytest.fixture
async def api_client(session_factory, workspace_id, monkeypatch):
    from engine.settings import settings

    monkeypatch.setattr(settings, "chatwoot_webhook_secret", "test-secret")

    app = FastAPI()
    app.include_router(jarvis_routes.router)

    crm = InMemoryCRM()
    lead_id = await crm.create_lead(
        Lead(id="", name="Ali", phone=None, source="ig_dm", campaign_id=None,
            temperature="warm", stage="new", assigned_to=None)
    )

    notify, notified = _notifier()
    deps = _deps(session_factory, crm=crm, notify=notify)
    app.dependency_overrides[jarvis_routes.get_deps] = lambda: deps

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.notified = notified  # type: ignore[attr-defined]
        client.workspace_id = workspace_id  # type: ignore[attr-defined]
        client.lead_id = lead_id  # type: ignore[attr-defined]
        yield client


async def test_route_inject_event_and_list_and_decision(api_client):
    resp = await api_client.post(
        "/v1/jarvis/events",
        json={
            "type": "cron.daily_report",
            "workspace_id": str(api_client.workspace_id),
            "company": "Test Brand",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok" and body["action_status"] == "executed"
    assert api_client.notified[-1]["kind"] == "daily_report"

    resp = await api_client.get("/v1/jarvis/actions", params={"status": "executed"})
    assert resp.status_code == 200
    actions = resp.json()
    assert any(a["type"] == "send_report" for a in actions)

    resp = await api_client.get(
        "/v1/jarvis/report/daily", params={"workspace_id": str(api_client.workspace_id)}
    )
    assert resp.status_code == 200
    assert "lid" in resp.json()["text"]


async def test_route_decision_flow(api_client):
    resp = await api_client.post(
        "/v1/jarvis/events",
        json={
            "type": "lead.created", "workspace_id": str(api_client.workspace_id),
            "lead_id": api_client.lead_id, "name": "Ali", "phone": None, "source": "ig_dm",
            "conversation_id": None, "text": "salom",
        },
    )
    action_id = resp.json()["action_id"]

    resp = await api_client.post(
        f"/v1/jarvis/actions/{action_id}/decision", json={"decision": "yes"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "executed"

    resp = await api_client.post(
        f"/v1/jarvis/actions/{uuid.uuid4()}/decision", json={"decision": "yes"}
    )
    assert resp.status_code == 404

    resp = await api_client.post(
        f"/v1/jarvis/actions/{action_id}/decision", json={"decision": "maybe"}
    )
    assert resp.status_code == 422


async def test_route_webhook_secret_check(api_client):
    resp = await api_client.post(
        "/webhooks/chatwoot",
        json={"event": "message_created", "message_type": "incoming"},
        headers={"X-Webhook-Secret": "wrong"},
    )
    assert resp.status_code == 401

    resp = await api_client.post(
        "/webhooks/chatwoot",
        json={"event": "conversation_created"},
        headers={"X-Webhook-Secret": "test-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
