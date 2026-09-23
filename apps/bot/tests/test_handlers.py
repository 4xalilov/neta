from __future__ import annotations

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot import texts
from bot.handlers import approval, brief, jarvis, settings, start
from bot.keyboards import CB, script_approval_kb
from bot.states import BriefStates, ScriptRejectStates, VideoRejectStates
from tests.conftest import FakeApiClient, FakeCallbackQuery, FakeMessage, FakeUser


def fsm_state() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))


# -- start ---------------------------------------------------
@pytest.mark.asyncio
async def test_start_owner_creates_workspace_and_shows_menu(monkeypatch):
    monkeypatch.setattr(start.settings, "owner_tg_id", 1)
    api = FakeApiClient(get_workspace=None, create_workspace={"id": "ws1", "name": "My biz"})
    message = FakeMessage(from_user=FakeUser(id=1, full_name="Owner"), chat_title="My biz")

    await start.cmd_start(message, api)

    assert message.answer.await_count == 2
    first_call_text = message.answer.await_args_list[0].args[0]
    assert "My biz" in first_call_text
    assert ("create_workspace", (), {"owner_tg_id": 1, "name": "My biz"}) in api.calls


@pytest.mark.asyncio
async def test_start_non_owner_gets_staff_menu(monkeypatch):
    monkeypatch.setattr(start.settings, "owner_tg_id", 999)
    api = FakeApiClient()
    message = FakeMessage(from_user=FakeUser(id=1, full_name="Xodim"))

    await start.cmd_start(message, api)

    texts_sent = [c.args[0] for c in message.answer.await_args_list]
    assert texts.WELCOME_STAFF.format(full_name="Xodim") in texts_sent
    assert not any(name == "create_workspace" for name, _, _ in api.calls)


# -- brief / poll_job ---------------------------------------------------
@pytest.mark.asyncio
async def test_poll_job_reports_done_immediately():
    edited: list[str] = []

    async def edit(text: str) -> None:
        edited.append(text)

    api = FakeApiClient(get_job={"status": "done"})
    job = await brief.poll_job(edit, api, "job-1", interval_s=1, timeout_s=10)

    assert job["status"] == "done"
    assert edited == [texts.BRIEF_DONE]


@pytest.mark.asyncio
async def test_poll_job_reports_failure():
    api = FakeApiClient(get_job={"status": "error", "error": "LLM xato"})
    edited: list[str] = []

    async def edit(text: str) -> None:
        edited.append(text)

    await brief.poll_job(edit, api, "job-1", interval_s=1, timeout_s=10)
    assert edited == [texts.BRIEF_FAILED.format(error="LLM xato")]


@pytest.mark.asyncio
async def test_poll_job_times_out_after_max_duration():
    api = FakeApiClient(get_job={"status": "running", "stage": "tts", "progress": 50})
    edited: list[str] = []
    slept: list[float] = []

    async def edit(text: str) -> None:
        edited.append(text)

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    await brief.poll_job(edit, api, "job-1", interval_s=1, timeout_s=2, sleep=fake_sleep)

    assert edited[-1] == texts.BRIEF_TIMEOUT
    assert slept == [1, 1]


@pytest.mark.asyncio
async def test_cmd_brief_with_inline_text_starts_job_and_polls_to_done():
    api = FakeApiClient(
        get_workspace={"id": "ws1"},
        create_brief="job-9",  # ApiClient.create_brief() unwraps to the job_id string
        get_job={"status": "done"},
    )
    message = FakeMessage(text="/brief yangi mahsulot haqida video")
    state = fsm_state()

    await brief.cmd_brief(message, api, state)

    assert ("create_brief", (), {"workspace_id": "ws1", "text": "yangi mahsulot haqida video"}) in api.calls
    progress_msg = message._children[0]
    assert progress_msg.edit_text.await_count >= 1
    assert progress_msg.edit_text.await_args_list[-1].args[0] == texts.BRIEF_DONE


@pytest.mark.asyncio
async def test_cmd_brief_without_text_asks_and_sets_fsm_state():
    api = FakeApiClient()
    message = FakeMessage(text="/brief")
    state = fsm_state()

    await brief.cmd_brief(message, api, state)

    assert await state.get_state() == BriefStates.waiting_text.state
    assert message.answer.await_args_list[-1].args[0] == texts.ASK_BRIEF


# -- approval: hook selection ---------------------------------------------------
@pytest.mark.asyncio
async def test_hook_selection_updates_radio_marks():
    hooks = ["Birinchi", "Ikkinchi", "Uchinchi"]
    message = FakeMessage(reply_markup=script_approval_kb("s1", hooks, selected_idx=0))
    callback = FakeCallbackQuery(data="cb:hook:s1:2", message=message)
    cb_data = CB(action="hook", id="s1", arg="2")

    await approval.on_hook_select(callback, cb_data)

    callback.answer.assert_awaited()
    new_markup = message.edit_reply_markup.await_args.kwargs["reply_markup"]
    marks = [row[0].text[0] for row in new_markup.inline_keyboard[:3]]
    assert marks == ["⚪", "⚪", "🔘"]


@pytest.mark.asyncio
async def test_script_approve_calls_api_and_shows_confirmation():
    api = FakeApiClient(approve_script={"ok": True})
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:script_ok:s1:1", message=message)
    cb_data = CB(action="script_ok", id="s1", arg="1")

    await approval.on_script_approve(callback, cb_data, api)

    assert ("approve_script", ("s1",), {"hook_idx": 1}) in api.calls
    message.edit_text.assert_awaited_with(texts.SCRIPT_APPROVED.format(hook_idx=2))


@pytest.mark.asyncio
async def test_script_reject_flow_asks_reason_then_calls_reject():
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:script_no:s1:-", message=message)
    cb_data = CB(action="script_no", id="s1")
    state = fsm_state()

    await approval.on_script_reject_start(callback, cb_data, state)
    assert await state.get_state() == ScriptRejectStates.waiting_reason.state
    message.edit_text.assert_awaited_with(texts.ASK_REJECT_REASON)

    api = FakeApiClient(reject={"ok": True})
    reason_message = FakeMessage(text="juda uzun bo'lib ketdi")
    await approval.on_script_reject_reason(reason_message, api, state)

    assert ("reject", ("s1",), {"reason": "juda uzun bo'lib ketdi"}) in api.calls
    assert await state.get_state() is None
    reason_message.answer.assert_awaited_with(
        texts.SCRIPT_REJECTED.format(reason="juda uzun bo'lib ketdi")
    )


# -- video approval ---------------------------------------------------
@pytest.mark.asyncio
async def test_video_publish_calls_api_with_publish_action():
    api = FakeApiClient(approve_video={"ok": True})
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:video_pub:s1:-", message=message)
    cb_data = CB(action="video_pub", id="s1")

    await approval.on_video_publish(callback, cb_data, api)

    assert ("approve_video", ("s1",), {"action": "publish"}) in api.calls
    message.edit_text.assert_awaited_with(texts.VIDEO_PUBLISHED)


@pytest.mark.asyncio
async def test_video_reject_flow(monkeypatch=None):
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:video_no:s1:-", message=message)
    cb_data = CB(action="video_no", id="s1")
    state = fsm_state()

    await approval.on_video_reject_start(callback, cb_data, state)
    assert await state.get_state() == VideoRejectStates.waiting_reason.state

    api = FakeApiClient(reject={"ok": True})
    reason_message = FakeMessage(text="sifat past")
    await approval.on_video_reject_reason(reason_message, api, state)
    assert ("reject", ("s1",), {"reason": "sifat past"}) in api.calls


# -- api error tolerance ---------------------------------------------------
@pytest.mark.asyncio
async def test_script_approve_shows_friendly_error_on_api_failure():
    from bot.api_client import ApiError

    api = FakeApiClient(approve_script=ApiError("boom"))
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:script_ok:s1:0", message=message)
    cb_data = CB(action="script_ok", id="s1", arg="0")

    await approval.on_script_approve(callback, cb_data, api)

    callback.answer.assert_awaited_with(texts.ERROR_GENERIC, show_alert=True)
    message.edit_text.assert_not_awaited()


# -- jarvis ---------------------------------------------------
@pytest.mark.asyncio
async def test_jarvis_daily_report_renders_numbers(monkeypatch):
    monkeypatch.setattr(jarvis.settings, "owner_tg_id", 1)
    api = FakeApiClient(
        get_workspace={"id": "ws1"},
        daily_report={"leads": 14, "hot": 9, "sales": 3, "revenue": 4200000, "overdue": 2},
    )
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:menu:-:report", message=message)

    await jarvis.on_menu_report(callback, api)

    rendered = message.edit_text.await_args.args[0]
    assert "14" in rendered and "9" in rendered and "2" in rendered


@pytest.mark.asyncio
async def test_jarvis_approval_decision_yes():
    api = FakeApiClient(jarvis_decision={"ok": True})
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:appr_yes:action-1:-", message=message)
    cb_data = CB(action="appr_yes", id="action-1")

    await jarvis.on_approval_yes(callback, cb_data, api)

    assert ("jarvis_decision", ("action-1",), {"decision": "yes"}) in api.calls
    message.edit_text.assert_awaited_with(texts.JARVIS_APPROVAL_YES)


# -- settings ---------------------------------------------------
@pytest.mark.asyncio
async def test_settings_change_persists_via_update_brand_profile(monkeypatch):
    monkeypatch.setattr(settings.bot_settings, "owner_tg_id", 1)
    api = FakeApiClient(
        get_workspace={"id": "ws1", "brand_profile": {"pronoun": "sen"}},
        update_brand_profile={"pronoun": "sen", "voice": "sardor", "register": "neutral"},
    )
    message = FakeMessage()
    callback = FakeCallbackQuery(data="cb:set_voice:-:sardor", message=message)
    cb_data = CB(action="set_voice", arg="sardor")

    await settings.on_settings_change(callback, cb_data, api)

    assert ("update_brand_profile", ("ws1",), {"voice": "sardor"}) in api.calls
    callback.answer.assert_awaited_with("Saqlandi ✅")
