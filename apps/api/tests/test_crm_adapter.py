"""engine.integrations.crm_adapter testlari. Tarmoq yo'q — Twenty httpx.MockTransport bilan."""
from __future__ import annotations

import httpx
import pytest

from engine.integrations import crm_adapter
from engine.integrations.crm_adapter import CRM, CRMError, InMemoryCRM, Lead, TwentyCRM, get_crm
from engine.settings import settings


def _lead(**overrides) -> Lead:
    base = {
        "id": "",
        "name": "Ali Valiyev",
        "phone": "+998901234567",
        "source": "ig_dm",
        "campaign_id": "camp-1",
        "temperature": "warm",
        "stage": "new",
        "assigned_to": None,
    }
    base.update(overrides)
    return Lead(**base)


# ---------------------------------------------------------------- InMemoryCRM


async def test_inmemory_lead_lifecycle():
    crm: CRM = InMemoryCRM()
    lead_id = await crm.create_lead(_lead())
    assert lead_id

    got = await crm.get_lead(lead_id)
    assert got is not None
    assert got.name == "Ali Valiyev" and got.stage == "new"

    await crm.update_stage(lead_id, "contacted")
    assert (await crm.get_lead(lead_id)).stage == "contacted"

    await crm.assign_lead(lead_id, "staff-1")
    assert (await crm.get_lead(lead_id)).assigned_to == "staff-1"

    await crm.update_lead_score(lead_id, "hot", 88)
    updated = await crm.get_lead(lead_id)
    assert updated.temperature == "hot" and updated.score == 88

    await crm.log_activity(lead_id, "Jarvis yozdi")
    assert crm._activity[lead_id] == ["Jarvis yozdi"]

    assert await crm.get_lead("no-such-id") is None


async def test_inmemory_tasks_and_campaign_stats():
    crm = InMemoryCRM()
    lead_id = await crm.create_lead(_lead(campaign_id="camp-9", stage="deal"))
    await crm.create_lead(_lead(campaign_id="camp-9", stage="new"))

    task_id = await crm.create_task("staff-1", "Uchrashuv belgilang", "2020-01-01T00:00:00+00:00", lead_id)
    assert task_id

    overdue = await crm.list_overdue_tasks()
    assert len(overdue) == 1 and overdue[0]["id"] == task_id

    open_tasks = await crm.list_open_tasks("staff-1")
    assert len(open_tasks) == 1

    await crm.complete_task(task_id)
    assert await crm.list_overdue_tasks() == []
    assert await crm.list_open_tasks("staff-1") == []

    stats = await crm.campaign_stats("camp-9")
    assert stats == {"campaign_id": "camp-9", "lead_count": 2, "deal_count": 1}


# ---------------------------------------------------------------- TwentyCRM (MockTransport)


def _handler(routes: dict[tuple[str, str], httpx.Response] | None = None, *, fail_times: int = 0):
    """``routes`` — ``(method, path) -> Response``. ``fail_times`` — shu son marta 500 qaytaradi,
    keyin ``routes`` dagi javobga o'tadi (retry testlari uchun)."""
    calls: list[httpx.Request] = []
    state = {"failed": 0}

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        key = (request.method, request.url.path)
        if state["failed"] < fail_times:
            state["failed"] += 1
            return httpx.Response(500, text="internal error")
        if routes and key in routes:
            return routes[key]
        return httpx.Response(404, json={"message": "not found"})

    return handle, calls


async def test_twenty_create_and_get_lead():
    routes = {
        ("POST", "/rest/leads"): httpx.Response(
            201, json={"data": {"createLead": {"id": "lead-abc", "name": "Ali"}}}
        ),
        ("GET", "/rest/leads/lead-abc"): httpx.Response(
            200,
            json={
                "data": {
                    "lead": {
                        "id": "lead-abc",
                        "name": "Ali Valiyev",
                        "phone": "+998901234567",
                        "source": "ig_dm",
                        "temperature": "warm",
                        "stage": "new",
                    }
                }
            },
        ),
    }
    handle, calls = _handler(routes)
    crm = TwentyCRM("http://twenty.local", "secret-key", transport=httpx.MockTransport(handle))

    lead_id = await crm.create_lead(_lead())
    assert lead_id == "lead-abc"

    lead = await crm.get_lead("lead-abc")
    assert lead is not None
    assert lead.name == "Ali Valiyev" and lead.stage == "new"

    assert calls[0].headers["authorization"] == "Bearer secret-key"


async def test_twenty_get_lead_not_found_returns_none():
    handle, _ = _handler({})  # hech qanday marshrut yo'q -> hammasi 404
    crm = TwentyCRM("http://twenty.local", "k", transport=httpx.MockTransport(handle))
    assert await crm.get_lead("missing") is None


async def test_twenty_update_stage_and_assign_and_score():
    seen: list[tuple[str, str, bytes]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.content))
        return httpx.Response(200, json={"data": {"lead": {"id": "lead-1"}}})

    crm = TwentyCRM("http://twenty.local", "k", transport=httpx.MockTransport(handle))
    await crm.update_stage("lead-1", "contacted")
    await crm.assign_lead("lead-1", "staff-9")
    await crm.update_lead_score("lead-1", "hot", 91)

    assert [m for m, _, _ in seen] == ["PATCH", "PATCH", "PATCH"]
    assert b'"contacted"' in seen[0][2]
    assert b'"staff-9"' in seen[1][2]
    assert b'"hot"' in seen[2][2] and b"91" in seen[2][2]


async def test_twenty_tasks_and_campaign_stats_and_activity():
    routes = {
        ("POST", "/rest/tasks"): httpx.Response(
            201, json={"data": {"createTask": {"id": "task-1"}}}
        ),
        ("GET", "/rest/tasks"): httpx.Response(
            200, json={"data": {"tasks": [{"id": "task-1", "status": "open"}]}}
        ),
        ("PATCH", "/rest/tasks/task-1"): httpx.Response(200, json={"data": {"task": {"id": "task-1"}}}),
        ("GET", "/rest/leads"): httpx.Response(
            200,
            json={
                "data": {
                    "leads": [
                        {"id": "l1", "stage": "deal"},
                        {"id": "l2", "stage": "new"},
                    ]
                }
            },
        ),
        ("POST", "/rest/notes"): httpx.Response(201, json={"data": {"createNote": {"id": "n1"}}}),
    }
    handle, _ = _handler(routes)
    crm = TwentyCRM("http://twenty.local", "k", transport=httpx.MockTransport(handle))

    task_id = await crm.create_task("staff-1", "Qo'ng'iroq qiling", "2026-01-01T00:00:00Z", "lead-1")
    assert task_id == "task-1"

    assert await crm.list_overdue_tasks() == [{"id": "task-1", "status": "open"}]
    assert await crm.list_open_tasks("staff-1") == [{"id": "task-1", "status": "open"}]

    await crm.complete_task("task-1")

    stats = await crm.campaign_stats("camp-1")
    assert stats == {"campaign_id": "camp-1", "lead_count": 2, "deal_count": 1}

    await crm.log_activity("lead-1", "eslatma yuborildi")


async def test_twenty_retries_on_5xx_then_succeeds():
    handle, calls = _handler(
        {("GET", "/rest/leads/lead-1"): httpx.Response(200, json={"data": {"lead": {"id": "lead-1"}}})},
        fail_times=2,
    )
    crm = TwentyCRM("http://twenty.local", "k", transport=httpx.MockTransport(handle))
    lead = await crm.get_lead("lead-1")
    assert lead is not None and lead.id == "lead-1"
    assert len(calls) == 3  # 2 marta 500, 3-marta muvaffaqiyatli


async def test_twenty_gives_up_after_max_attempts():
    handle, calls = _handler({}, fail_times=99)
    crm = TwentyCRM("http://twenty.local", "k", transport=httpx.MockTransport(handle))
    with pytest.raises(CRMError):
        await crm.get_lead("lead-1")
    assert len(calls) == 3


async def test_twenty_retries_on_connect_error():
    attempts = {"n": 0}

    def handle(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise httpx.ConnectError("ulanib bo'lmadi", request=request)
        return httpx.Response(200, json={"data": {"lead": {"id": "lead-1"}}})

    crm = TwentyCRM("http://twenty.local", "k", transport=httpx.MockTransport(handle))
    lead = await crm.get_lead("lead-1")
    assert lead is not None
    assert attempts["n"] == 2


# ---------------------------------------------------------------- get_crm() factory


def test_get_crm_returns_inmemory_by_default(monkeypatch):
    monkeypatch.setattr(crm_adapter, "_crm_singleton", None)
    monkeypatch.setattr(settings, "crm_provider", "memory")
    crm = get_crm()
    assert isinstance(crm, InMemoryCRM)
    assert get_crm() is crm  # keshlanadi


def test_get_crm_returns_twenty_when_configured(monkeypatch):
    monkeypatch.setattr(crm_adapter, "_crm_singleton", None)
    monkeypatch.setattr(settings, "crm_provider", "twenty")
    try:
        crm = get_crm()
        assert isinstance(crm, TwentyCRM)
    finally:
        monkeypatch.setattr(crm_adapter, "_crm_singleton", None)
