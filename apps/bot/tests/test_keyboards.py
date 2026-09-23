from bot.keyboards import (
    CB,
    approval_request_kb,
    jarvis_report_kb,
    menu_kb,
    script_approval_kb,
    settings_kb,
    task_kb,
    video_approval_kb,
    voice_mode_kb,
    voice_result_kb,
)


def _all_callback_data(markup) -> list[str]:
    return [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]


def test_menu_layout_is_two_by_two_plus_voice_mode_row():
    kb = menu_kb()
    assert len(kb.inline_keyboard) == 3
    assert [b.text for b in kb.inline_keyboard[0]] == ["📝 Brif", "📅 Reja"]
    assert [b.text for b in kb.inline_keyboard[1]] == ["📊 Hisobot", "⚙️ Sozlamalar"]
    assert [b.text for b in kb.inline_keyboard[2]] == ["🎙 Jarvis rejimi"]


def test_script_approval_kb_marks_selected_hook_with_filled_radio():
    hooks = ["Birinchi hook", "Ikkinchi hook", "Uchinchi hook"]
    kb = script_approval_kb("script-123", hooks, selected_idx=1)
    hook_rows = kb.inline_keyboard[:3]
    marks = [row[0].text[0] for row in hook_rows]
    assert marks == ["⚪", "🔘", "⚪"]
    # action row: Tasdiq / Tahrir / Qayta, then a separate cancel row
    action_row_texts = [b.text for b in kb.inline_keyboard[3]]
    assert action_row_texts == ["✅ Tasdiq", "✏️ Tahrir", "🔄 Qayta"]
    assert [b.text for b in kb.inline_keyboard[4]] == ["❌ Bekor"]


def test_video_approval_kb_has_three_actions():
    kb = video_approval_kb("script-1")
    texts = [b.text for row in kb.inline_keyboard for b in row]
    assert texts == ["✅ Nashr", "🕒 Rejalashtir", "❌ Rad"]


def test_jarvis_report_kb_actions():
    kb = jarvis_report_kb("ws-1")
    texts = [b.text for row in kb.inline_keyboard for b in row]
    assert texts == ["✉️ Hammasiga yoz", "👤 Xodimga eslat"]


def test_approval_request_kb_actions():
    kb = approval_request_kb("action-1")
    texts = [b.text for row in kb.inline_keyboard for b in row]
    assert texts == ["✅ Ha", "❌ Yo'q", "✏️ Tahrir"]


def test_task_kb_actions_and_callback_data():
    kb = task_kb("task-1")
    texts = [b.text for row in kb.inline_keyboard for b in row]
    assert texts == ["✅ Bajarildi", "⏳ Kechikadi"]
    data = _all_callback_data(kb)
    assert "cb:task_status:task-1:done" in data
    assert "cb:task_status:task-1:delayed" in data


def test_settings_kb_marks_current_choice():
    kb = settings_kb(pronoun="sen", voice="sardor", register="formal")
    flat = [b.text for row in kb.inline_keyboard for b in row]
    assert "🔘 Sen" in flat and "⚪ Siz" in flat
    assert "🔘 Sardor" in flat and "⚪ Madina" in flat
    assert "🔘 Rasmiy" in flat


def test_settings_kb_marks_voice_mode_state():
    on = settings_kb("siz", "madina", "neutral", voice_mode=True)
    off = settings_kb("siz", "madina", "neutral", voice_mode=False)
    assert "🔘 🎙 Jarvis rejimi" in [b.text for row in on.inline_keyboard for b in row]
    assert "⚪ 🎙 Jarvis rejimi" in [b.text for row in off.inline_keyboard for b in row]


def test_voice_mode_kb_marks_current_state():
    on = voice_mode_kb(True)
    flat_on = [b.text for row in on.inline_keyboard for b in row]
    assert "🔘 Yoqilgan" in flat_on and "⚪ O'chirilgan" in flat_on

    off = voice_mode_kb(False)
    flat_off = [b.text for row in off.inline_keyboard for b in row]
    assert "⚪ Yoqilgan" in flat_off and "🔘 O'chirilgan" in flat_off


def test_voice_result_kb_always_has_fix_and_retry():
    kb = voice_result_kb()
    texts_ = [b.text for row in kb.inline_keyboard for b in row]
    assert "✏️ Tuzatish" in texts_
    assert "🔁 Qayta ayting" in texts_
    assert "✅ Ha" not in texts_  # no confirmation needed by default


def test_voice_result_kb_shows_confirm_row_with_action_id():
    kb = voice_result_kb(action_id="a1", show_confirm=True)
    first_row_data = [b.callback_data for b in kb.inline_keyboard[0]]
    assert first_row_data == ["cb:voice_yes:a1:-", "cb:voice_no:a1:-"]


def test_voice_result_kb_skips_confirm_row_without_action_id():
    kb = voice_result_kb(action_id=None, show_confirm=True)
    all_data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert not any(d.startswith(("cb:voice_yes:", "cb:voice_no:")) for d in all_data)


def test_all_callback_data_is_ascii_and_at_most_64_bytes():
    long_id = "a" * 30  # a plausibly long uuid/db-id
    keyboards = [
        menu_kb(),
        script_approval_kb(long_id, ["Hook birinchi variant matni", "Ikkinchi", "Uchinchi"], 2),
        video_approval_kb(long_id),
        jarvis_report_kb(long_id),
        approval_request_kb(long_id),
        task_kb(long_id),
        settings_kb("siz", "madina", "neutral"),
        voice_mode_kb(True),
        voice_result_kb(action_id=long_id, show_confirm=True),
    ]
    for kb in keyboards:
        for data in _all_callback_data(kb):
            assert data.isascii()
            assert len(data.encode("ascii")) <= 64, data


def test_cb_pack_roundtrips_via_scheme():
    cb = CB(action="script_ok", id="abc123", arg="1")
    packed = cb.pack()
    assert packed == "cb:script_ok:abc123:1"
    assert CB.unpack(packed) == cb
