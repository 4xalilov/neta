"""engine.integrations.chatwoot testlari. Tarmoq yo'q — httpx.MockTransport; DB — sqlite."""
from __future__ import annotations

import hashlib
import hmac

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from engine import llm
from engine.db import init_models
from engine.integrations import chatwoot
from engine.integrations.crm_adapter import InMemoryCRM
from engine.models.content import Workspace
from engine.models.crm import CrmLink


@pytest.fixture(autouse=True)
def _fake_llm():
    """``handle_webhook`` -> ``jarvis.supervisor`` -> ``lead_scorer`` LLM chaqiradi (lead.created
    hodisasida) — haqiqiy tarmoqqa chiqmasin."""
    llm.set_fake(
        lambda tier, system, user: {
            "temperature": "warm", "score": 50, "reason": "avtomatik baholash", "next_step": "kuzatish"
        }
    )
    yield
    llm.clear_fake()


# ---------------------------------------------------------------- verify_signature


def test_verify_signature_shared_secret_match():
    assert chatwoot.verify_signature(b"{}", "shhh", "shhh") is True


def test_verify_signature_mismatch():
    assert chatwoot.verify_signature(b"{}", "wrong", "shhh") is False
    assert chatwoot.verify_signature(b"{}", None, "shhh") is False
    assert chatwoot.verify_signature(b"{}", "shhh", "") is False


def test_verify_signature_hmac_fallback():
    body = b'{"event": "message_created"}'
    digest = hmac.new(b"shhh", body, hashlib.sha256).hexdigest()
    assert chatwoot.verify_signature(body, digest, "shhh") is True


# ---------------------------------------------------------------- parse_webhook


def test_parse_webhook_incoming_instagram_dm():
    payload = {
        "event": "message_created",
        "message_type": "incoming",
        "content": "Salom, narxi qancha?",
        "conversation": {"id": 42},
        "inbox": {"channel_type": "Channel::Instagram"},
        "sender": {"id": 7, "name": "Ali", "phone_number": None},
    }
    event = chatwoot.parse_webhook(payload)
    assert event.kind == "message_created"
    assert event.conversation_id == 42
    assert event.contact_id == "7"
    assert event.contact_name == "Ali"
    assert event.inbox_channel == "instagram"
    assert event.direction == "incoming"
    assert event.text == "Salom, narxi qancha?"


def test_parse_webhook_outgoing_is_other_direction():
    payload = {
        "event": "message_created",
        "message_type": "outgoing",
        "content": "Salom!",
        "conversation": {"id": 1},
        "inbox": {"channel_type": "Channel::Telegram"},
        "sender": {"id": 3, "name": "Bot"},
    }
    event = chatwoot.parse_webhook(payload)
    assert event.direction == "outgoing"
    assert event.inbox_channel == "telegram"


def test_parse_webhook_unknown_event_is_other():
    event = chatwoot.parse_webhook({"event": "contact_updated"})
    assert event.kind == "other"


# ---------------------------------------------------------------- reply / get_contact


async def test_reply_posts_to_chatwoot(monkeypatch):
    from engine.settings import settings

    monkeypatch.setattr(settings, "chatwoot_url", "http://chatwoot.local")
    monkeypatch.setattr(settings, "chatwoot_account_id", 5)
    monkeypatch.setattr(settings, "chatwoot_api_token", "tok-123")

    seen = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["token"] = request.headers.get("api_access_token")
        seen["body"] = request.content
        return httpx.Response(200, json={"id": 99})

    await chatwoot.reply(42, "Salom!", transport=httpx.MockTransport(handle))
    assert seen["path"] == "/api/v1/accounts/5/conversations/42/messages"
    assert seen["token"] == "tok-123"
    assert b"Salom" in seen["body"]


async def test_get_contact(monkeypatch):
    from engine.settings import settings

    monkeypatch.setattr(settings, "chatwoot_url", "http://chatwoot.local")
    monkeypatch.setattr(settings, "chatwoot_account_id", 5)

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/accounts/5/contacts/7"
        return httpx.Response(200, json={"id": 7, "name": "Ali"})

    contact = await chatwoot.get_contact("7", transport=httpx.MockTransport(handle))
    assert contact == {"id": 7, "name": "Ali"}


# ---------------------------------------------------------------- handle_webhook


@pytest.fixture
async def sqlite_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_models(bind=engine)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _make_workspace(session_factory) -> str:
    async with session_factory() as session:
        ws = Workspace(name="Test Brand", timezone="Asia/Tashkent")
        session.add(ws)
        await session.commit()
        return str(ws.id)


async def test_handle_webhook_new_contact_creates_lead_and_link(sqlite_session_factory):
    await _make_workspace(sqlite_session_factory)
    crm = InMemoryCRM()
    notified = []

    async def notify(*, chat_id, kind, payload):
        notified.append({"chat_id": chat_id, "kind": kind, "payload": payload})

    payload = {
        "event": "message_created",
        "message_type": "incoming",
        "content": "Salom, narxi qancha?",
        "conversation": {"id": 1},
        "inbox": {"channel_type": "Channel::Instagram"},
        "sender": {"id": 55, "name": "Vali", "phone_number": "+998901112233"},
    }

    event = await chatwoot.handle_webhook(
        payload, crm=crm, session_factory=sqlite_session_factory, notify=notify
    )
    assert event.contact_id == "55"

    # CRM'da lid yaratilgan
    assert len(crm._leads) == 1
    lead = next(iter(crm._leads.values()))
    assert lead.source == "ig_dm" and lead.name == "Vali"

    # crm_link yozilgan
    async with sqlite_session_factory() as session:
        from sqlalchemy import select

        link = (await session.scalars(select(CrmLink))).one()
        assert link.chatwoot_contact_id == "55"
        assert link.twenty_person_id == next(iter(crm._leads))

    # message_lead requires_approval -> egaga tasdiq so'ralgan
    assert len(notified) == 1
    assert notified[0]["kind"] == "approval"
    assert notified[0]["payload"]["type"] == "message_lead"


async def test_handle_webhook_existing_contact_is_lead_reply(sqlite_session_factory):
    await _make_workspace(sqlite_session_factory)
    crm = InMemoryCRM()
    notified = []

    async def notify(*, chat_id, kind, payload):
        notified.append(payload)

    payload = {
        "event": "message_created",
        "message_type": "incoming",
        "content": "birinchi xabar",
        "conversation": {"id": 1},
        "inbox": {"channel_type": "Channel::Instagram"},
        "sender": {"id": 77, "name": "Laylo"},
    }
    await chatwoot.handle_webhook(
        payload, crm=crm, session_factory=sqlite_session_factory, notify=notify
    )
    assert len(crm._leads) == 1

    payload2 = {**payload, "content": "ikkinchi xabar"}
    await chatwoot.handle_webhook(
        payload2, crm=crm, session_factory=sqlite_session_factory, notify=notify
    )
    # yangi lid yaratilmagan (bitta kontakt uchun bitta lid)
    assert len(crm._leads) == 1
    assert len(notified) == 2  # ikkalasi ham message_lead approval so'ragan


async def test_handle_webhook_outgoing_message_ignored(sqlite_session_factory):
    await _make_workspace(sqlite_session_factory)
    crm = InMemoryCRM()

    async def notify(**kw):
        raise AssertionError("outgoing xabar uchun notify chaqirilmasligi kerak")

    payload = {
        "event": "message_created",
        "message_type": "outgoing",
        "content": "Salom!",
        "conversation": {"id": 1},
        "inbox": {"channel_type": "Channel::Instagram"},
        "sender": {"id": 1, "name": "Bot"},
    }
    await chatwoot.handle_webhook(
        payload, crm=crm, session_factory=sqlite_session_factory, notify=notify
    )
    assert crm._leads == {}
