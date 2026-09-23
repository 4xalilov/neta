"""Twenty CRM ustida yupqa adapter. Kodning boshqa joyi Twenty API'ni bilmaydi
(docs/07-open-source-foundations.md: "faqat crm_adapter.py orqali murojaat qilinadi").

Ikkita implementatsiya bir xil ``CRM`` Protocol'ni bajaradi:
- ``TwentyCRM`` — ishlab chiqarish, Twenty REST API ustidan (``{twenty_url}/rest/...``).
- ``InMemoryCRM`` — testlar va dev uchun (``settings.crm_provider == "memory"``).

Twenty haqida: standart obyektlar (``people``, ``companies``, ``opportunities``, ``tasks``) +
bizning custom obyekt ``leads`` (Lead: name, phone, ig_handle, source, temperature, stage,
score, campaign_id, assigned_to — infra/twenty/README.md). Task uchun Twenty'ning o'z
``tasks`` obyekti ishlatiladi.

DIQQAT: ``TwentyCRM._PATHS`` dagi yo'llar va JSON javob shakli TAXMIN — real Twenty
instansiyasida ``TWENTY_VERSION`` (``.env``) bo'yicha https://docs.twenty.com bilan
tasdiqlanishi kerak (docs/07 "Xavflar": "Twenty tez o'zgaradi").
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, ClassVar, Protocol

import httpx

from engine.settings import settings

logger = logging.getLogger(__name__)

__all__ = [
    "CRM",
    "CRMError",
    "InMemoryCRM",
    "Lead",
    "TwentyCRM",
    "get_crm",
]


class CRMError(RuntimeError):
    """CRM (Twenty) bilan aloqa xatosi — retry'lardan keyin ham muvaffaqiyatsiz, yoki
    4xx/5xx javob. Chaqiruvchi tomon Twenty'ning ichki tafsilotlarini bilmasligi kerak,
    shuning uchun bitta umumiy tur bilan ko'tariladi.
    """


@dataclass
class Lead:
    id: str
    name: str
    phone: str | None
    source: str
    campaign_id: str | None
    temperature: str  # hot|warm|cold
    stage: str        # new|contacted|meeting|deal|lost
    assigned_to: str | None
    score: float | None = None
    ig_handle: str | None = None


class CRM(Protocol):
    async def create_lead(self, lead: Lead) -> str: ...
    async def get_lead(self, lead_id: str) -> Lead | None: ...
    async def update_stage(self, lead_id: str, stage: str) -> None: ...
    async def update_lead_score(self, lead_id: str, temperature: str, score: float) -> None: ...
    async def assign_lead(self, lead_id: str, staff_id: str) -> None: ...
    async def create_task(
        self, staff_id: str, title: str, due_at: str, lead_id: str | None
    ) -> str: ...
    async def complete_task(self, task_id: str) -> None: ...
    async def list_overdue_tasks(self) -> list[dict]: ...
    async def list_open_tasks(self, staff_id: str) -> list[dict]: ...
    async def campaign_stats(self, campaign_id: str) -> dict: ...
    async def log_activity(self, lead_id: str, text: str) -> None: ...


# ---------------------------------------------------------------- Twenty (ishlab chiqarish)


def _unwrap(data: Any) -> Any:
    """Twenty REST javobi odatda ``{"data": {...}}`` bilan o'raladi, ba'zan ichida yana bitta
    obyekt nomi bo'ladi (masalan ``{"data": {"createLead": {...}}}`` yoki
    ``{"data": {"leads": [...]}}``). Bu funksiya shu qatlamlarni ochadi. TAXMIN — haqiqiy
    Twenty javobi bilan tasdiqlanishi kerak.
    """
    if isinstance(data, dict) and "data" in data:
        inner = data["data"]
        if isinstance(inner, dict) and len(inner) == 1:
            return next(iter(inner.values()))
        return inner
    return data


def _extract_id(data: Any) -> str:
    rec = _unwrap(data)
    if isinstance(rec, list):
        rec = rec[0] if rec else {}
    if isinstance(rec, dict):
        return str(rec.get("id", ""))
    return ""


def _extract_record(data: Any) -> dict | None:
    rec = _unwrap(data)
    if isinstance(rec, list):
        return rec[0] if rec else None
    return rec if isinstance(rec, dict) else None


def _extract_list(data: Any) -> list[dict]:
    rec = _unwrap(data)
    if isinstance(rec, list):
        return rec
    if isinstance(rec, dict):
        for v in rec.values():
            if isinstance(v, list):
                return v
    return []


def _lead_from_dict(d: dict) -> Lead:
    return Lead(
        id=str(d.get("id", "")),
        name=d.get("name", ""),
        phone=d.get("phone"),
        source=d.get("source", ""),
        campaign_id=d.get("campaignId") or d.get("campaign_id"),
        temperature=d.get("temperature", ""),
        stage=d.get("stage", "new"),
        assigned_to=d.get("assignedTo") or d.get("assigned_to"),
        score=d.get("score"),
        ig_handle=d.get("igHandle") or d.get("ig_handle"),
    )


class TwentyCRM:
    """Twenty CRM ustidagi yupqa REST adapter (``httpx.AsyncClient``, 3 urinishgacha retry).

    Har bir chaqiriqda yangi ``AsyncClient`` ochiladi (``integrations/tts.py`` dagi
    ``NavoiyTTS``/``AishaTTS`` uslubiga mos) — testda ``transport=httpx.MockTransport(...)``
    beriladi.
    """

    # verify against https://docs.twenty.com for TWENTY_VERSION
    _PATHS: ClassVar[dict[str, str]] = {
        "leads": "/rest/leads",
        "lead": "/rest/leads/{id}",
        "tasks": "/rest/tasks",
        "task": "/rest/tasks/{id}",
        "people": "/rest/people",
        "companies": "/rest/companies",
        "opportunities": "/rest/opportunities",
        "notes": "/rest/notes",
    }

    _MAX_ATTEMPTS = 3
    _BACKOFF_S = 0.05

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else settings.twenty_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.twenty_api_key
        self._transport = transport  # faqat testlar uchun (httpx.MockTransport)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            transport=self._transport,
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        last_exc: CRMError | None = None
        for attempt in range(self._MAX_ATTEMPTS):
            try:
                async with self._client() as client:
                    resp = await client.request(method, path, **kw)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_exc = CRMError(f"Twenty {method} {path}: ulanish xatosi: {exc}")
                if attempt < self._MAX_ATTEMPTS - 1:
                    await asyncio.sleep(self._BACKOFF_S * (attempt + 1))
                    continue
                raise last_exc from exc

            if resp.status_code >= 500:
                last_exc = CRMError(f"Twenty {method} {path} -> {resp.status_code}: {resp.text}")
                if attempt < self._MAX_ATTEMPTS - 1:
                    await asyncio.sleep(self._BACKOFF_S * (attempt + 1))
                    continue
                raise last_exc

            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise CRMError(
                    f"Twenty {method} {path} -> {exc.response.status_code}: {exc.response.text}"
                ) from exc
            return resp

        assert last_exc is not None  # yetib bo'lmaydigan holat, mypy uchun
        raise last_exc

    async def create_lead(self, lead: Lead) -> str:
        body = {
            "name": lead.name,
            "phone": lead.phone,
            "igHandle": lead.ig_handle,
            "source": lead.source,
            "campaignId": lead.campaign_id,
            "temperature": lead.temperature,
            "stage": lead.stage,
            "score": lead.score,
            "assignedTo": lead.assigned_to,
        }
        resp = await self._request("POST", self._PATHS["leads"], json=body)
        return _extract_id(resp.json())

    async def get_lead(self, lead_id: str) -> Lead | None:
        path = self._PATHS["lead"].format(id=lead_id)
        try:
            resp = await self._request("GET", path)
        except CRMError as exc:
            if "404" in str(exc):
                return None
            raise
        data = _extract_record(resp.json())
        return _lead_from_dict(data) if data else None

    async def update_stage(self, lead_id: str, stage: str) -> None:
        path = self._PATHS["lead"].format(id=lead_id)
        await self._request("PATCH", path, json={"stage": stage})

    async def update_lead_score(self, lead_id: str, temperature: str, score: float) -> None:
        path = self._PATHS["lead"].format(id=lead_id)
        await self._request("PATCH", path, json={"temperature": temperature, "score": score})

    async def assign_lead(self, lead_id: str, staff_id: str) -> None:
        path = self._PATHS["lead"].format(id=lead_id)
        await self._request("PATCH", path, json={"assignedTo": staff_id})

    async def create_task(
        self, staff_id: str, title: str, due_at: str, lead_id: str | None
    ) -> str:
        body = {"title": title, "dueAt": due_at, "assigneeId": staff_id, "leadId": lead_id}
        resp = await self._request("POST", self._PATHS["tasks"], json=body)
        return _extract_id(resp.json())

    async def complete_task(self, task_id: str) -> None:
        path = self._PATHS["task"].format(id=task_id)
        await self._request("PATCH", path, json={"status": "done"})

    async def list_overdue_tasks(self) -> list[dict]:
        now = datetime.now(UTC).isoformat()
        # filtr sintaksisi TAXMIN (Twenty REST "filter" query parametri)
        resp = await self._request(
            "GET", self._PATHS["tasks"], params={"filter": f"dueAt[lt]:{now},status[eq]:open"}
        )
        return _extract_list(resp.json())

    async def list_open_tasks(self, staff_id: str) -> list[dict]:
        resp = await self._request(
            "GET",
            self._PATHS["tasks"],
            params={"filter": f"assigneeId[eq]:{staff_id},status[eq]:open"},
        )
        return _extract_list(resp.json())

    async def campaign_stats(self, campaign_id: str) -> dict:
        # Twenty'da alohida aggregate endpoint bo'lishi mumkin — hozircha lidlarni o'zimiz
        # sanaymiz (TAXMIN, kam lid sonida yetarli, ko'p bo'lsa pagination kerak bo'ladi).
        resp = await self._request(
            "GET", self._PATHS["leads"], params={"filter": f"campaignId[eq]:{campaign_id}"}
        )
        leads = _extract_list(resp.json())
        return {
            "campaign_id": campaign_id,
            "lead_count": len(leads),
            "deal_count": sum(1 for lead in leads if lead.get("stage") == "deal"),
        }

    async def log_activity(self, lead_id: str, text: str) -> None:
        # Twenty "notes"/timeline API shakli TAXMIN
        await self._request("POST", self._PATHS["notes"], json={"body": text, "leadId": lead_id})


# ---------------------------------------------------------------- InMemory (testlar/dev)


class InMemoryCRM:
    """Xotiradagi CRM — ``CRM`` Protocol bilan bir xil interfeys, tarmoqqa chiqmaydi.

    ``settings.crm_provider == "memory"`` bo'lganda ``get_crm()`` shuni qaytaradi.
    """

    def __init__(self) -> None:
        self._leads: dict[str, Lead] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._activity: dict[str, list[str]] = {}
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq}"

    async def create_lead(self, lead: Lead) -> str:
        lead_id = lead.id or self._next_id("lead")
        self._leads[lead_id] = replace(lead, id=lead_id)
        return lead_id

    async def get_lead(self, lead_id: str) -> Lead | None:
        return self._leads.get(lead_id)

    async def update_stage(self, lead_id: str, stage: str) -> None:
        if lead_id in self._leads:
            self._leads[lead_id] = replace(self._leads[lead_id], stage=stage)

    async def update_lead_score(self, lead_id: str, temperature: str, score: float) -> None:
        if lead_id in self._leads:
            self._leads[lead_id] = replace(
                self._leads[lead_id], temperature=temperature, score=score
            )

    async def assign_lead(self, lead_id: str, staff_id: str) -> None:
        if lead_id in self._leads:
            self._leads[lead_id] = replace(self._leads[lead_id], assigned_to=staff_id)

    async def create_task(
        self, staff_id: str, title: str, due_at: str, lead_id: str | None
    ) -> str:
        task_id = self._next_id("task")
        self._tasks[task_id] = {
            "id": task_id,
            "staff_id": staff_id,
            "title": title,
            "due_at": due_at,
            "lead_id": lead_id,
            "status": "open",
        }
        return task_id

    async def complete_task(self, task_id: str) -> None:
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = "done"

    async def list_overdue_tasks(self) -> list[dict]:
        now = datetime.now(UTC).isoformat()
        return [
            t
            for t in self._tasks.values()
            if t["status"] == "open" and t["due_at"] and t["due_at"] < now
        ]

    async def list_open_tasks(self, staff_id: str) -> list[dict]:
        return [
            t
            for t in self._tasks.values()
            if t["status"] == "open" and t["staff_id"] == staff_id
        ]

    async def campaign_stats(self, campaign_id: str) -> dict:
        leads = [lead for lead in self._leads.values() if lead.campaign_id == campaign_id]
        return {
            "campaign_id": campaign_id,
            "lead_count": len(leads),
            "deal_count": sum(1 for lead in leads if lead.stage == "deal"),
        }

    async def log_activity(self, lead_id: str, text: str) -> None:
        self._activity.setdefault(lead_id, []).append(text)


# ---------------------------------------------------------------- factory


_crm_singleton: CRM | None = None


def get_crm() -> CRM:
    """``settings.crm_provider`` bo'yicha CRM namunasini qaytaradi va keshlaydi (modul
    darajasida bitta namuna — ``jarvis_routes.get_deps`` shuni ishlatadi).

    Testlarda odatda bevosita ``InMemoryCRM()`` yoki ``TwentyCRM(transport=...)`` yaratiladi,
    bu factory faqat HTTP marshrut qatlami uchun.
    """
    global _crm_singleton
    if _crm_singleton is None:
        _crm_singleton = TwentyCRM() if settings.crm_provider == "twenty" else InMemoryCRM()
    return _crm_singleton
