import json

import pytest

from bot.keyboards import (
    approval_request_kb,
    jarvis_report_kb,
    script_approval_kb,
    task_kb,
    video_approval_kb,
)
from bot.notify import build_notification


def test_script_kind_renders_script_approval_screen():
    payload = {
        "script_id": "s1",
        "hooks": ["Hook 1", "Hook 2", "Hook 3"],
        "selected_idx": 0,
        "body": "Body",
        "cta": "CTA",
        "uz_score": 9,
        "brand_score": 8,
        "hook_score": 7,
    }
    text, kb = build_notification("script", payload)
    assert "Ssenariy tasdiqlash" in text
    assert kb.inline_keyboard == script_approval_kb("s1", payload["hooks"], 0).inline_keyboard


def test_video_kind_renders_video_approval_screen():
    payload = {"script_id": "s1", "cost": "0.18", "vision_qa": "OK", "duration": 15}
    text, kb = build_notification("video", payload)
    assert "Video tasdiqlash" in text
    assert kb.inline_keyboard == video_approval_kb("s1").inline_keyboard


def test_report_kind_renders_jarvis_report_screen():
    payload = {"workspace_id": "ws1", "leads": 14, "hot": 9, "sales": 3, "revenue": 100, "overdue": 2}
    text, kb = build_notification("report", payload)
    assert "Kunlik hisobot" in text
    assert kb.inline_keyboard == jarvis_report_kb("ws1").inline_keyboard


def test_approval_kind_renders_approval_request_screen():
    payload = {"action_id": "a1", "description": "6 ta lidga yozish"}
    text, kb = build_notification("approval", payload)
    assert "Tasdiq so'rovi" in text
    assert kb.inline_keyboard == approval_request_kb("a1").inline_keyboard


def test_unknown_kind_falls_back_to_generic_error():
    text, kb = build_notification("mystery", {})
    assert "Xatolik" in text
    assert kb is None


def test_voice_reply_kind_renders_text_with_no_keyboard():
    payload = {"text": "6 ta issiq lidga yozildi.", "audio_url": "https://cdn.example.com/a.ogg"}
    text, kb = build_notification("voice_reply", payload)
    assert "6 ta issiq lidga yozildi." in text
    assert kb is None  # the voice note itself is sent separately by _handle_message


def test_clarify_kind_with_action_id_renders_confirm_keyboard():
    payload = {"question": "Azizgami yoki Boburgami yozay?", "action_id": "a1"}
    text, kb = build_notification("clarify", payload)
    assert "Azizgami yoki Boburgami yozay?" in text
    assert kb.inline_keyboard == approval_request_kb("a1").inline_keyboard


def test_clarify_kind_without_action_id_has_no_keyboard():
    text, kb = build_notification("clarify", {"question": "Qaysi lidga?"})
    assert "Qaysi lidga?" in text
    assert kb is None


# -- kind="task" (a staff member was voice-assigned a task) ---------------------------------------------------
def test_task_kind_renders_new_task_screen_with_status_buttons():
    payload = {
        "task_id": "t1",
        "title": "zakazni yopish",
        "due_at": "2026-09-24T15:00:00+05:00",
        "due": "ertaga 15:00",
        "staff_name": "Aziz",
        "workspace_id": "ws1",
    }
    text, kb = build_notification("task", payload)
    assert "Yangi vazifa" in text
    assert "zakazni yopish" in text
    assert "ertaga 15:00" in text  # human `due`, not the raw `due_at`
    assert kb.inline_keyboard == task_kb("t1").inline_keyboard


def test_task_kind_falls_back_to_due_at_when_due_missing():
    payload = {"task_id": "t1", "title": "zakazni yopish", "due_at": "2026-09-24T15:00:00+05:00"}
    text, _ = build_notification("task", payload)
    assert "2026-09-24T15:00:00+05:00" in text


# -- kind="reminder" (remind_staff intent) ---------------------------------------------------
def test_reminder_kind_shows_title_when_present():
    payload = {"staff_id": "s1", "staff_name": "Aziz", "title": "zakazni yopish", "task_ids": ["t1"]}
    text, kb = build_notification("reminder", payload)
    assert "Eslatma" in text
    assert "Aziz" in text
    assert "zakazni yopish" in text
    assert kb is None


def test_reminder_kind_falls_back_to_titles_list_without_a_single_title():
    payload = {"staff_name": "Aziz", "titles": ["zakazni yopish", "hisobot yuborish"]}
    text, _ = build_notification("reminder", payload)
    assert "zakazni yopish" in text
    assert "hisobot yuborish" in text


def test_reminder_kind_falls_back_to_note_without_titles():
    payload = {"staff_name": "Aziz", "note": "2 ta vazifa muddati o'tdi"}
    text, _ = build_notification("reminder", payload)
    assert "2 ta vazifa muddati o'tdi" in text


@pytest.mark.asyncio
async def test_handle_message_sends_voice_note_for_voice_reply_with_audio_url():
    from unittest.mock import AsyncMock

    from bot.notify import _handle_message

    bot = AsyncMock()
    raw = json.dumps(
        {
            "chat_id": 42,
            "kind": "voice_reply",
            "payload": {"text": "Tayyor.", "audio_url": "https://cdn.example.com/a.ogg"},
        }
    )

    await _handle_message(bot, raw)

    bot.send_message.assert_awaited_once()
    bot.send_voice.assert_awaited_once_with(42, "https://cdn.example.com/a.ogg")


@pytest.mark.asyncio
async def test_handle_message_skips_voice_note_when_no_audio_url():
    from unittest.mock import AsyncMock

    from bot.notify import _handle_message

    bot = AsyncMock()
    raw = json.dumps({"chat_id": 42, "kind": "voice_reply", "payload": {"text": "Tayyor."}})

    await _handle_message(bot, raw)

    bot.send_message.assert_awaited_once()
    bot.send_voice.assert_not_awaited()


# -- audio_fmt routing (apps/api/README.md "Ovozli boshqaruv") ---------------------------------------------------
@pytest.mark.asyncio
async def test_handle_message_uses_send_audio_for_mp3_audio_fmt():
    from unittest.mock import AsyncMock

    from bot.notify import _handle_message

    bot = AsyncMock()
    raw = json.dumps(
        {
            "chat_id": 42,
            "kind": "voice_reply",
            "payload": {
                "text": "Tayyor.",
                "audio_url": "https://cdn.example.com/a.mp3",
                "audio_fmt": "mp3",
            },
        }
    )

    await _handle_message(bot, raw)

    bot.send_audio.assert_awaited_once_with(42, "https://cdn.example.com/a.mp3")
    bot.send_voice.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_message_uses_send_audio_for_wav_audio_fmt():
    from unittest.mock import AsyncMock

    from bot.notify import _handle_message

    bot = AsyncMock()
    raw = json.dumps(
        {
            "chat_id": 42,
            "kind": "voice_reply",
            "payload": {
                "text": "Tayyor.",
                "audio_url": "https://cdn.example.com/a.wav",
                "audio_fmt": "wav",
            },
        }
    )

    await _handle_message(bot, raw)

    bot.send_audio.assert_awaited_once_with(42, "https://cdn.example.com/a.wav")
    bot.send_voice.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_message_skips_audio_entirely_when_audio_fmt_is_null():
    from unittest.mock import AsyncMock

    from bot.notify import _handle_message

    bot = AsyncMock()
    raw = json.dumps(
        {
            "chat_id": 42,
            "kind": "voice_reply",
            "payload": {
                "text": "Tayyor.",
                "audio_url": "https://cdn.example.com/a.ogg",
                "audio_fmt": None,
            },
        }
    )

    await _handle_message(bot, raw)

    bot.send_message.assert_awaited_once()
    bot.send_voice.assert_not_awaited()
    bot.send_audio.assert_not_awaited()
