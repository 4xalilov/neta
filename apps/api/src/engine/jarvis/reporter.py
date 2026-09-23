"""Reporter: kunlik hisobot matni (docs/06-jarvis-crm.md namunasi bo'yicha, o'zbek tilida).

Raqamlar bizning Postgres'dan (``lead``/``deal``/``task`` — docs/07 hozircha bu jadvallar
ham mavjud, TODO: Twenty asosiy manbaga o'tganda ``campaign_stats``/``crm`` dan olinadi) +
xarajat ``engine.cost_tracker.summary`` orqali. Matn hozircha shablon bilan (deterministik,
testlanishi oson) — ``agents/prompts/jarvis_reporter.md`` uslub/ohangni hujjatlaydi va
keyingi bosqichda LLM bilan tabiiyroq qayta yozish uchun tayyor.

TTS ixtiyoriy: ``engine.integrations.tts`` ni ``getattr`` orqali chaqiramiz, shunda audio
kutubxonalar o'rnatilmagan test muhitida ham modul import qilinaveradi.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine import cost_tracker
from engine.models.crm import Deal, Lead, Task

logger = logging.getLogger(__name__)


@dataclass
class DailyReportResult:
    text: str
    audio: bytes | None = None
    audio_format: str | None = None


async def _counts_for_day(
    session: AsyncSession, workspace_id: uuid.UUID, day: date_
) -> dict:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)

    leads_total = (
        await session.scalar(
            select(func.count(Lead.id)).where(
                Lead.workspace_id == workspace_id,
                Lead.created_at >= start,
                Lead.created_at < end,
            )
        )
        or 0
    )
    leads_hot = (
        await session.scalar(
            select(func.count(Lead.id)).where(
                Lead.workspace_id == workspace_id,
                Lead.created_at >= start,
                Lead.created_at < end,
                Lead.temperature == "hot",
            )
        )
        or 0
    )
    deals = (
        await session.scalar(
            select(func.count(Deal.id))
            .join(Lead, Deal.lead_id == Lead.id)
            .where(
                Lead.workspace_id == workspace_id,
                Deal.closed_at >= start,
                Deal.closed_at < end,
                Deal.status == "won",
            )
        )
        or 0
    )
    deals_amount = (
        await session.scalar(
            select(func.coalesce(func.sum(Deal.amount), 0.0))
            .join(Lead, Deal.lead_id == Lead.id)
            .where(
                Lead.workspace_id == workspace_id,
                Deal.closed_at >= start,
                Deal.closed_at < end,
                Deal.status == "won",
            )
        )
        or 0.0
    )
    overdue_tasks = (
        await session.scalar(
            select(func.count(Task.id)).where(
                Task.workspace_id == workspace_id,
                Task.status == "open",
                Task.due_at.is_not(None),
                Task.due_at < datetime.now(UTC),
            )
        )
        or 0
    )

    return {
        "leads_total": leads_total,
        "leads_hot": leads_hot,
        "deals": deals,
        "deals_amount": deals_amount,
        "overdue_tasks": overdue_tasks,
    }


def _format_report_text(counts: dict) -> str:
    """docs/06 namunasi: "Kecha: 14 lid (Reels #12 dan 9), 3 sotuv 4.2 mln so'm, 2 vazifa
    muddati o'tdi (Aziz). Bugun issiq 6 lidga yozaymi?" — bu yerda kampaniya/xodim
    kesimisiz, umumiy sonlar bilan (TODO: campaign_stats/staff kesimi qo'shish)."""
    parts = [f"Kecha: {counts['leads_total']} lid"]
    if counts["leads_hot"]:
        parts[0] += f" ({counts['leads_hot']} issiq)"
    if counts["deals"]:
        amount_mln = counts["deals_amount"] / 1_000_000
        parts.append(f"{counts['deals']} sotuv {amount_mln:.1f} mln so'm")
    if counts["overdue_tasks"]:
        parts.append(f"{counts['overdue_tasks']} vazifa muddati o'tdi")

    text = ", ".join(parts) + "."
    if counts["leads_hot"]:
        text += f" Bugun issiq {counts['leads_hot']} lidga yozaymi?"
    return text


async def build_daily_report(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    company: str = "kompaniya",
    day: date_ | None = None,
    with_audio: bool = False,
) -> DailyReportResult:
    day = day or (datetime.now(UTC).date() - timedelta(days=1))
    counts = await _counts_for_day(session, workspace_id, day)
    # cost_tracker.summary hozircha faqat matnga chiqmaydi (docs/06 namunasida yo'q), lekin
    # kelajakda "xarajat/lid" ko'rsatkichi uchun tayyor turadi.
    cost_tracker.summary(str(workspace_id))
    text = _format_report_text(counts)

    audio: bytes | None = None
    audio_format: str | None = None
    if with_audio:
        try:
            from engine.integrations import tts as tts_module

            synthesize = getattr(tts_module, "synthesize", None)
            if synthesize is not None:
                result = await synthesize(
                    text, workspace_id=str(workspace_id), node="jarvis.reporter"
                )
                audio, audio_format = result.audio, result.format
        except Exception:
            logger.warning("reporter: TTS xato, faqat matn qaytarildi", exc_info=True)

    return DailyReportResult(text=text, audio=audio, audio_format=audio_format)
