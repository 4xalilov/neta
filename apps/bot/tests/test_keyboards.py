from bot.keyboards import (
    CB,
    approval_request_kb,
    jarvis_report_kb,
    menu_kb,
    script_approval_kb,
    settings_kb,
    video_approval_kb,
)


def _all_callback_data(markup) -> list[str]:
    return [btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data]


def test_menu_layout_is_two_by_two():
    kb = menu_kb()
    assert len(kb.inline_keyboard) == 2
    assert [b.text for b in kb.inline_keyboard[0]] == ["📝 Brif", "📅 Reja"]
    assert [b.text for b in kb.inline_keyboard[1]] == ["📊 Hisobot", "⚙️ Sozlamalar"]


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


def test_settings_kb_marks_current_choice():
    kb = settings_kb(pronoun="sen", voice="sardor", register="formal")
    flat = [b.text for row in kb.inline_keyboard for b in row]
    assert "🔘 Sen" in flat and "⚪ Siz" in flat
    assert "🔘 Sardor" in flat and "⚪ Madina" in flat
    assert "🔘 Rasmiy" in flat


def test_all_callback_data_is_ascii_and_at_most_64_bytes():
    long_id = "a" * 30  # a plausibly long uuid/db-id
    keyboards = [
        menu_kb(),
        script_approval_kb(long_id, ["Hook birinchi variant matni", "Ikkinchi", "Uchinchi"], 2),
        video_approval_kb(long_id),
        jarvis_report_kb(long_id),
        approval_request_kb(long_id),
        settings_kb("siz", "madina", "neutral"),
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
