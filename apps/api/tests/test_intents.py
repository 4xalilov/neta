"""``engine.jarvis.intents``: o'zbekcha nisbiy sana, nomlarni moslash, niyat tahlili (fake LLM)."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from engine import llm
from engine.agents import prompt_loader
from engine.jarvis import intents
from engine.jarvis.intents import (
    GENERIC_CLARIFY,
    Intent,
    OwnerContext,
    fuzzy_match,
    parse_intent,
    parse_uz_datetime,
)

TZ = "Asia/Tashkent"
# 2026-09-23 — chorshanba, 10:00 Toshkent vaqti
NOW = datetime(2026, 9, 23, 10, 0, tzinfo=ZoneInfo(TZ))


def _t(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=ZoneInfo(TZ))


# ---------------------------------------------------------------- parse_uz_datetime


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("bugun 15:00", _t(2026, 9, 23, 15)),
        ("ertaga", _t(2026, 9, 24, 18)),
        ("zakazni ertaga 3 gacha yopsin", _t(2026, 9, 24, 15)),
        ("indinga", _t(2026, 9, 25, 18)),
        ("indinga ertalab soat 9 da", _t(2026, 9, 25, 9)),
        ("juma", _t(2026, 9, 25, 18)),
        ("jumagacha", _t(2026, 9, 25, 18)),
        ("dushanba kuni", _t(2026, 9, 28, 18)),
        ("chorshanba", _t(2026, 9, 30, 18)),  # bugun chorshanba → keyingi hafta
        ("shanba kuni soat 11:00", _t(2026, 9, 26, 11)),
        ("soat 3 da", _t(2026, 9, 23, 15)),
        ("soat uchda", _t(2026, 9, 23, 15)),
        ("soat 9 da", _t(2026, 9, 24, 9)),  # 9:00 o'tib ketgan → ertaga
        ("kechqurun 8 da", _t(2026, 9, 23, 20)),
        ("15:30", _t(2026, 9, 23, 15, 30)),
        ("soat 4 yarimda", _t(2026, 9, 23, 16, 30)),
        ("2 soatdan keyin", _t(2026, 9, 23, 12)),
        ("yarim soatdan keyin", _t(2026, 9, 23, 10, 30)),
        ("30 daqiqadan keyin", _t(2026, 9, 23, 10, 30)),
        ("3 kundan keyin", _t(2026, 9, 26, 18)),
        ("tushgacha", _t(2026, 9, 23, 12)),
        ("zavtra 10:00", _t(2026, 9, 24, 10)),
        ("Ertaga soat oʻn birda", _t(2026, 9, 24, 11)),
    ],
)
def test_parse_uz_datetime(text, expected):
    assert parse_uz_datetime(text, NOW, TZ) == expected


def test_parse_uz_datetime_none_and_naive_now():
    assert parse_uz_datetime("hech narsa yo'q", NOW, TZ) is None
    assert parse_uz_datetime("", NOW, TZ) is None
    naive_utc = datetime(2026, 9, 23, 5, 0, tzinfo=UTC).replace(tzinfo=None)  # 10:00 Toshkent
    assert parse_uz_datetime("ertaga 3 gacha", naive_utc, TZ) == _t(2026, 9, 24, 15)
    # noma'lum tz → Asia/Tashkent
    assert parse_uz_datetime("bugun 15:00", NOW, "Mars/Base") == _t(2026, 9, 23, 15)


# ---------------------------------------------------------------- fuzzy_match

STAFF = [("s1", "Aziz"), ("s2", "Dilnoza Karimova"), ("s3", "Jasur")]


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Azizga", "s1"), ("aziz aka", "s1"), ("Dilnoza opaga", "s2"), ("Dilnozaga", "s2"),
     ("Azis", "s1"), ("Jasurni", "s3"), ("Bobur", None), ("", None)],
)
def test_fuzzy_match(name, expected):
    hit = fuzzy_match(name, STAFF)
    assert (hit[0] if hit else None) == expected


# ---------------------------------------------------------------- parse_intent (fake LLM)


@pytest.fixture
def fake(monkeypatch):
    """``responses[text] -> dict``; chaqiriqlar ``calls`` da (system, user)."""
    state: dict = {"responses": {}, "calls": []}

    def handler(tier, system, user):
        state["calls"].append((tier, system, user))
        out = state["responses"].get(user)
        if isinstance(out, Exception):
            raise out
        return out or {"intent": "unknown", "confidence": 0.2}

    llm.set_fake(handler)
    yield state
    llm.clear_fake()


def _ctx(**kw) -> OwnerContext:
    base = {"now": NOW, "timezone": TZ, "workspace_id": "ws-1", "company": "Qahva uyi",
            "staff": list(STAFF), "leads": [("l1", "Malika"), ("l2", "Sardor Aliyev")],
            "workspaces": [("w1", "Qahva uyi"), ("w2", "Fitnes klub Olimp")]}
    base.update(kw)
    return OwnerContext(**base)


async def test_assign_task_resolves_staff_and_due(fake):
    text = "Azizga ayt, zakazni ertaga 3 gacha yopsin"
    fake["responses"][text] = {
        "intent": "assign_task", "confidence": 0.95,
        "entities": {"staff_name": "Azizga", "task_title": "zakazni yopish",
                     "due_text": "ertaga 3 gacha"},
    }
    intent = await parse_intent(text, context=_ctx())
    assert intent.intent == "assign_task"
    assert intent.entities.staff_id == "s1" and intent.entities.staff_name == "Aziz"
    assert datetime.fromisoformat(intent.entities.due_at) == _t(2026, 9, 24, 15)
    assert intent.clarify_question is None and not intent.needs_clarification
    tier, system, user = fake["calls"][0]
    assert tier == "draft" and user == text
    assert "Dilnoza Karimova" in system and "chorshanba" in system and "2026-09-23 10:00" in system


async def test_due_from_full_text_when_llm_omits_due_text(fake):
    text = "Jasurga topshir: hisobotni juma kuni tayyorlasin"
    fake["responses"][text] = {"intent": "assign_task", "confidence": 0.9,
                               "entities": {"staff_name": "Jasur", "task_title": "hisobot"}}
    intent = await parse_intent(text, context=_ctx())
    assert datetime.fromisoformat(intent.entities.due_at) == _t(2026, 9, 25, 18)


async def test_low_confidence_asks_clarification(fake):
    fake["responses"]["anavi narsani qil"] = {
        "intent": "daily_report", "confidence": 0.4,
        "clarify_question": "Hisobotnimi yoki vazifanimi?",
    }
    intent = await parse_intent("anavi narsani qil", context=_ctx())
    assert intent.needs_clarification
    assert intent.clarify_question == "Hisobotnimi yoki vazifanimi?"

    fake["responses"]["mmm"] = {"intent": "nimadir", "confidence": 0.99}
    intent = await parse_intent("mmm", context=_ctx())
    assert intent.intent == "unknown" and intent.clarify_question == GENERIC_CLARIFY


async def test_missing_required_entities_ask_specific_question(fake):
    fake["responses"]["vazifa ber"] = {"intent": "assign_task", "confidence": 0.9,
                                      "entities": {"task_title": "zakaz"}}
    intent = await parse_intent("vazifa ber", context=_ctx())
    assert "Qaysi xodimga" in intent.clarify_question and "Aziz" in intent.clarify_question

    fake["responses"]["Boburga ayt"] = {"intent": "assign_task", "confidence": 0.9,
                                       "entities": {"staff_name": "Bobur", "task_title": "x"}}
    intent = await parse_intent("Boburga ayt", context=_ctx())
    assert intent.entities.staff_id is None and "Qaysi xodimga" in intent.clarify_question

    fake["responses"]["Azizga ayt"] = {"intent": "assign_task", "confidence": 0.9,
                                      "entities": {"staff_name": "Aziz"}}
    intent = await parse_intent("Azizga ayt", context=_ctx())
    assert intent.clarify_question == "Azizga qanday vazifa beray?"

    fake["responses"]["lidga yoz"] = {"intent": "message_lead", "confidence": 0.9}
    intent = await parse_intent("lidga yoz", context=_ctx())
    assert "Qaysi lidga" in intent.clarify_question


async def test_lead_and_workspace_fuzzy(fake):
    fake["responses"]["Sardorga yoz"] = {"intent": "message_lead", "confidence": 0.9,
                                        "entities": {"lead_name": "Sardorga"}}
    intent = await parse_intent("Sardorga yoz", context=_ctx())
    assert intent.entities.lead_id == "l2" and not intent.needs_clarification

    text = "fitnes klub uchun 3 ta reels tayyorla"
    fake["responses"][text] = {
        "intent": "create_brief", "confidence": 0.9,
        "entities": {"workspace_name": "fitnes klub", "count": "3",
                     "brief_text": "fitnes klub uchun 3 ta Reels"},
    }
    intent = await parse_intent(text, context=_ctx())
    assert intent.entities.workspace_id == "w2" and intent.entities.count == 3

    fake["responses"]["Olimpga o't"] = {"intent": "select_workspace", "confidence": 0.9,
                                       "entities": {"workspace_name": "Olimp"}}
    intent = await parse_intent("Olimpga o't", context=_ctx())
    assert intent.entities.workspace_id == "w2"

    fake["responses"]["Marsga o't"] = {"intent": "select_workspace", "confidence": 0.9,
                                      "entities": {"workspace_name": "Mars"}}
    intent = await parse_intent("Marsga o't", context=_ctx())
    assert "Qaysi mijoz" in intent.clarify_question


async def test_reference_resolution_from_history(fake):
    history = [
        {"role": "user", "text": "Malikaga yoz", "intent": "message_lead",
         "entities": {"lead_name": "Malika", "lead_id": "l1"}},
        {"role": "jarvis", "text": "Malikaga xabar tayyor.", "lead_ids": ["l1"],
         "lead_names": ["Malika"]},
    ]
    fake["responses"]["unga qo'ng'iroq qil"] = {"intent": "call_lead", "confidence": 0.85}
    intent = await parse_intent("unga qo'ng'iroq qil", context=_ctx(history=history))
    assert intent.entities.lead_ids == ["l1"] and not intent.needs_clarification

    # "yana bir marta" — LLM tushunmasa, oxirgi ega niyati takrorlanadi
    fake["responses"]["yana bir marta"] = {"intent": "unknown", "confidence": 0.3}
    intent = await parse_intent("yana bir marta", context=_ctx(history=history))
    assert intent.intent == "message_lead" and intent.entities.lead_id == "l1"
    assert not intent.needs_clarification


async def test_update_settings_aliases(fake):
    fake["responses"]["ovozni Sardorga o'zgartir"] = {
        "intent": "update_settings", "confidence": 0.9,
        "entities": {"setting_key": "ovoz", "setting_value": "Sardor"},
    }
    intent = await parse_intent("ovozni Sardorga o'zgartir", context=_ctx())
    assert (intent.entities.setting_key, intent.entities.setting_value) == ("voice", "sardor")

    fake["responses"]["rangni o'zgartir"] = {
        "intent": "update_settings", "confidence": 0.9,
        "entities": {"setting_key": "rang", "setting_value": "qizil"},
    }
    intent = await parse_intent("rangni o'zgartir", context=_ctx())
    assert "Qaysi sozlama" in intent.clarify_question


async def test_llm_failure_returns_unknown(fake):
    fake["responses"]["salom"] = RuntimeError("tarmoq yo'q")
    intent = await parse_intent("salom", context=_ctx())
    assert intent.intent == "unknown" and intent.clarify_question == GENERIC_CLARIFY
    empty = await parse_intent("  ", context=_ctx())
    assert empty.needs_clarification


def test_intent_model_coercion():
    it = Intent.model_validate({
        "intent": "MESSAGE_LEAD", "confidence": "1.7",
        "entities": {"temperature": "issiq", "count": "3 ", "period": "kechagi",
                     "staff_name": "  ", "lead_ids": "l1"},
    })
    assert it.intent == "message_lead" and it.confidence == 1.0
    assert it.entities.temperature == "hot" and it.entities.count == 3
    assert it.entities.period == "yesterday" and it.entities.staff_name is None
    assert it.entities.lead_ids == ["l1"]
    assert Intent.model_validate({"entities": "x"}).entities.temperature is None
    assert len(intents.INTENTS) == 16


def test_prompt_renders_without_leftovers():
    text = prompt_loader.render(
        "jarvis_intents", now="2026-09-23 10:00", weekday="chorshanba", timezone=TZ,
        company="Qahva", staff=["Aziz"], leads=["Malika"], workspaces=["Qahva"],
        pending=[{"id": "a1", "type": "message_lead"}], history=[{"role": "user", "text": "x"}],
    )
    assert text.splitlines()[0].startswith("# Rol:")
    assert not set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", text))
    schema = json.loads([ln for ln in text.splitlines() if ln.startswith("{")][-1])
    assert set(schema) == {"intent", "entities", "confidence", "clarify_question", "reply_hint"}
    for example in ("Azizga ayt, zakazni ertaga 3 gacha yopsin", "hammasiga ha",
                    "kechagi hisobotni ayt", "issiq lidlarga yoz",
                    "fitnes klub uchun 3 ta reels tayyorla"):
        assert example in text
    for name in intents.INTENTS:
        assert f"`{name}`" in text


def test_now_naive_in_prompt():
    ctx = _ctx(now=datetime(2026, 9, 23, 5, 0, tzinfo=UTC).replace(tzinfo=None))  # naiv → UTC
    assert "2026-09-23 10:00" in intents._render_prompt(ctx)
    assert datetime(2026, 9, 23, 5, tzinfo=UTC).astimezone(ZoneInfo(TZ)).hour == 10
