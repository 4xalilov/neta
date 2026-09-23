import json

import pytest

from bot.keyboards import (
    approval_request_kb,
    jarvis_report_kb,
    script_approval_kb,
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
