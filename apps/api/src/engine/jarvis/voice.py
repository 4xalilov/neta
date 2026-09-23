"""Ovozli boshqaruv (roadmap 5.10): ega gapiradi → Jarvis tinglaydi, bajaradi, ovoz bilan javob beradi.

``handle_owner_utterance`` oqimi::

    audio? → stt.transcribe → owner_memory.remember(user) → intents.parse_intent
      → marshrut (quyida) → javob matni (docs/04: qisqa, raqam birinchi, "siz")
      → settings.voice_reply bo'lsa: tts.synthesize → audio.mp3_to_ogg_opus (Telegram voice)
      → owner_memory.remember(jarvis)

Marshrutlar:
- ``daily_report`` → ``reporter.build_daily_report`` (kecha yoki bugun).
- ``assign_task`` → ``supervisor.propose_action("assign_task")`` → ``task_manager.create_task``
  + xodimga ``notify(kind="task")`` (policy: autonomous).
- ``remind_staff`` → ``propose_action("remind_staff")`` (xodim aytilgan bo'lsa) yoki har
  kechikkan vazifa uchun ``supervisor.handle_event(task.overdue)``.
- ``approve`` / ``reject`` → ``supervisor.decide`` (id aytilmasa — oxirgi Jarvis javobidagi
  harakatlar, bo'lmasa eng yangi ``pending``); ``approve_all`` → ``supervisor.batch_approve``.
- ``message_lead`` / ``call_lead`` → ``propose_action`` — POLICY GATE: ``requires_approval``
  bo'lgani uchun ``pending`` + egaga ``notify(kind="approval")``; bu yerda HECH QACHON
  to'g'ridan-to'g'ri bajarilmaydi.
- ``query_leads`` / ``query_tasks`` → DB hisoblari → qisqa raqamli javob.
- ``create_brief`` → ``VoiceReply.enqueue_brief`` (API qatlami arq ``run_brief`` qo'yadi).
- ``select_workspace`` → faol workspace almashadi (``VoiceReply.workspace_id`` + xotirada).
- ``update_settings`` → ``brand_profile`` patch (pronoun/voice/register).
- ``unknown`` / past ishonch / yetishmayotgan ma'lumot → ``clarify_question``.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine import cost_tracker
from engine.integrations import audio as audio_mod
from engine.integrations import stt, tts
from engine.jarvis import owner_memory, reporter, supervisor, task_manager
from engine.jarvis.deps import JarvisDeps
from engine.jarvis.intents import (
    GENERIC_CLARIFY,
    Intent,
    OwnerContext,
    parse_intent,
)
from engine.jarvis.intents import _zone as zone_for
from engine.models import (
    BrandProfile,
    JarvisAction,
    Lead,
    OwnerMemory,
    Staff,
    Task,
    Workspace,
)
from engine.settings import settings
from engine.uz.normalize import MONTHS

logger = logging.getLogger(__name__)

MAX_LEADS_PER_COMMAND = 20
VOICE_MAP = {"madina": "uz-UZ-MadinaNeural", "sardor": "uz-UZ-SardorNeural"}
TEMPERATURE_UZ = {"hot": "issiq", "warm": "iliq", "cold": "sovuq"}

NO_WORKSPACE_REPLY = "Avval botda /start bosing — workspace yaratilsin, keyin buyruq bering."
STT_FAILED_REPLY = "Ovozli xabarni o'qiy olmadim. Qaytadan yuboring yoki yozib yuboring."
EMPTY_TRANSCRIPT_REPLY = "Ovozda gap eshitilmadi. Qaytadan aytib bera olasizmi?"


@dataclass
class VoiceReply:
    transcript: str
    intent: Intent
    reply_text: str
    reply_audio: bytes | None = None
    reply_audio_fmt: str | None = None  # "ogg" (voice note) | "mp3"/"wav" (ffmpeg yo'q)
    actions: list[dict[str, Any]] = field(default_factory=list)
    needs_confirmation: bool = False
    cost_usd: float = 0.0
    workspace_id: str | None = None  # javobdan keyingi faol workspace (select_workspace)
    enqueue_brief: str | None = None  # create_brief: API qatlami run_brief qo'yadi
    stt_provider: str | None = None

    @property
    def clarify(self) -> bool:
        return self.intent.needs_clarification


@dataclass
class _Outcome:
    reply_text: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    needs_confirmation: bool = False
    memory: dict[str, Any] = field(default_factory=dict)
    enqueue_brief: str | None = None
    workspace_id: str | None = None


@dataclass
class _Env:
    deps: JarvisDeps
    ctx: OwnerContext
    ws: Workspace
    brand: dict[str, Any]
    chat_id: int


# ---------------------------------------------------------------- yordamchilar


def _uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def fmt_due(due: datetime, now: datetime, tz: str) -> str:
    """"bugun 15:00" / "ertaga 15:00" / "25-sentyabr 18:00" (workspace vaqti bo'yicha)."""
    zone = zone_for(tz)
    local = _aware(due).astimezone(zone)
    today = _aware(now).astimezone(zone).date()
    hhmm = local.strftime("%H:%M")
    delta = (local.date() - today).days
    if delta == 0:
        return f"bugun {hhmm}"
    if delta == 1:
        return f"ertaga {hhmm}"
    if delta == 2:
        return f"indinga {hhmm}"
    return f"{local.day}-{MONTHS[local.month - 1]} {hhmm}"


def _action_dict(action: JarvisAction) -> dict[str, Any]:
    return {"id": str(action.id), "type": action.type, "status": action.status,
            "level": str(action.level)}


async def _latest_brand(session: AsyncSession, ws_id: uuid.UUID) -> BrandProfile | None:
    return (await session.execute(
        select(BrandProfile).where(BrandProfile.workspace_id == ws_id)
        .order_by(BrandProfile.created_at.desc()).limit(1)
    )).scalar_one_or_none()


async def _resolve_workspace(
    session: AsyncSession, chat_id: int, workspace_id: Any, history: list[dict]
) -> Workspace | None:
    ws_uuid = _uuid(workspace_id)
    if ws_uuid is not None:
        return await session.get(Workspace, ws_uuid)
    for turn in reversed(history):  # select_workspace natijasi xotirada
        active = _uuid(turn.get("workspace_id")) if turn.get("role") == "jarvis" else None
        if active is not None:
            ws = await session.get(Workspace, active)
            if ws is not None:
                return ws
    if chat_id:
        return (await session.execute(
            select(Workspace).where(Workspace.owner_tg_id == chat_id)
            .order_by(Workspace.created_at).limit(1)
        )).scalar_one_or_none()
    return None


def _history_turns(rows: list) -> list[dict[str, Any]]:
    turns = owner_memory.as_prompt_turns(rows)
    for row, turn in zip(rows, turns):
        data = row.intent_json or {}
        for key in ("lead_ids", "workspace_id"):
            if data.get(key):
                turn[key] = data[key]
    return turns


async def _build_context(
    session: AsyncSession, *, ws: Workspace | None, chat_id: int, now: datetime,
    history: list[dict[str, Any]],
) -> OwnerContext:
    ctx = OwnerContext(now=now, history=history)
    if ws is None:
        return ctx
    ctx.workspace_id = str(ws.id)
    ctx.timezone = ws.timezone or ctx.timezone
    ctx.company = ws.name
    staff = await session.scalars(select(Staff).where(Staff.workspace_id == ws.id))
    ctx.staff = [(str(s.id), s.name) for s in staff]
    leads = await session.scalars(
        select(Lead).where(Lead.workspace_id == ws.id, Lead.name.is_not(None))
        .order_by(Lead.created_at.desc()).limit(50)
    )
    ctx.leads = [(str(ld.id), ld.name or "") for ld in leads]
    owners = {x for x in (ws.owner_tg_id, chat_id) if x}
    if owners:
        rows = await session.scalars(
            select(Workspace).where(Workspace.owner_tg_id.in_(owners))
            .order_by(Workspace.created_at)
        )
        ctx.workspaces = [(str(w.id), w.name) for w in rows]
    if not any(wid == str(ws.id) for wid, _ in ctx.workspaces):
        ctx.workspaces.insert(0, (str(ws.id), ws.name))
    pending = await session.scalars(
        select(JarvisAction).where(JarvisAction.workspace_id == ws.id,
                                   JarvisAction.status == "pending")
        .order_by(JarvisAction.created_at.desc()).limit(10)
    )
    ctx.pending = [
        {"id": str(a.id), "type": a.type,
         "summary": (a.payload or {}).get("description") or (a.payload or {}).get("name")}
        for a in pending
    ]
    return ctx


# ---------------------------------------------------------------- marshrutlar


async def _route_daily_report(env: _Env, intent: Intent) -> _Outcome:
    zone = zone_for(env.ctx.timezone)
    today = _aware(env.ctx.now).astimezone(zone).date()
    today_mode = intent.entities.period == "today"
    day = today if today_mode else today - timedelta(days=1)
    async with env.deps.session_factory() as session:
        report = await reporter.build_daily_report(
            session, workspace_id=env.ws.id, company=env.ws.name, day=day
        )
        pending = await session.scalar(
            select(func.count(JarvisAction.id)).where(
                JarvisAction.workspace_id == env.ws.id, JarvisAction.status == "pending")
        ) or 0
    text = report.text
    if today_mode:
        text = text.replace("Kecha:", "Bugun:", 1).replace(" Bugun issiq", " Issiq", 1)
    if pending:
        text += f" Tasdiq kutmoqda: {pending} ta."
    return _Outcome(text, actions=[{"type": "daily_report", "day": day.isoformat()}])


async def _route_assign_task(env: _Env, intent: Intent) -> _Outcome:
    ents = intent.entities
    staff_uuid = _uuid(ents.staff_id)
    async with env.deps.session_factory() as session:
        staff = await session.get(Staff, staff_uuid) if staff_uuid else None
    if staff is None:
        return _Outcome("Qaysi xodimga topshiray? Ismini ayting.")
    now = env.ctx.now
    due = datetime.fromisoformat(ents.due_at) if ents.due_at else task_manager.default_deadline(
        _aware(now))
    due_utc = _aware(due).astimezone(UTC)
    title = ents.task_title or intent.text
    due_label = fmt_due(due_utc, now, env.ctx.timezone)
    payload = {"staff_id": str(staff.id), "staff_name": staff.name, "title": title,
               "due_at": due_utc.isoformat(), "source": "owner.voice",
               "description": f"{staff.name}: «{title}», {due_label} gacha"}
    created: dict[str, str] = {}

    async def execute(session: AsyncSession) -> None:
        task = await task_manager.create_task(
            session, workspace_id=env.ws.id, staff_id=staff.id, title=title, due_at=due_utc,
        )
        created["task_id"] = str(task.id)
        try:  # Twenty'da ham ko'rinsin (docs/07); CRM xatosi vazifani to'xtatmaydi
            await env.deps.crm.create_task(str(staff.id), title, due_utc.isoformat(), None)
        except Exception:
            logger.warning("voice: crm.create_task xato", exc_info=True)
        await env.deps.notify(
            chat_id=staff.tg_id or str(staff.id), kind="task",
            payload={"task_id": str(task.id), "title": title, "due_at": due_utc.isoformat(),
                     "due": due_label, "staff_name": staff.name,
                     "workspace_id": str(env.ws.id)},
        )

    action = await supervisor.propose_action(
        env.deps, workspace_id=env.ws.id, action_type="assign_task", payload=payload,
        execute=execute,
    )
    act = {**_action_dict(action), **created}
    if action.status == "executed":
        reply = f"{staff.name}ga vazifa berildi: «{title}», muddat {due_label}. Xabar yubordim."
        return _Outcome(reply, actions=[act], memory={"staff_name": staff.name})
    reply = f"{staff.name}ga «{title}» vazifasi tasdiqingizni kutmoqda."
    return _Outcome(reply, actions=[act], needs_confirmation=True,
                    memory={"staff_name": staff.name, "action_ids": [act["id"]]})


async def _route_remind_staff(env: _Env, intent: Intent) -> _Outcome:
    deps, ws = env.deps, env.ws
    now = _aware(env.ctx.now)
    staff_uuid = _uuid(intent.entities.staff_id)
    if staff_uuid is None:  # xodim aytilmagan — muddati o'tgan hamma vazifalar
        async with deps.session_factory() as session:
            tasks = list(await session.scalars(
                select(Task).where(Task.workspace_id == ws.id, Task.status == "open",
                                   Task.due_at.is_not(None))
            ))
        overdue = [t for t in tasks if _aware(t.due_at) < now]
        if not overdue:
            return _Outcome("Muddati o'tgan vazifa yo'q — eslatish shart emas.")
        actions = []
        for t in overdue:
            action = await supervisor.handle_event(
                {"type": "task.overdue", "task_id": str(t.id), "escalate": False}, deps
            )
            if action is not None:
                actions.append(_action_dict(action))
        return _Outcome(f"{len(overdue)} ta kechikkan vazifa bo'yicha xodimlarga eslatdim.",
                        actions=actions)

    async with deps.session_factory() as session:
        staff = await session.get(Staff, staff_uuid)
        tasks = list(await session.scalars(
            select(Task).where(Task.staff_id == staff_uuid, Task.status == "open")
            .order_by(Task.due_at)
        ))
    if staff is None:
        return _Outcome("Bu xodim topilmadi.")
    task_ids = [str(t.id) for t in tasks]
    n_overdue = sum(1 for t in tasks if t.due_at and _aware(t.due_at) < now)
    note = intent.entities.task_title
    payload = {"staff_id": str(staff.id), "staff_name": staff.name, "task_ids": task_ids,
               "titles": [t.title for t in tasks][:5], "note": note, "source": "owner.voice",
               # supervisor'ning ``reminder`` payload'i bilan mos kalit (bot bitta ekran)
               "title": ", ".join(t.title for t in tasks[:3]) or note or ""}

    async def execute(session: AsyncSession) -> None:
        for tid in task_ids:
            t = await session.get(Task, uuid.UUID(tid))
            if t is not None:
                await task_manager.mark_reminded(session, t)
        await deps.notify(chat_id=staff.tg_id or str(staff.id), kind="reminder", payload=payload)

    action = await supervisor.propose_action(
        deps, workspace_id=ws.id, action_type="remind_staff", payload=payload, execute=execute,
    )
    if tasks:
        reply = f"{staff.name}ga eslatdim: {len(tasks)} ta ochiq vazifa"
        reply += f", {n_overdue} tasi muddati o'tgan." if n_overdue else "."
    else:
        reply = f"{staff.name}ga eslatma yubordim" + (f": «{note}»." if note else ".")
    return _Outcome(reply, actions=[_action_dict(action)], memory={"staff_name": staff.name})


def _last_jarvis_turn(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    for turn in reversed(history):
        if turn.get("role") == "jarvis":
            return turn
    return None


async def _pending_targets(env: _Env, intent: Intent) -> list[uuid.UUID]:
    """Qaysi harakat(lar)ga "ha"/"yo'q": aniq id → oxirgi Jarvis javobidagilar → eng yangisi."""
    async with env.deps.session_factory() as session:
        async def still_pending(ids: list[Any]) -> list[uuid.UUID]:
            out = []
            for raw in ids:
                aid = _uuid(raw)
                action = await session.get(JarvisAction, aid) if aid else None
                if (action is not None and action.status == "pending"
                        and action.workspace_id == env.ws.id):
                    out.append(action.id)
            return out

        if intent.entities.action_id:
            found = await still_pending([intent.entities.action_id])
            if found:
                return found
        last = _last_jarvis_turn(env.ctx.history)
        if last and last.get("action_ids"):
            found = await still_pending(list(last["action_ids"]))
            if found:
                return found
        latest = (await session.execute(
            select(JarvisAction.id).where(JarvisAction.workspace_id == env.ws.id,
                                          JarvisAction.status == "pending")
            .order_by(JarvisAction.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        return [latest] if latest else []


async def _route_decision(env: _Env, intent: Intent) -> _Outcome:
    decision = "yes" if intent.intent == "approve" else "no"
    targets = await _pending_targets(env, intent)
    if not targets:
        return _Outcome("Tasdiq kutayotgan harakat yo'q.")
    actions = [_action_dict(await supervisor.decide(env.deps, aid, decision)) for aid in targets]
    n = len(actions)
    reply = (f"Tasdiqlandi: {n} ta harakat bajarildi." if decision == "yes"
             else f"Bekor qilindi: {n} ta harakat.")
    return _Outcome(reply, actions=actions)


async def _route_approve_all(env: _Env, intent: Intent) -> _Outcome:
    done = await supervisor.batch_approve(env.deps, env.ws.id)
    if not done:
        return _Outcome("Tasdiq kutayotgan harakat yo'q.")
    return _Outcome(f"Hammasi tasdiqlandi: {len(done)} ta harakat bajarildi.",
                    actions=[_action_dict(a) for a in done])


async def _target_leads(env: _Env, intent: Intent) -> list[Lead]:
    ents = intent.entities
    ids = [x for x in (_uuid(i) for i in ([ents.lead_id] if ents.lead_id else ents.lead_ids))
           if x]
    async with env.deps.session_factory() as session:
        if ids:
            rows = await session.scalars(
                select(Lead).where(Lead.workspace_id == env.ws.id, Lead.id.in_(ids)))
            return list(rows)
        if ents.temperature:
            limit = min(ents.count or MAX_LEADS_PER_COMMAND, MAX_LEADS_PER_COMMAND)
            rows = await session.scalars(
                select(Lead).where(Lead.workspace_id == env.ws.id,
                                   Lead.temperature == ents.temperature,
                                   Lead.stage.not_in(("deal", "lost")))
                .order_by(Lead.score.desc(), Lead.created_at.desc()).limit(limit)
            )
            return list(rows)
    return []


async def _route_lead_action(env: _Env, intent: Intent) -> _Outcome:
    """message_lead / call_lead — HAR DOIM ``propose_action`` (policy gate) orqali."""
    action_type = intent.intent
    leads = await _target_leads(env, intent)
    ents = intent.entities
    if not leads:
        if ents.temperature:
            return _Outcome(f"{TEMPERATURE_UZ[ents.temperature].capitalize()} lid topilmadi.")
        return _Outcome("Bu lid topilmadi. Ismini aniqroq ayting.")

    verb = "xabar yozaymi" if action_type == "message_lead" else "qo'ng'iroq qilaymi"
    actions: list[dict[str, Any]] = []
    pending_ids: list[str] = []
    executor = supervisor._APPROVAL_EXECUTORS.get(action_type)
    for lead in leads:
        label = lead.name or lead.phone or "lid"
        temp = TEMPERATURE_UZ.get(lead.temperature or "", "")
        payload = {"lead_id": str(lead.id), "name": lead.name, "phone": lead.phone,
                   "temperature": lead.temperature, "text": ents.message_text,
                   "source": "owner.voice",
                   "description": f"{label}{f' ({temp} lid)' if temp else ''}ga {verb}?"}

        async def execute(session: AsyncSession, _payload: dict = payload) -> None:
            # Faqat policy ``autonomous`` bo'lsa chaqiriladi (docs/06: 2 haftadan keyin).
            if executor is not None:
                await executor(env.deps, session, _payload)

        action = await supervisor.propose_action(
            env.deps, workspace_id=env.ws.id, action_type=action_type, payload=payload,
            execute=execute,
        )
        actions.append(_action_dict(action))
        if action.status == "pending":
            pending_ids.append(str(action.id))

    memory = {"lead_ids": [str(ld.id) for ld in leads],
              "lead_names": [ld.name for ld in leads if ld.name][:10],
              "action_ids": pending_ids}
    n = len(leads)
    if ents.temperature and not (ents.lead_id or ents.lead_ids):
        who = f"{n} ta {TEMPERATURE_UZ[ents.temperature]} lid"
    else:
        who = (leads[0].name or "lid") if n == 1 else f"{n} ta lid"
    what = "ga xabar" if action_type == "message_lead" else "ga qo'ng'iroq"
    if pending_ids:
        reply = (f"{who}{what} tayyor. Tasdiqlaysizmi? «Ha» yoki «hammasiga ha» deng."
                 if n > 1 else f"{who}{what} tayyor. Tasdiqlaysizmi?")
        return _Outcome(reply, actions=actions, needs_confirmation=True, memory=memory)
    return _Outcome(f"{who}{what} yuborildi.", actions=actions, memory=memory)


def _period_bounds(period: str | None, now: datetime, tz: str) -> tuple[datetime, datetime, str]:
    zone = zone_for(tz)
    local_today = _aware(now).astimezone(zone).date()
    start_day = local_today
    end_day = local_today + timedelta(days=1)
    label = "Bugun"
    if period == "yesterday":
        start_day, end_day, label = local_today - timedelta(days=1), local_today, "Kecha"
    elif period == "week":
        start_day, label = local_today - timedelta(days=6), "7 kunda"

    def to_utc(d: Any) -> datetime:
        return datetime(d.year, d.month, d.day, tzinfo=zone).astimezone(UTC)

    return to_utc(start_day), to_utc(end_day), label


async def _route_query_leads(env: _Env, intent: Intent) -> _Outcome:
    start, end, label = _period_bounds(intent.entities.period, env.ctx.now, env.ctx.timezone)
    async with env.deps.session_factory() as session:
        rows = (await session.execute(
            select(Lead.temperature, func.count(Lead.id))
            .where(Lead.workspace_id == env.ws.id, Lead.created_at >= start,
                   Lead.created_at < end)
            .group_by(Lead.temperature)
        )).all()
    by_temp = {t or "": n for t, n in rows}
    total = sum(by_temp.values())
    temp = intent.entities.temperature
    if temp:
        n = by_temp.get(temp, 0)
        reply = f"{label} {n} ta {TEMPERATURE_UZ[temp]} lid (jami {total})."
    elif total == 0:
        reply = f"{label} lid yo'q."
    else:
        parts = [f"{by_temp[k]} {TEMPERATURE_UZ[k]}" for k in ("hot", "warm", "cold")
                 if by_temp.get(k)]
        reply = f"{label} {total} lid" + (f": {', '.join(parts)}." if parts else ".")
    return _Outcome(reply, actions=[{"type": "query_leads", "total": total, **by_temp}])


async def _route_query_tasks(env: _Env, intent: Intent) -> _Outcome:
    now = _aware(env.ctx.now)
    staff_uuid = _uuid(intent.entities.staff_id)
    stmt = select(Task, Staff.name).join(Staff, Task.staff_id == Staff.id).where(
        Task.workspace_id == env.ws.id, Task.status == "open")
    if staff_uuid:
        stmt = stmt.where(Task.staff_id == staff_uuid)
    async with env.deps.session_factory() as session:
        rows = (await session.execute(stmt)).all()
    total = len(rows)
    overdue_by: dict[str, int] = {}
    for task, name in rows:
        if task.due_at and _aware(task.due_at) < now:
            overdue_by[name] = overdue_by.get(name, 0) + 1
    overdue = sum(overdue_by.values())
    prefix = f"{intent.entities.staff_name}: " if staff_uuid else ""
    if total == 0:
        reply = f"{prefix}ochiq vazifa yo'q." if prefix else "Ochiq vazifa yo'q."
    else:
        reply = f"{prefix}{total} ochiq vazifa"
        if overdue:
            reply += f", {overdue} tasi muddati o'tgan"
            if not staff_uuid:
                worst = sorted(overdue_by.items(), key=lambda kv: -kv[1])[:3]
                reply += " (" + ", ".join(f"{n} {c}" for n, c in worst) + ")"
        reply += "."
    return _Outcome(reply, actions=[{"type": "query_tasks", "open": total, "overdue": overdue}])


async def _route_create_brief(env: _Env, intent: Intent) -> _Outcome:
    brief = intent.entities.brief_text or intent.text
    target_id = intent.entities.workspace_id or str(env.ws.id)
    name = intent.entities.workspace_name if intent.entities.workspace_id else env.ws.name
    reply = f"Brif qabul qilindi ({name}): «{brief}». Ssenariy tayyor bo'lgach yuboraman."
    return _Outcome(reply, actions=[{"type": "enqueue_brief", "workspace_id": target_id,
                                     "text": brief}],
                    enqueue_brief=brief, workspace_id=target_id,
                    memory={"workspace_id": target_id})


async def _route_schedule_post(env: _Env, intent: Intent) -> _Outcome:
    return _Outcome(
        "Nashrni rejalashtirish hozircha video tasdiqlash ekranida: «🕒 Rejalashtir» tugmasi."
    )


async def _route_select_workspace(env: _Env, intent: Intent) -> _Outcome:
    wid = intent.entities.workspace_id
    return _Outcome(f"Faol mijoz: {intent.entities.workspace_name}. Buyruqlar endi shu mijoz uchun.",
                    actions=[{"type": "select_workspace", "workspace_id": wid}],
                    workspace_id=wid, memory={"workspace_id": wid})


_SETTING_LABELS = {
    "pronoun": lambda v: f"endi «{v}» deb murojaat qilaman",
    "voice": lambda v: f"ovoz — {v.capitalize()}",
    "register": lambda v: "uslub — " + {"casual": "erkin", "neutral": "neytral",
                                         "formal": "rasmiy"}.get(v, v),
}


async def _route_update_settings(env: _Env, intent: Intent) -> _Outcome:
    key, value = intent.entities.setting_key, intent.entities.setting_value
    if not key or not value:
        return _Outcome(intent.clarify_question or GENERIC_CLARIFY)
    fields: dict[str, Any] = {key: value}
    if key == "pronoun":
        fields["address_form"] = value
    if key == "voice" and value in VOICE_MAP:
        fields["tts_voice"] = VOICE_MAP[value]
    async with env.deps.session_factory() as session:
        bp = await _latest_brand(session, env.ws.id)
        if bp is None:
            session.add(BrandProfile(workspace_id=env.ws.id, data=fields))
        else:
            bp.data = {**(bp.data or {}), **fields}  # yangi dict — JSON o'zgarishi aniqlanadi
        await session.commit()
    env.brand.update(fields)
    return _Outcome(f"Sozlama saqlandi: {_SETTING_LABELS[key](value)}.",
                    actions=[{"type": "update_settings", key: value}])


async def _route_smalltalk(env: _Env, intent: Intent) -> _Outcome:
    hint = (intent.reply_hint or "").strip()
    if hint:
        return _Outcome(hint)
    return _Outcome(f"Men Jarvis, {env.ws.name} virtual yordamchisi. Hisobot, vazifa yoki "
                    "lidlar bo'yicha buyruq bering.")


_ROUTES: dict[str, Callable[[_Env, Intent], Awaitable[_Outcome]]] = {
    "daily_report": _route_daily_report,
    "assign_task": _route_assign_task,
    "remind_staff": _route_remind_staff,
    "approve": _route_decision,
    "reject": _route_decision,
    "approve_all": _route_approve_all,
    "message_lead": _route_lead_action,
    "call_lead": _route_lead_action,
    "query_leads": _route_query_leads,
    "query_tasks": _route_query_tasks,
    "create_brief": _route_create_brief,
    "schedule_post": _route_schedule_post,
    "select_workspace": _route_select_workspace,
    "update_settings": _route_update_settings,
    "smalltalk": _route_smalltalk,
}


# ---------------------------------------------------------------- ovozli javob


async def synthesize_reply(text: str, *, workspace_id: str = "",
                           voice: str | None = None) -> tuple[bytes | None, str | None]:
    """Javob matni → Telegram voice (OGG/Opus). TTS yo'q → ``(None, None)``; ffmpeg yo'q →
    TTS'ning o'z formati (mp3/wav) — bot uni ``sendAudio`` bilan yuborishi mumkin."""
    if not text:
        return None, None
    try:
        res = await tts.synthesize(text, voice=voice, workspace_id=workspace_id,
                                   node="jarvis.voice")
    except Exception:
        logger.warning("voice: TTS ishlamadi, faqat matn qaytariladi", exc_info=True)
        return None, None
    try:
        return await audio_mod.mp3_to_ogg_opus(res.audio), "ogg"
    except audio_mod.AudioError:
        logger.warning("voice: ogg/opus'ga o'girib bo'lmadi (ffmpeg?)", exc_info=True)
        return res.audio, res.format


def _cost_since(t0: float, workspace_ids: set[str]) -> float:
    return round(sum(e["usd"] for e in list(cost_tracker.RECENT)
                     if e["ts"] >= t0 and e["workspace_id"] in workspace_ids), 6)


# ---------------------------------------------------------------- asosiy kirish


async def handle_owner_utterance(
    deps: JarvisDeps,
    *,
    chat_id: int,
    workspace_id: Any = None,
    text: str | None = None,
    audio: bytes | None = None,
    audio_fmt: str | None = None,
    now: datetime | None = None,
) -> VoiceReply:
    """Ega gapi (matn yoki ovoz) → bajarilgan harakatlar + javob (matn va ovoz)."""
    t0 = time.time()
    now = _aware(now or deps.now())
    chat_id = int(chat_id or 0)
    transcript = (text or "").strip()
    stt_provider: str | None = None
    ws_hint = str(workspace_id or "")

    if audio:
        try:
            res = await stt.transcribe(audio, audio_fmt, workspace_id=ws_hint)
            transcript, stt_provider = res.text, res.provider
        except Exception:
            logger.warning("voice: STT muvaffaqiyatsiz", exc_info=True)
            intent = Intent(intent="unknown", clarify_question=STT_FAILED_REPLY)
            return VoiceReply(transcript="", intent=intent, reply_text=STT_FAILED_REPLY,
                              cost_usd=_cost_since(t0, {ws_hint, ""}),
                              workspace_id=ws_hint or None)
    if not transcript:
        intent = Intent(intent="unknown", clarify_question=EMPTY_TRANSCRIPT_REPLY)
        return VoiceReply(transcript="", intent=intent, reply_text=EMPTY_TRANSCRIPT_REPLY,
                          stt_provider=stt_provider, cost_usd=_cost_since(t0, {ws_hint, ""}),
                          workspace_id=ws_hint or None)

    n_rows = max(settings.owner_memory_turns, 0) * 2  # 1 almashuv = ega + Jarvis
    async with deps.session_factory() as session:
        rows = await owner_memory.recent(session, chat_id, n_rows) if chat_id else []
        history = _history_turns(rows)
        ws = await _resolve_workspace(session, chat_id, workspace_id, history)
        ctx = await _build_context(session, ws=ws, chat_id=chat_id, now=now, history=history)
        bp = await _latest_brand(session, ws.id) if ws else None
        brand = dict(bp.data or {}) if bp else {}
        user_row = await owner_memory.remember(
            session, chat_id=chat_id, role="user", text=transcript,
            workspace_id=ws.id if ws else None,
        )
        user_row_id = user_row.id
        await session.commit()

    intent = await parse_intent(transcript, context=ctx)

    async with deps.session_factory() as session:
        row = await session.get(OwnerMemory, user_row_id)
        if row is not None:
            row.intent_json = {"intent": intent.intent, "confidence": intent.confidence,
                               "entities": intent.entities.model_dump(exclude_none=True,
                                                                      exclude_defaults=True)}
            await session.commit()

    if intent.needs_clarification:
        outcome = _Outcome(intent.clarify_question or GENERIC_CLARIFY)
    elif ws is None:
        outcome = _Outcome(NO_WORKSPACE_REPLY)
    else:
        route = _ROUTES.get(intent.intent)
        env = _Env(deps=deps, ctx=ctx, ws=ws, brand=brand, chat_id=chat_id)
        if route is None:
            outcome = _Outcome(GENERIC_CLARIFY)
        else:
            try:
                outcome = await route(env, intent)
            except Exception:
                logger.exception("voice: %s marshrutida xato", intent.intent)
                outcome = _Outcome("Buyruqni bajarishda xatolik bo'ldi. Birozdan keyin "
                                   "qayta urinib ko'ring.")

    active_ws = outcome.workspace_id or (str(ws.id) if ws else None)
    voice_name = brand.get("tts_voice") or VOICE_MAP.get(str(brand.get("voice", "")))
    reply_audio: bytes | None = None
    reply_fmt: str | None = None
    if settings.voice_reply:
        reply_audio, reply_fmt = await synthesize_reply(
            outcome.reply_text, workspace_id=active_ws or "", voice=voice_name
        )

    async with deps.session_factory() as session:
        memory = {"intent": intent.intent,
                  "entities": intent.entities.model_dump(exclude_none=True,
                                                         exclude_defaults=True),
                  **outcome.memory}
        if outcome.workspace_id:
            memory["workspace_id"] = outcome.workspace_id
        await owner_memory.remember(
            session, chat_id=chat_id, role="jarvis", text=outcome.reply_text,
            workspace_id=active_ws, intent=memory,
        )
        await session.commit()

    return VoiceReply(
        transcript=transcript,
        intent=intent,
        reply_text=outcome.reply_text,
        reply_audio=reply_audio,
        reply_audio_fmt=reply_fmt,
        actions=outcome.actions,
        needs_confirmation=outcome.needs_confirmation,
        cost_usd=_cost_since(t0, {ws_hint, active_ws or "", str(ws.id) if ws else "", ""}),
        workspace_id=active_ws,
        enqueue_brief=outcome.enqueue_brief,
        stt_provider=stt_provider,
    )


__all__ = ["VoiceReply", "fmt_due", "handle_owner_utterance", "synthesize_reply"]
