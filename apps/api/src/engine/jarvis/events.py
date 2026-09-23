"""Jarvis event turlari (docs/06-jarvis-crm.md "Event manbalari").

Hozircha LangGraph ishlatilmaydi (5.5 keyinroq supervisor grafini shu interfeys atrofida
o'raydi) — bu yerda faqat oddiy ``TypedDict``'lar, hujjat va IDE uchun. ``supervisor.handle_event``
haqiqiy kirishda oddiy ``dict`` qabul qiladi (event manbalari — HTTP JSON, cron, webhook —
har xil bo'lgani uchun qattiq validatsiya qilinmaydi, faqat ``type`` maydoni tekshiriladi).
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

EventType = Literal[
    "lead.created",
    "lead.reply",
    "task.overdue",
    "task.due_soon",
    "cron.daily_report",
    "owner.command",
    "staff.reply",
]


class BaseEvent(TypedDict, total=False):
    type: EventType
    workspace_id: str


class LeadCreatedEvent(BaseEvent):
    lead_id: str
    source: str
    name: str | None
    phone: str | None
    conversation_id: int | None
    text: str


class LeadReplyEvent(BaseEvent):
    lead_id: str
    conversation_id: int | None
    text: str


class TaskOverdueEvent(BaseEvent):
    """``task.overdue`` va ``task.due_soon`` ikkalasi ham shu shaklda: ``escalate=True``
    bo'lsa ega'ga eskalatsiya, aks holda xodimga eslatma (docs/04 "Eskalatsiya qoidalari").
    """

    task_id: str
    escalate: bool


TaskDueSoonEvent = TaskOverdueEvent


class CronDailyReportEvent(BaseEvent):
    company: str


class OwnerCommandEvent(BaseEvent):
    text: str
    chat_id: int


class StaffReplyEvent(BaseEvent):
    staff_id: str
    task_id: str | None
    text: str
    chat_id: int


# supervisor.handle_event ning haqiqiy kirish turi — yuqoridagi TypedDict'lar faqat shakl uchun.
Event = dict[str, Any]
