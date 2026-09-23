"""Ega buyrug'idan niyat tahlili (roadmap 5.10): matn (STT'dan yoki yozilgan) → ``Intent``.

- LLM: ``llm.complete_json(tier="draft")`` + ``agents/prompts/jarvis_intents.md`` (few-shot,
  so'zlashuv uslubi va ruscha o'zlashmalar bilan). Kontekst: xodimlar, oxirgi lidlar, egadagi
  workspace'lar, tasdiq kutayotgan harakatlar va oxirgi suhbat (``owner_memory``).
- LLM'dan keyin DETERMINISTIK qadamlar: xodim/lid/workspace nomlari DB qatorlariga
  ``difflib`` bilan moslanadi (o'zbek kelishik qo'shimchalari olib tashlanadi: "Azizga" →
  "Aziz"); muddat ``parse_uz_datetime`` bilan hisoblanadi (LLM sanani hisoblamaydi —
  faqat ``due_text`` ni aynan ko'chiradi); havolalar ("uni", "o'sha lidga", "yana bir marta")
  LLM hal qilmasa oxirgi suhbatdan olinadi.
- ``confidence < settings.intent_min_confidence`` yoki majburiy ma'lumot yo'q → o'zbekcha
  ``clarify_question`` (Jarvis bajarmaydi, bitta savol beradi — docs/06 "Deadline mantiqi" 3).
"""
from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from engine import llm
from engine.agents import prompt_loader
from engine.settings import settings

logger = logging.getLogger(__name__)

IntentName = Literal[
    "daily_report", "assign_task", "remind_staff", "approve", "reject", "approve_all",
    "message_lead", "call_lead", "query_leads", "query_tasks", "create_brief",
    "schedule_post", "update_settings", "select_workspace", "smalltalk", "unknown",
]
INTENTS: tuple[str, ...] = get_args(IntentName)

DEFAULT_DEADLINE_HOUR = 18  # "ertaga", "juma" — soat aytilmasa ish kuni oxiri
DEFAULT_TZ = "Asia/Tashkent"
FUZZY_CUTOFF = 0.75

GENERIC_CLARIFY = (
    "Tushunmadim. Qaytadan aytib bera olasizmi? Masalan: "
    "«Azizga ertaga 15:00 gacha hisobotni topshir»."
)


# ============================================================ o'zbekcha nisbiy sana/vaqt


def _plain(text: str) -> str:
    """Kichik harf, apostrof variantlari → ``'``, bo'shliqlar bitta."""
    t = (text or "").lower()
    t = re.sub(r"[ʻʼ‘’`´]", "'", t)
    return re.sub(r"\s+", " ", t).strip()


_HOUR_WORDS = {
    "o'n ikki": 12, "o'n bir": 11, "o'n": 10, "to'qqiz": 9, "sakkiz": 8, "yetti": 7,
    "olti": 6, "besh": 5, "to'rt": 4, "uch": 3, "ikki": 2, "bir": 1,
}
_HOUR_WORD_RE = "|".join(re.escape(w) for w in _HOUR_WORDS)  # uzunlari oldin (dict tartibi)
_NUM_WORDS = {"bir yarim": 1.5, "yarim": 0.5, **{k: float(v) for k, v in _HOUR_WORDS.items()}}
_NUM_RE = r"\d+(?:[.,]\d+)?|" + "|".join(re.escape(w) for w in _NUM_WORDS)

_WEEKDAYS = {
    "dushanba": 0, "seshanba": 1, "chorshanba": 2, "payshanba": 3, "yakshanba": 6,
    "juma": 4, "shanba": 5,
    # ruscha o'zlashmalar (lotinda)
    "ponedelnik": 0, "vtornik": 1, "sreda": 2, "chetverg": 3, "pyatnitsa": 4,
    "subbota": 5, "voskresenye": 6,
}
_WEEKDAY_RE = re.compile(r"\b(" + "|".join(_WEEKDAYS) + r")")
_DAY_WORDS = {
    "bugun": 0, "segodnya": 0, "ertaga": 1, "zavtra": 1, "ertasiga": 1,
    "indinga": 2, "indin": 2, "poslezavtra": 2,
}
_DAY_RE = re.compile(r"\b(" + "|".join(sorted(_DAY_WORDS, key=len, reverse=True)) + r")\b")

_REL_TIME_RE = re.compile(
    r"\b(" + _NUM_RE + r")\s*(soat|daqiqa|minut)\w*\s+(keyin|so'ng|o'tib)"
)
_REL_DAY_RE = re.compile(r"\b(" + _NUM_RE + r")\s*(kun|hafta)\w*\s+(keyin|so'ng|o'tib)")
_HHMM_RE = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")
_SOAT_NUM_RE = re.compile(r"\bsoat\s+(\d{1,2})(\s*(?:-?\s*)?yarim)?")
_SOAT_WORD_RE = re.compile(r"\bsoat\s+(" + _HOUR_WORD_RE + r")(?:\s+yarim|da|gacha|ga|lar)?\b")
_WORD_SUFFIX_RE = re.compile(r"\b(" + _HOUR_WORD_RE + r")(?:da|gacha)\b")
_NUM_SUFFIX_RE = re.compile(r"\b(\d{1,2})\s*-?\s*(gacha|da|ga)\b")
_MORNING_RE = re.compile(r"\b(ertalab|tongda|ertalabki)\b")
_EVENING_RE = re.compile(
    r"\b(kechqurun\w*|kechki|kechasi|tushdan keyin|obeddan keyin|abeddan keyin)\b"
)
_NOON_RE = re.compile(r"\b(tushgacha|obedgacha|abedgacha)\b")
_EOD_RE = re.compile(r"\b(kechgacha|kun oxirigacha|ish oxirigacha)\b")


def _zone(tz: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def _num(token: str) -> float:
    token = token.strip()
    if token in _NUM_WORDS:
        return _NUM_WORDS[token]
    return float(token.replace(",", "."))


def _parse_clock(t: str) -> tuple[int, int] | None:
    """Matndagi soat: ``15:30``, ``soat 3 da``, ``soat uchda``, ``3 gacha``, ``beshgacha``."""
    hour: int | None = None
    minute = 0
    m = _HHMM_RE.search(t)
    if m and int(m.group(1)) <= 23 and int(m.group(2)) <= 59:
        return int(m.group(1)), int(m.group(2))
    if (m := _SOAT_NUM_RE.search(t)) is not None:
        hour = int(m.group(1))
        minute = 30 if m.group(2) else 0
    elif (m := _SOAT_WORD_RE.search(t)) is not None:
        hour = _HOUR_WORDS[m.group(1)]
        minute = 30 if "yarim" in m.group(0) else 0
    elif (m := _NUM_SUFFIX_RE.search(t)) is not None:
        hour = int(m.group(1))
    elif (m := _WORD_SUFFIX_RE.search(t)) is not None:
        hour = _HOUR_WORDS[m.group(1)]
    elif _NOON_RE.search(t):
        return 12, 0
    elif _EOD_RE.search(t):
        return DEFAULT_DEADLINE_HOUR, 0
    if hour is None or hour > 23:
        return None
    # Biznes konteksti: "soat 3 da" = 15:00. Ertalab aytilmasa 1–7 → kunduzi/kechki.
    evening = _EVENING_RE.search(t) is not None and hour < 12
    afternoon = 1 <= hour <= 7 and not _MORNING_RE.search(t)
    if evening or afternoon:
        hour += 12
    return hour, minute


def parse_uz_datetime(text: str, now: datetime, tz: str | None = DEFAULT_TZ) -> datetime | None:
    """O'zbekcha nisbiy muddatni aniq vaqtga aylantiradi (``tz`` bo'yicha aware ``datetime``).

    Qo'llab-quvvatlanadi: ``bugun/ertaga/indinga`` (+ ``zavtra``/``poslezavtra``), hafta
    kunlari (``juma``, ``dushanbagacha`` — keyingi shunday kun; bugun o'sha kun bo'lsa —
    keyingi hafta), ``soat 3 da``/``soat uchda``/``3 gacha`` (1–7 → 13–19, "ertalab" bo'lmasa),
    ``15:30``, ``2 soatdan keyin``, ``yarim soatdan keyin``, ``30 daqiqadan keyin``,
    ``3 kundan keyin``, ``tushgacha`` (12:00), ``kechgacha`` (18:00).
    Kun aytilib soat aytilmasa — 18:00. Faqat soat aytilib u o'tib ketgan bo'lsa — ertaga.
    Hech narsa topilmasa ``None``. ``now`` naiv bo'lsa UTC deb olinadi.
    """
    if not text:
        return None
    zone = _zone(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now_local = now.astimezone(zone)
    t = _plain(text)

    m = _REL_TIME_RE.search(t)
    if m:
        amount = _num(m.group(1))
        unit = m.group(2)
        delta = timedelta(hours=amount) if unit == "soat" else timedelta(minutes=amount)
        return (now_local + delta).replace(second=0, microsecond=0)

    day_offset: int | None = None
    if (m := _REL_DAY_RE.search(t)) is not None:
        amount = _num(m.group(1))
        day_offset = round(amount * (7 if m.group(2) == "hafta" else 1))
        t = t[:m.start()] + " " + t[m.end():]
    elif (m := _DAY_RE.search(t)) is not None:
        day_offset = _DAY_WORDS[m.group(1)]
    elif (m := _WEEKDAY_RE.search(t)) is not None:
        ahead = (_WEEKDAYS[m.group(1)] - now_local.weekday()) % 7
        day_offset = ahead or 7

    clock = _parse_clock(t)
    if day_offset is None and clock is None:
        return None

    base: date = now_local.date() + timedelta(days=day_offset or 0)
    hour, minute = clock if clock else (DEFAULT_DEADLINE_HOUR, 0)
    dt = datetime(base.year, base.month, base.day, hour, minute, tzinfo=zone)
    if day_offset is None and dt <= now_local:
        dt += timedelta(days=1)
    return dt


# ============================================================ modellar


_TEMPERATURE_ALIASES = {
    "hot": "hot", "issiq": "hot", "goryachiy": "hot",
    "warm": "warm", "iliq": "warm",
    "cold": "cold", "sovuq": "cold", "xolodniy": "cold",
}
_PERIOD_ALIASES = {
    "today": "today", "bugun": "today", "bugungi": "today",
    "yesterday": "yesterday", "kecha": "yesterday", "kechagi": "yesterday",
    "week": "week", "hafta": "week", "haftalik": "week",
}


class IntentEntities(BaseModel):
    model_config = ConfigDict(extra="ignore")

    staff_name: str | None = None
    staff_id: str | None = None
    lead_name: str | None = None
    lead_id: str | None = None
    lead_ids: list[str] = Field(default_factory=list)
    task_title: str | None = None
    due_text: str | None = None
    due_at: str | None = None  # ISO 8601, workspace tz bilan (parse_uz_datetime)
    temperature: Literal["hot", "warm", "cold"] | None = None
    count: int | None = None
    period: Literal["today", "yesterday", "week"] | None = None
    workspace_name: str | None = None
    workspace_id: str | None = None
    brief_text: str | None = None
    message_text: str | None = None
    setting_key: str | None = None
    setting_value: str | None = None
    action_id: str | None = None

    @field_validator("temperature", mode="before")
    @classmethod
    def _temperature(cls, v: Any) -> Any:
        if v in (None, ""):
            return None
        return _TEMPERATURE_ALIASES.get(_plain(str(v)))

    @field_validator("period", mode="before")
    @classmethod
    def _period(cls, v: Any) -> Any:
        if v in (None, ""):
            return None
        return _PERIOD_ALIASES.get(_plain(str(v)))

    @field_validator("count", mode="before")
    @classmethod
    def _count(cls, v: Any) -> Any:
        if v in (None, ""):
            return None
        try:
            return int(float(str(v).replace(",", ".")))
        except ValueError:
            return None

    @field_validator("lead_ids", mode="before")
    @classmethod
    def _lead_ids(cls, v: Any) -> Any:
        if v in (None, ""):
            return []
        return [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)]

    @field_validator(
        "staff_name", "staff_id", "lead_name", "lead_id", "task_title", "due_text", "due_at",
        "workspace_name", "workspace_id", "brief_text", "message_text", "setting_key",
        "setting_value", "action_id", mode="before",
    )
    @classmethod
    def _str_or_none(cls, v: Any) -> Any:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


class Intent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: IntentName = "unknown"
    entities: IntentEntities = Field(default_factory=IntentEntities)
    confidence: float = 0.0
    clarify_question: str | None = None
    reply_hint: str | None = None
    text: str = ""  # tahlil qilingan asl matn

    @field_validator("intent", mode="before")
    @classmethod
    def _intent(cls, v: Any) -> Any:
        key = str(v or "").strip().lower()
        return key if key in INTENTS else "unknown"

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, v: Any) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("entities", mode="before")
    @classmethod
    def _entities(cls, v: Any) -> Any:
        return v if isinstance(v, (dict, IntentEntities)) else {}

    @property
    def needs_clarification(self) -> bool:
        return bool(self.clarify_question)


@dataclass
class OwnerContext:
    """Niyat tahlili konteksti — ``jarvis.voice`` DB'dan yig'adi."""

    now: datetime
    timezone: str = DEFAULT_TZ
    workspace_id: str | None = None
    company: str = ""
    staff: list[tuple[str, str]] = field(default_factory=list)  # (id, name)
    leads: list[tuple[str, str]] = field(default_factory=list)  # (id, name)
    workspaces: list[tuple[str, str]] = field(default_factory=list)  # (id, name)
    pending: list[dict[str, Any]] = field(default_factory=list)  # [{id, type, summary}]
    history: list[dict[str, Any]] = field(default_factory=list)  # owner_memory.as_prompt_turns


# ============================================================ nomlarni moslash (difflib)

# O'zbek kelishik/egalik qo'shimchalari va murojaatlar (uzunlari oldin).
_NAME_SUFFIXES = sorted(
    ["larga", "larni", "lardan", "ning", "niki", "dagi", "ga", "ka", "qa", "ni", "dan", "da",
     "ga", "lar", "jon", "aka", "opa", "akaga", "opaga", "akani", "opani", "xon", "bek"],
    key=len, reverse=True,
)


def _name_variants(name: str) -> list[str]:
    base = _plain(name).strip(" .,!?:;\"'«»")
    out = [base]
    words = base.split()
    if words:
        first = words[0]
        out.append(first)
        for word in (base, first):
            for suf in _NAME_SUFFIXES:
                if word.endswith(suf) and len(word) - len(suf) >= 3:
                    stem = word[: -len(suf)].strip()
                    out.append(stem)
                    # "Dilnoza opaga" → "dilnoza"
                    out.append(stem.split()[0] if stem.split() else stem)
    return list(dict.fromkeys(v for v in out if v))


def fuzzy_match(
    name: str | None, candidates: list[tuple[str, str]], cutoff: float = FUZZY_CUTOFF
) -> tuple[str, str] | None:
    """``name`` ni ``[(id, name), ...]`` ichidan topadi: aniq → birinchi so'z → difflib."""
    if not name or not candidates:
        return None
    index: dict[str, tuple[str, str]] = {}
    firsts: dict[str, list[tuple[str, str]]] = {}
    for cid, cname in candidates:
        key = _plain(cname)
        index.setdefault(key, (cid, cname))
        if key.split():
            firsts.setdefault(key.split()[0], []).append((cid, cname))
    for first, rows in firsts.items():  # birinchi ism yagona bo'lsa — kalit sifatida
        if len(rows) == 1:
            index.setdefault(first, rows[0])

    variants = _name_variants(name)
    for v in variants:
        if v in index:
            return index[v]
    keys = list(index)
    best: tuple[float, tuple[str, str]] | None = None
    for v in variants:
        for match in difflib.get_close_matches(v, keys, n=1, cutoff=cutoff):
            ratio = difflib.SequenceMatcher(None, v, match).ratio()
            if best is None or ratio > best[0]:
                best = (ratio, index[match])
    if best:
        return best[1]
    # Oxirgi urinish: nomning biror so'zi ("Olimp" → "Fitnes klub Olimp") — faqat yagona bo'lsa.
    for v in variants:
        if len(v) < 4:
            continue
        hits = {index[k] for k in keys if v in k.split() or (" " in v and v in k)}
        if len(hits) == 1:
            return hits.pop()
    return None


# ============================================================ tahlil


_REFERENCE_RE = re.compile(
    r"\b(uni|unga|undan|uning|o'sha|o'shanga|o'shani|shu|shunga|shuni|avvalgi\w*|oldingi\w*)\b"
)
_REPEAT_RE = re.compile(r"\b(yana bir marta|yana bir bor|takrorla\w*|yana shunday|yana shuni)\b")

SETTING_OPTIONS: dict[str, dict[str, str]] = {
    "pronoun": {"siz": "siz", "sen": "sen"},
    "voice": {"madina": "madina", "sardor": "sardor", "ayol": "madina", "erkak": "sardor"},
    "register": {"casual": "casual", "erkin": "casual", "neutral": "neutral",
                 "neytral": "neutral", "formal": "formal", "rasmiy": "formal"},
}
_SETTING_KEY_ALIASES = {
    "pronoun": "pronoun", "address_form": "pronoun", "murojaat": "pronoun",
    "voice": "voice", "ovoz": "voice", "tts_voice": "voice",
    "register": "register", "uslub": "register", "registr": "register",
}

_CLARIFY = {
    "staff": "Qaysi xodimga? Xodimlar: {names}.",
    "staff_unknown": "Qaysi xodimga topshiray?",
    "task_title": "{staff}ga qanday vazifa beray?",
    "lead": "Qaysi lidga? Ismini yoki «issiq lidlar» deb ayting.",
    "workspace": "Qaysi mijoz? Ro'yxat: {names}.",
    "workspace_unknown": "Qaysi mijozga o'tay? Nomini ayting.",
    "brief_text": "Qanday kontent tayyorlay? Mavzuni qisqa ayting.",
    "setting": "Qaysi sozlama? Masalan: «ovozni Sardorga o'zgartir» yoki «sen deb gapir».",
}


def _names(rows: list[tuple[str, str]], limit: int = 6) -> str:
    names = [n for _, n in rows[:limit]]
    return ", ".join(names) if names else "—"


def _history_value(history: list[dict[str, Any]], key: str) -> Any:
    for turn in reversed(history):
        if turn.get(key) not in (None, "", []):
            return turn[key]
        ents = turn.get("entities") or {}
        if ents.get(key) not in (None, "", []):
            return ents[key]
    return None


def _last_user_intent(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    for turn in reversed(history):
        if turn.get("role") == "user" and turn.get("intent") not in (None, "unknown"):
            return turn
    return None


def _render_prompt(ctx: OwnerContext) -> str:
    zone = _zone(ctx.timezone)
    now = ctx.now if ctx.now.tzinfo else ctx.now.replace(tzinfo=UTC)
    local = now.astimezone(zone)
    weekday = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba",
               "yakshanba"][local.weekday()]
    return prompt_loader.render(
        "jarvis_intents",
        now=local.strftime("%Y-%m-%d %H:%M"),
        weekday=weekday,
        timezone=ctx.timezone,
        company=ctx.company or "—",
        staff=[n for _, n in ctx.staff],
        leads=[n for _, n in ctx.leads[:30]],
        workspaces=[n for _, n in ctx.workspaces],
        pending=ctx.pending[:10],
        history=ctx.history,
    )


def _apply_references(intent: Intent, text: str, ctx: OwnerContext) -> None:
    t = _plain(text)
    ents = intent.entities
    if _REPEAT_RE.search(t) and intent.intent in ("unknown", "smalltalk"):
        prev = _last_user_intent(ctx.history)
        if prev:
            intent.intent = prev["intent"]
            merged = {**(prev.get("entities") or {}),
                      **ents.model_dump(exclude_none=True, exclude_defaults=True)}
            intent.entities = ents = IntentEntities.model_validate(merged)
            intent.confidence = max(intent.confidence, 0.8)
            intent.clarify_question = None

    has_ref = bool(_REFERENCE_RE.search(t))
    if intent.intent in ("message_lead", "call_lead") and not (
        ents.lead_name or ents.lead_id or ents.temperature or ents.lead_ids
    ) and has_ref:
        lead_ids = _history_value(ctx.history, "lead_ids")
        if lead_ids:
            ents.lead_ids = [str(x) for x in lead_ids]
        else:
            ents.lead_name = _history_value(ctx.history, "lead_name")
    if intent.intent in ("assign_task", "remind_staff") and not ents.staff_name and has_ref:
        ents.staff_name = _history_value(ctx.history, "staff_name")


def _resolve(intent: Intent, text: str, ctx: OwnerContext) -> list[str]:
    """Nomlarni moslaydi, muddatni hisoblaydi; yetishmayotgan majburiy maydonlar ro'yxati."""
    ents = intent.entities
    missing: list[str] = []
    name = intent.intent

    # --- xodim
    if ents.staff_name:
        hit = fuzzy_match(ents.staff_name, ctx.staff)
        if hit:
            ents.staff_id, ents.staff_name = hit
        elif name in ("assign_task", "remind_staff", "query_tasks"):
            ents.staff_id = None
            if name != "query_tasks":
                missing.append("staff")
    elif name == "assign_task":
        missing.append("staff")
    if name == "assign_task" and not ents.task_title:
        missing.append("task_title")

    # --- lid(lar)
    if ents.lead_name and not ents.lead_id:
        hit = fuzzy_match(ents.lead_name, ctx.leads)
        if hit:
            ents.lead_id, ents.lead_name = hit
    if name in ("message_lead", "call_lead") and not (
        ents.lead_id or ents.lead_ids or ents.temperature
    ):
        missing.append("lead")

    # --- workspace (agentlik rejimi)
    if ents.workspace_name:
        hit = fuzzy_match(ents.workspace_name, ctx.workspaces, cutoff=0.6)
        if hit:
            ents.workspace_id, ents.workspace_name = hit
    if name == "select_workspace" and not ents.workspace_id:
        missing.append("workspace")

    # --- muddat
    if name in ("assign_task", "remind_staff", "schedule_post", "call_lead", "message_lead"):
        due = parse_uz_datetime(ents.due_text or "", ctx.now, ctx.timezone)
        if due is None and not ents.due_text:
            due = parse_uz_datetime(text, ctx.now, ctx.timezone)
        if due is None and ents.due_at:
            try:
                due = datetime.fromisoformat(ents.due_at)
            except ValueError:
                due = None
        ents.due_at = due.isoformat() if due else None

    # --- kontent brifi
    if name == "create_brief" and not ents.brief_text:
        ents.brief_text = text.strip() or None
        if not ents.brief_text:
            missing.append("brief_text")

    # --- sozlama
    if name == "update_settings":
        key = _SETTING_KEY_ALIASES.get(_plain(ents.setting_key or ""))
        value = SETTING_OPTIONS.get(key or "", {}).get(_plain(ents.setting_value or ""))
        if key and value:
            ents.setting_key, ents.setting_value = key, value
        else:
            missing.append("setting")
    return missing


def _clarify_for(missing: list[str], intent: Intent, ctx: OwnerContext) -> str:
    what = missing[0]
    if what == "staff":
        return (_CLARIFY["staff"].format(names=_names(ctx.staff)) if ctx.staff
                else _CLARIFY["staff_unknown"])
    if what == "task_title":
        return _CLARIFY["task_title"].format(staff=intent.entities.staff_name or "Xodim")
    if what == "workspace":
        return (_CLARIFY["workspace"].format(names=_names(ctx.workspaces)) if ctx.workspaces
                else _CLARIFY["workspace_unknown"])
    return _CLARIFY.get(what, GENERIC_CLARIFY)


async def parse_intent(text: str, *, context: OwnerContext) -> Intent:
    """Matn → ``Intent`` (LLM + deterministik moslash). Hech qachon exception chiqarmaydi:
    LLM xatosi → ``unknown`` + umumiy aniqlashtiruvchi savol."""
    text = (text or "").strip()
    if not text:
        return Intent(intent="unknown", confidence=0.0, clarify_question=GENERIC_CLARIFY)
    try:
        raw = await llm.complete_json(
            "draft", _render_prompt(context), text, temperature=0.0, max_tokens=800,
            node="jarvis.intents", workspace_id=context.workspace_id or "",
        )
        intent = Intent.model_validate({**raw, "text": text})
    except Exception:
        logger.warning("intents: niyat tahlili muvaffaqiyatsiz", exc_info=True)
        return Intent(intent="unknown", text=text, confidence=0.0,
                      clarify_question=GENERIC_CLARIFY)

    _apply_references(intent, text, context)
    missing = _resolve(intent, text, context)

    if intent.intent == "unknown" or intent.confidence < settings.intent_min_confidence:
        intent.clarify_question = intent.clarify_question or GENERIC_CLARIFY
    elif missing:
        intent.clarify_question = _clarify_for(missing, intent, context)
    elif intent.intent not in ("unknown",):
        intent.clarify_question = None
    return intent
