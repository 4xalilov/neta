"""Chatwoot inbox: webhook qabul (message_created), javob yuborish, kontakt <-> lead sinxron.

Kodning boshqa joyi Chatwoot API'ni bilmaydi — faqat shu modul orqali (CLAUDE.md).
Chatwoot standart holatda webhookni HMAC bilan imzolamaydi, shuning uchun ulanish
maxfiy ``X-Webhook-Secret`` sarlavhasi bilan tekshiriladi (infra/chatwoot/README.md:
webhook sozlamasida custom header sifatida qo'shiladi). HMAC ixtiyoriy qo'shimcha
tekshiruv sifatida ham qo'llab-quvvatlanadi (agar kimdir shu yo'l bilan imzolasa).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from engine.integrations.crm_adapter import CRM, Lead
from engine.settings import settings

logger = logging.getLogger(__name__)

__all__ = [
    "ChatwootEvent",
    "get_contact",
    "handle_webhook",
    "link_contact_to_lead",
    "parse_webhook",
    "reply",
    "verify_signature",
]

NotifyFn = Callable[..., Awaitable[None]]

# Chatwoot inbox.channel_type -> bizning inbox_channel. TAXMIN — versiyaga qarab
# qiymatlar farq qilishi mumkin (https://www.chatwoot.com/docs webhook payload).
_CHANNEL_MAP = {
    "Channel::Instagram": "instagram",
    "Channel::FacebookPage": "instagram",  # Meta unified inbox holatlarida ham shu yo'nalish
    "Channel::Telegram": "telegram",
    "Channel::WebWidget": "website",
    "Channel::Api": "website",
}

# Chatwoot lead source -> bizning LeadSource (docs/02, models/crm.py::LeadSource)
_SOURCE_BY_CHANNEL = {
    "instagram": "ig_dm",
    "telegram": "site",
    "website": "site",
    "other": "site",
}


# ---------------------------------------------------------------- imzo tekshiruvi


def verify_signature(raw_body: bytes, header_sig: str | None, secret: str) -> bool:
    """Asosiy tekshiruv: ``header_sig`` (``X-Webhook-Secret`` sarlavhasi) maxfiy so'zga
    to'g'ridan-to'g'ri teng bo'lishi kerak (doimiy vaqtli taqqoslash). Qo'shimcha: agar
    ``header_sig`` to'g'ridan-to'g'ri mos kelmasa, HMAC-SHA256(raw_body, secret) hex
    ko'rinishiga solishtiriladi (ixtiyoriy, kimdir shu usul bilan imzolasa).
    """
    if not secret or not header_sig:
        return False
    if hmac.compare_digest(header_sig, secret):
        return True
    expected_hmac = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header_sig, expected_hmac)


# ---------------------------------------------------------------- webhook parsing


@dataclass
class ChatwootEvent:
    kind: str  # message_created | conversation_created | other
    conversation_id: int | None
    contact_id: str | None
    contact_name: str | None
    phone: str | None
    inbox_channel: str  # instagram | telegram | website | other
    text: str
    direction: str  # incoming | outgoing
    raw: dict


def _inbox_channel(payload: dict) -> str:
    channel_type = (payload.get("inbox") or {}).get("channel_type") or payload.get("channel") or ""
    return _CHANNEL_MAP.get(channel_type, "other")


def parse_webhook(payload: dict) -> ChatwootEvent:
    """Chatwoot webhook payload'ini ``ChatwootEvent`` ga aylantiradi.

    Payload shakli Chatwoot versiyasiga qarab biroz farq qilishi mumkin (TAXMIN) —
    shuning uchun maydonlar bir nechta kalit nomidan ``.get`` bilan olinadi.
    """
    event = payload.get("event", "other")
    kind = event if event in ("message_created", "conversation_created") else "other"

    conversation = payload.get("conversation") or {}
    conversation_id = conversation.get("id") if conversation else payload.get("conversation_id")
    if conversation_id is None:
        conversation_id = payload.get("id") if kind == "conversation_created" else None

    sender = payload.get("sender") or {}
    contact = payload.get("contact") or sender or {}
    raw_contact_id = contact.get("id")
    contact_id = str(raw_contact_id) if raw_contact_id is not None else None
    contact_name = contact.get("name")
    phone = contact.get("phone_number") or contact.get("phone")

    inbox_channel = _inbox_channel(payload)
    text = payload.get("content") or ""
    message_type = payload.get("message_type", "incoming")
    direction = "incoming" if message_type == "incoming" else "outgoing"

    return ChatwootEvent(
        kind=kind,
        conversation_id=conversation_id,
        contact_id=contact_id,
        contact_name=contact_name,
        phone=phone,
        inbox_channel=inbox_channel,
        text=text,
        direction=direction,
        raw=payload,
    )


# ---------------------------------------------------------------- Chatwoot REST


def _client(transport: httpx.BaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.chatwoot_url,
        transport=transport,
        timeout=30.0,
        headers={"api_access_token": settings.chatwoot_api_token},
    )


async def reply(
    conversation_id: int, text: str, *, transport: httpx.BaseTransport | None = None
) -> dict:
    """Suhbatga javob yozadi (POST .../conversations/{id}/messages)."""
    path = (
        f"/api/v1/accounts/{settings.chatwoot_account_id}"
        f"/conversations/{conversation_id}/messages"
    )
    async with _client(transport) as client:
        resp = await client.post(path, json={"content": text, "message_type": "outgoing"})
        resp.raise_for_status()
        return resp.json()


async def get_contact(
    contact_id: str, *, transport: httpx.BaseTransport | None = None
) -> dict:
    path = f"/api/v1/accounts/{settings.chatwoot_account_id}/contacts/{contact_id}"
    async with _client(transport) as client:
        resp = await client.get(path)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------- crm_link


async def link_contact_to_lead(
    session: AsyncSession,
    workspace_id: uuid.UUID | str,
    contact_id: str,
    lead_id: str,
) -> Any:
    """Chatwoot kontaktini CRM lid bilan ``crm_link`` jadvaliga yozadi.

    ``twenty_person_id`` — CRM'ning o'z lid/person id'si (Twenty bo'lsa Twenty id,
    ``InMemoryCRM`` bo'lsa uning ichki id'i) — ``lead_id`` parametri sifatida keladi.
    ``crm_link.lead_id`` (ichki Postgres ``lead`` jadvaliga FK) hozircha ishlatilmaydi
    (docs/07: "Twenty — asosiy manba"), shuning uchun ``None`` qoldiriladi.
    """
    from engine.models.crm import CrmLink  # aylanma import'dan qochish uchun shu yerda

    link = CrmLink(
        workspace_id=workspace_id,
        chatwoot_contact_id=str(contact_id),
        twenty_person_id=str(lead_id),
        lead_id=None,
    )
    session.add(link)
    await session.flush()
    return link


async def _default_workspace_id(session: AsyncSession) -> uuid.UUID:
    from engine.models.content import Workspace  # aylanma import'dan qochish uchun shu yerda

    ws_id = await session.scalar(select(Workspace.id).limit(1))
    if ws_id is None:
        raise RuntimeError(
            "chatwoot.handle_webhook: hech qanday Workspace topilmadi — avval bittasini yarating"
        )
    return ws_id


# ---------------------------------------------------------------- webhook -> Jarvis


async def handle_webhook(
    payload: dict,
    *,
    crm: CRM,
    session_factory: async_sessionmaker[AsyncSession],
    notify: NotifyFn,
    workspace_id: uuid.UUID | str | None = None,
) -> ChatwootEvent:
    """Chatwoot webhook'ini qabul qiladi: yangi kontaktdan kelgan kirish xabari bo'lsa —
    CRM'da Lead yaratadi, ``crm_link`` yozadi va ``jarvis.supervisor.handle_event`` ga
    ``lead.created`` eventini yuboradi. Allaqachon bog'langan kontakt bo'lsa — ``lead.reply``.
    """
    from engine.jarvis import supervisor as jarvis_supervisor
    from engine.jarvis.deps import JarvisDeps
    from engine.models.crm import CrmLink

    event = parse_webhook(payload)
    if event.kind != "message_created" or event.direction != "incoming" or not event.contact_id:
        return event

    deps = JarvisDeps(crm=crm, session_factory=session_factory, notify=notify)

    async with session_factory() as session:
        existing = await session.scalar(
            select(CrmLink).where(CrmLink.chatwoot_contact_id == str(event.contact_id))
        )

        if existing is not None:
            ws_id = existing.workspace_id
            lead_id = existing.twenty_person_id
        else:
            ws_id = workspace_id or await _default_workspace_id(session)
            source = _SOURCE_BY_CHANNEL.get(event.inbox_channel, "site")
            crm_lead = Lead(
                id="",
                name=event.contact_name or "Noma'lum",
                phone=event.phone,
                source=source,
                campaign_id=None,
                temperature="warm",
                stage="new",
                assigned_to=None,
                ig_handle=event.contact_name if event.inbox_channel == "instagram" else None,
            )
            lead_id = await crm.create_lead(crm_lead)
            await link_contact_to_lead(session, ws_id, event.contact_id, lead_id)
            await session.commit()

    event_type = "lead.reply" if existing is not None else "lead.created"
    jarvis_event = {
        "type": event_type,
        "workspace_id": str(ws_id),
        "lead_id": lead_id,
        "conversation_id": event.conversation_id,
        "text": event.text,
    }
    if event_type == "lead.created":
        jarvis_event.update(
            {
                "name": event.contact_name,
                "phone": event.phone,
                "source": _SOURCE_BY_CHANNEL.get(event.inbox_channel, "site"),
            }
        )

    try:
        await jarvis_supervisor.handle_event(jarvis_event, deps)
    except Exception:
        logger.exception("chatwoot.handle_webhook: jarvis.supervisor.handle_event xato berdi")

    return event
