from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot import texts
from bot.api_client import ApiError
from bot.handlers import settings as settings_handlers
from bot.handlers import voice
from bot.keyboards import CB
from bot.states import VoiceStates
from bot.voice_mode import set_voice_mode
from tests.conftest import (
    FakeApiClient,
    FakeBot,
    FakeCallbackQuery,
    FakeMessage,
    FakeRedis,
    FakeUser,
)


def fsm_state() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))


def _voice_result(**overrides) -> dict:
    result = {
        "transcript": "hammasiga ha",
        "intent": "approve_all",
        "confidence": 0.95,
        "reply_text": "Bajarildi, hammasiga ha deyildi.",
        "needs_confirmation": False,
        "actions": [],
        "audio_url": None,
        "audio_b64": None,
        "job_id": None,
    }
    result.update(overrides)
    return result


# -- voice/audio message happy path ---------------------------------------------------
@pytest.mark.asyncio
async def test_voice_message_shows_transcript_and_reply_and_sends_voice_note(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 1)
    audio_b64 = base64.b64encode(b"jarvis-voice-bytes").decode()
    api = FakeApiClient(
        get_workspace={"id": "ws1"},
        voice_command=_voice_result(audio_b64=audio_b64),
    )
    message = FakeMessage(
        from_user=FakeUser(id=1, full_name="Owner"), voice=SimpleNamespace(file_id="v1")
    )
    bot = FakeBot(downloaded=b"ogg-bytes")

    await voice.on_voice_message(message, api, bot)

    assert bot.download.await_count == 1
    assert (
        "voice_command",
        (1,),
        {"audio": b"ogg-bytes", "text": None, "workspace_id": "ws1", "role": "owner"},
    ) in api.calls
    placeholder = message._children[0]
    rendered = placeholder.edit_text.await_args.args[0]
    assert "hammasiga ha" in rendered
    assert "Bajarildi, hammasiga ha deyildi." in rendered
    assert placeholder.voice_notes_sent  # audio_b64 present -> a voice note was sent


@pytest.mark.asyncio
async def test_voice_message_uses_staff_role_for_non_owner(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 999)
    api = FakeApiClient(get_workspace={"id": "ws1"}, voice_command=_voice_result())
    message = FakeMessage(
        from_user=FakeUser(id=1, full_name="Xodim"), audio=SimpleNamespace(file_id="a1")
    )
    bot = FakeBot()

    await voice.on_voice_message(message, api, bot)

    assert any(kwargs.get("role") == "staff" for name, _, kwargs in api.calls if name == "voice_command")


@pytest.mark.asyncio
async def test_voice_note_uses_audio_url_when_no_b64(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 1)
    api = FakeApiClient(
        get_workspace={"id": "ws1"},
        voice_command=_voice_result(audio_url="https://cdn.example.com/jarvis.ogg"),
    )
    message = FakeMessage(from_user=FakeUser(id=1, full_name="Owner"), voice=SimpleNamespace(file_id="v1"))
    bot = FakeBot()

    await voice.on_voice_message(message, api, bot)

    placeholder = message._children[0]
    assert placeholder.voice_notes_sent == ["https://cdn.example.com/jarvis.ogg"]


@pytest.mark.asyncio
async def test_voice_message_no_audio_means_no_voice_note(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 1)
    api = FakeApiClient(get_workspace={"id": "ws1"}, voice_command=_voice_result())
    message = FakeMessage(from_user=FakeUser(id=1, full_name="Owner"), voice=SimpleNamespace(file_id="v1"))
    bot = FakeBot()

    await voice.on_voice_message(message, api, bot)

    placeholder = message._children[0]
    assert placeholder.voice_notes_sent == []


@pytest.mark.asyncio
async def test_voice_message_shows_generic_error_on_api_failure(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 1)
    api = FakeApiClient(get_workspace={"id": "ws1"}, voice_command=ApiError("boom"))
    message = FakeMessage(from_user=FakeUser(id=1, full_name="Owner"), voice=SimpleNamespace(file_id="v1"))
    bot = FakeBot()

    await voice.on_voice_message(message, api, bot)

    placeholder = message._children[0]
    placeholder.edit_text.assert_awaited_with(texts.ERROR_GENERIC)


# -- needs_confirmation / pending action -> ✅/❌ keyboard ---------------------------------------------------
@pytest.mark.asyncio
async def test_pending_action_shows_confirm_buttons_with_action_id(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 1)
    api = FakeApiClient(
        get_workspace={"id": "ws1"},
        voice_command=_voice_result(
            transcript="issiq lidlarga yoz",
            reply_text="6 ta issiq lidga yozaymi?",
            needs_confirmation=True,
            actions=[
                {
                    "id": "a1",
                    "type": "message_lead",
                    "level": 2,
                    "status": "pending",
                    "summary": "6 ta lidga yozish",
                }
            ],
        ),
    )
    message = FakeMessage(from_user=FakeUser(id=1, full_name="Owner"), voice=SimpleNamespace(file_id="v1"))
    bot = FakeBot()

    await voice.on_voice_message(message, api, bot)

    placeholder = message._children[0]
    kb = placeholder.edit_text.await_args.kwargs["reply_markup"]
    callback_datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "cb:voice_yes:a1:-" in callback_datas
    assert "cb:voice_no:a1:-" in callback_datas


@pytest.mark.asyncio
async def test_voice_confirm_yes_calls_jarvis_decision():
    api = FakeApiClient(jarvis_decision={"ok": True})
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:voice_yes:a1:-", message=message)
    cb_data = CB(action="voice_yes", id="a1")

    await voice.on_voice_confirm_yes(callback, cb_data, api)

    assert ("jarvis_decision", ("a1",), {"decision": "yes"}) in api.calls
    message.edit_text.assert_awaited_with(texts.JARVIS_APPROVAL_YES)


@pytest.mark.asyncio
async def test_voice_confirm_no_calls_jarvis_decision():
    api = FakeApiClient(jarvis_decision={"ok": True})
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:voice_no:a1:-", message=message)
    cb_data = CB(action="voice_no", id="a1")

    await voice.on_voice_confirm_no(callback, cb_data, api)

    assert ("jarvis_decision", ("a1",), {"decision": "no"}) in api.calls
    message.edit_text.assert_awaited_with(texts.JARVIS_APPROVAL_NO)


@pytest.mark.asyncio
async def test_voice_retry_prompts_for_a_new_voice_message():
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:voice_retry:-:-", message=message)

    await voice.on_voice_retry(callback)

    callback.answer.assert_awaited()
    message.edit_text.assert_awaited_with(texts.VOICE_RETRY)


# -- ✏️ Tuzatish FSM -> resend as text ---------------------------------------------------
@pytest.mark.asyncio
async def test_voice_fix_flow_resends_corrected_text_and_renders_new_reply(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 1)
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:voice_fix:-:-", message=message)
    state = fsm_state()

    await voice.on_voice_fix_start(callback, state)
    assert await state.get_state() == VoiceStates.waiting_correction.state
    message.edit_text.assert_awaited_with(texts.VOICE_ASK_CORRECTION)

    api = FakeApiClient(
        get_workspace={"id": "ws1"},
        voice_command=_voice_result(
            transcript="kechagi hisobotni ayt",
            reply_text="Mana kunlik hisobot.",
        ),
    )
    correction_message = FakeMessage(
        text="kechagi hisobotni ayt", from_user=FakeUser(id=1, full_name="Owner")
    )
    await voice.on_voice_correction_text(correction_message, api, state)

    assert await state.get_state() is None
    assert (
        "voice_command",
        (1,),
        {"audio": None, "text": "kechagi hisobotni ayt", "workspace_id": "ws1", "role": "owner"},
    ) in api.calls
    placeholder = correction_message._children[0]
    rendered = placeholder.edit_text.await_args.args[0]
    assert "kechagi hisobotni ayt" in rendered
    assert "Mana kunlik hisobot." in rendered


@pytest.mark.asyncio
async def test_voice_correction_with_empty_text_shows_error():
    api = FakeApiClient()
    state = fsm_state()
    await state.set_state(VoiceStates.waiting_correction)
    correction_message = FakeMessage(text="   ")

    await voice.on_voice_correction_text(correction_message, api, state)

    correction_message.answer.assert_awaited_with(texts.ERROR_GENERIC)
    assert api.calls == []


# -- job_id -> reuse brief-progress poller ---------------------------------------------------
@pytest.mark.asyncio
async def test_voice_result_with_job_id_polls_brief_progress(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 1)
    api = FakeApiClient(
        get_workspace={"id": "ws1"},
        voice_command=_voice_result(
            transcript="fitnes klub uchun 3 ta reels tayyorla",
            reply_text="Boshladim, 3 ta reels tayyorlanmoqda.",
            job_id="job-1",
        ),
        get_job={"status": "done"},
    )
    message = FakeMessage(from_user=FakeUser(id=1, full_name="Owner"), voice=SimpleNamespace(file_id="v1"))
    bot = FakeBot()

    await voice.on_voice_message(message, api, bot)

    placeholder = message._children[0]
    assert placeholder._children, "expected a brief-progress placeholder message"
    progress_msg = placeholder._children[-1]
    assert progress_msg.edit_text.await_args_list[-1].args[0] == texts.BRIEF_DONE


# -- 🎙 Jarvis rejimi: owner plain text routing ---------------------------------------------------
@pytest.mark.asyncio
async def test_owner_text_routes_to_voice_command_when_mode_on(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 1)
    redis = FakeRedis()  # no stored key -> default on
    api = FakeApiClient(get_workspace={"id": "ws1"}, voice_command=_voice_result())
    message = FakeMessage(text="hammasiga ha", from_user=FakeUser(id=1, full_name="Owner"))

    await voice.on_owner_text_via_voice_mode(message, api, redis)

    assert any(name == "voice_command" for name, _, _ in api.calls)
    placeholder = message._children[0]
    assert "Bajarildi" in placeholder.edit_text.await_args.args[0]


@pytest.mark.asyncio
async def test_owner_text_falls_back_to_old_flow_when_mode_off(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 1)
    redis = FakeRedis()
    await set_voice_mode(redis, 1, False)
    api = FakeApiClient()
    message = FakeMessage(text="hammasiga ha", from_user=FakeUser(id=1, full_name="Owner"))

    await voice.on_owner_text_via_voice_mode(message, api, redis)

    assert api.calls == []
    assert message.answer.await_count == 0


@pytest.mark.asyncio
async def test_staff_plain_text_is_never_routed_via_voice_mode(monkeypatch):
    monkeypatch.setattr(voice.settings, "owner_tg_id", 999)
    redis = FakeRedis()
    api = FakeApiClient()
    message = FakeMessage(text="salom", from_user=FakeUser(id=1, full_name="Xodim"))

    await voice.on_owner_text_via_voice_mode(message, api, redis)

    assert api.calls == []


# -- 🎙 Jarvis rejimi toggle screens (menu + settings) ---------------------------------------------------
@pytest.mark.asyncio
async def test_menu_voice_mode_screen_shows_current_state():
    redis = FakeRedis()
    message = FakeMessage(chat_id=1)
    callback = FakeCallbackQuery(data="cb:menu:-:voice", message=message)

    await voice.on_menu_voice_mode(callback, redis)

    assert "Yoqilgan" in message.edit_text.await_args.args[0]


@pytest.mark.asyncio
async def test_voice_mode_set_off_persists_to_redis():
    redis = FakeRedis()
    message = FakeMessage(chat_id=5)
    callback = FakeCallbackQuery(data="cb:voice_mode_set:-:off", message=message)
    cb_data = CB(action="voice_mode_set", arg="off")

    await voice.on_voice_mode_set(callback, cb_data, redis)

    assert redis.store["chat:5:voice_mode"] == "off"
    assert "O'chirilgan" in message.edit_text.await_args.args[0]


@pytest.mark.asyncio
async def test_settings_screen_shows_voice_mode_toggle_row(monkeypatch):
    monkeypatch.setattr(settings_handlers.bot_settings, "owner_tg_id", 1)
    api = FakeApiClient(get_workspace={"id": "ws1", "brand_profile": {}})
    redis = FakeRedis()
    message = FakeMessage(chat_id=1)
    callback = FakeCallbackQuery(data="cb:menu:-:settings", message=message)

    await settings_handlers.on_menu_settings(callback, api, redis)

    kb = message.edit_text.await_args.kwargs["reply_markup"]
    flat = [b.text for row in kb.inline_keyboard for b in row]
    assert "🔘 🎙 Jarvis rejimi" in flat  # default on


@pytest.mark.asyncio
async def test_settings_voice_mode_toggle_flips_and_persists(monkeypatch):
    monkeypatch.setattr(settings_handlers.bot_settings, "owner_tg_id", 1)
    api = FakeApiClient(get_workspace={"id": "ws1", "brand_profile": {}})
    redis = FakeRedis()
    message = FakeMessage(chat_id=1)
    callback = FakeCallbackQuery(data="cb:voice_mode_toggle:-:-", message=message)

    await settings_handlers.on_voice_mode_toggle(callback, api, redis)

    assert redis.store["chat:1:voice_mode"] == "off"
    kb = message.edit_text.await_args.kwargs["reply_markup"]
    flat = [b.text for row in kb.inline_keyboard for b in row]
    assert "⚪ 🎙 Jarvis rejimi" in flat


# -- /jarvis help screen ---------------------------------------------------
@pytest.mark.asyncio
async def test_jarvis_help_lists_five_uz_examples():
    message = FakeMessage(text="/jarvis")

    await voice.cmd_jarvis_help(message)

    rendered = message.answer.await_args.args[0]
    for example in (
        "Azizga ayt, zakazni ertaga 3 gacha yopsin",
        "hammasiga ha",
        "kechagi hisobotni ayt",
        "issiq lidlarga yoz",
        "fitnes klub uchun 3 ta reels tayyorla",
    ):
        assert example in rendered
