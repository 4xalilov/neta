"""TaskManager: vazifa yaratish (muddat — ega buyrug'idan yoki SLA), eslatma, eskalatsiya.

Bu modul bizning Postgres ``task`` jadvali (``engine.models.crm.Task``) bilan ishlaydi —
davriy eslatma/eskalatsiya tekshiruvi (``reminders_due``/``escalations_due``) uchun har safar
CRM API'ga murojaat qilish shart emas. Vazifa Twenty'da ham ko'rinishi uchun supervisor uni
``crm.create_task`` bilan alohida yozadi (docs/07 "Twenty — asosiy manba"); muddat mantiqi esa
shu yerda, DB'da (docs/06 "Deadline mantiqi", docs/04 "Eskalatsiya qoidalari").
"""
from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.jarvis.policy import DEFAULT_SLA_HOURS
from engine.models.crm import Task

# docs/04 "Eskalatsiya qoidalari": "Vazifa muddati o'tdi -> 1 soatdan keyin xodimga eslatma;
# 2-marta o'tsa -> egaga xabar."
REMINDER_INTERVAL_HOURS = 1
ESCALATE_AFTER_REMINDERS = 2


def sla_hours_for(temperature: str | None) -> int:
    """docs/06 "Deadline mantiqi" 2-band: issiq 2 soat, iliq 24 soat, sovuq 3 kun."""
    return DEFAULT_SLA_HOURS.get(temperature or "warm", DEFAULT_SLA_HOURS["warm"])


def default_deadline(now: datetime, temperature: str | None = None) -> datetime:
    return now + timedelta(hours=sla_hours_for(temperature))


_DEADLINE_RE = re.compile(r"(bugun|ertaga)?\s*(\d{1,2})[:.](\d{2})", re.IGNORECASE)


def parse_deadline_from_text(
    text: str, now: datetime, temperature: str | None = None
) -> datetime:
    """Ega/xodim matnidan muddatni o'qishga urinadi (masalan "bugun 18:00", "ertaga 10:00").

    Topolmasa — SLA bo'yicha standart muddat (docs/06 "Deadline mantiqi" 1-2 band: "Ega
    buyruqda muddat aytdi -> shu. Aytmadi -> workspace.default_sla"). Murakkab holatlar
    (hafta kuni, "2 soatdan keyin" kabi nisbiy vaqt) hali qo'llab-quvvatlanmaydi — TODO.
    """
    m = _DEADLINE_RE.search(text.lower())
    if not m:
        return default_deadline(now, temperature)

    day_word, hh, mm = m.groups()
    base = now.date()
    if day_word == "ertaga":
        base = base + timedelta(days=1)
    try:
        dt = datetime.combine(base, datetime.min.time()).replace(
            hour=int(hh), minute=int(mm), tzinfo=now.tzinfo or UTC
        )
    except ValueError:
        return default_deadline(now, temperature)

    if day_word is None and dt < now:
        dt = dt + timedelta(days=1)
    return dt


def _overdue_hours(now: datetime, due_at: datetime) -> float:
    """sqlite'da ``DateTime(timezone=True)`` tzinfo'ni yo'qotishi mumkin — ikkalasini ham
    aware qilib solishtiramiz (naiv bo'lsa UTC deb qabul qilinadi)."""
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return (now - due_at).total_seconds() / 3600


async def create_task(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    staff_id: uuid.UUID,
    title: str,
    due_at: datetime,
    lead_id: uuid.UUID | None = None,
) -> Task:
    task = Task(
        workspace_id=workspace_id,
        staff_id=staff_id,
        lead_id=lead_id,
        title=title,
        due_at=due_at,
        status="open",
    )
    session.add(task)
    await session.flush()
    return task


async def complete_task(session: AsyncSession, task_id: uuid.UUID) -> Task | None:
    task = await session.get(Task, task_id)
    if task is not None:
        task.status = "done"
        await session.flush()
    return task


async def _open_tasks_with_deadline(session: AsyncSession) -> list[Task]:
    result = await session.scalars(
        select(Task).where(
            Task.status == "open",
            Task.due_at.is_not(None),
            Task.escalated_at.is_(None),
        )
    )
    return list(result)


async def reminders_due(session: AsyncSession, now: datetime) -> list[Task]:
    """1 soatdan (yoki har keyingi 1 soatlik intervaldan) keyin eslatma kerak bo'lgan,
    lekin hali eskalatsiya chegarasiga (2-eslatma) yetmagan ochiq vazifalar."""
    tasks = await _open_tasks_with_deadline(session)
    due = []
    for task in tasks:
        overdue_h = _overdue_hours(now, task.due_at)
        needs_next_reminder = overdue_h >= REMINDER_INTERVAL_HOURS * (task.reminders_sent + 1)
        if needs_next_reminder and task.reminders_sent < ESCALATE_AFTER_REMINDERS:
            due.append(task)
    return due


async def escalations_due(session: AsyncSession, now: datetime) -> list[Task]:
    """2-marta eslatma o'tgan (docs/04: "2-marta o'tsa -> egaga xabar") ochiq vazifalar."""
    tasks = await _open_tasks_with_deadline(session)
    due = []
    for task in tasks:
        overdue_h = _overdue_hours(now, task.due_at)
        if (
            task.reminders_sent >= ESCALATE_AFTER_REMINDERS
            and overdue_h >= REMINDER_INTERVAL_HOURS * ESCALATE_AFTER_REMINDERS
        ):
            due.append(task)
    return due


async def mark_reminded(session: AsyncSession, task: Task) -> None:
    task.reminders_sent += 1
    await session.flush()


async def mark_escalated(session: AsyncSession, task: Task, now: datetime) -> None:
    task.escalated_at = now
    await session.flush()
