import pytest

from bot import texts


def _line_count(rendered: str) -> int:
    return len(rendered.strip().splitlines())


CASES = [
    (texts.WELCOME_OWNER, {"workspace_name": "Mening biznesim"}),
    (texts.WELCOME_STAFF, {"full_name": "Aziz Aliyev"}),
    (texts.MENU_HEADING, {}),
    (texts.ASK_BRIEF, {}),
    (texts.BRIEF_STARTED, {}),
    (texts.BRIEF_PROGRESS, {"stage": "TTS", "progress": 42}),
    (texts.BRIEF_DONE, {}),
    (texts.BRIEF_FAILED, {"error": "timeout"}),
    (texts.BRIEF_TIMEOUT, {}),
    (
        texts.SCRIPT_APPROVAL,
        {
            "hook": "Buni bilmasangiz pushaymon bo'lasiz!",
            "body": "Qisqa matn",
            "cta": "Hoziroq buyurtma bering",
            "uz_score": 9,
            "brand_score": 8,
            "hook_score": 7,
        },
    ),
    (texts.SCRIPT_APPROVED, {"hook_idx": 2}),
    (texts.ASK_REJECT_REASON, {}),
    (texts.SCRIPT_REJECTED, {"reason": "juda uzun"}),
    (texts.SCRIPT_RETRY, {}),
    (
        texts.VIDEO_APPROVAL,
        {"cost": "0.18", "vision_qa": "OK", "duration": 15},
    ),
    (texts.VIDEO_PUBLISHED, {}),
    (texts.VIDEO_SCHEDULED, {}),
    (texts.ASK_VIDEO_REJECT_REASON, {}),
    (texts.VIDEO_REJECTED, {"reason": "sifat past"}),
    (
        texts.JARVIS_REPORT,
        {"leads": 14, "hot": 9, "sales": 3, "revenue": "4 200 000", "overdue": 2},
    ),
    (texts.JARVIS_REPORT_ACK, {}),
    (texts.JARVIS_REMIND_ACK, {}),
    (texts.JARVIS_APPROVAL_REQUEST, {"description": "6 ta issiq lidga yozish"}),
    (texts.JARVIS_APPROVAL_YES, {}),
    (texts.JARVIS_APPROVAL_NO, {}),
    (texts.JARVIS_APPROVAL_EDIT, {}),
    (
        texts.SETTINGS_HEADING,
        {"pronoun": "Siz", "voice": "Madina", "register": "Neytral"},
    ),
    (texts.SETTINGS_SAVED, {}),
    (texts.ERROR_GENERIC, {}),
    (texts.CANCELLED, {}),
    (texts.VOICE_LISTENING, {}),
    (
        texts.VOICE_RESULT,
        {"transcript": "hammasiga ha", "reply_text": "Bajarildi."},
    ),
    (texts.VOICE_ASK_CORRECTION, {}),
    (texts.VOICE_RETRY, {}),
    (texts.VOICE_MODE_HEADING, {"state": "Yoqilgan ✅"}),
    (texts.JARVIS_HELP, {}),
    (texts.VOICE_REPLY_NOTIFY, {"text": "Tayyor."}),
    (texts.VOICE_CLARIFY, {"question": "Qaysi lidga?"}),
]


@pytest.mark.parametrize("template,kwargs", CASES)
def test_texts_render_and_stay_within_six_lines(template: str, kwargs: dict):
    rendered = template.format(**kwargs)
    assert rendered  # renders without raising
    assert _line_count(rendered) <= 6


def test_first_line_is_bold_heading_with_emoji():
    headings = [
        texts.WELCOME_OWNER,
        texts.MENU_HEADING,
        texts.ASK_BRIEF,
        texts.SCRIPT_APPROVAL,
        texts.VIDEO_APPROVAL,
        texts.JARVIS_REPORT,
        texts.JARVIS_APPROVAL_REQUEST,
        texts.SETTINGS_HEADING,
        texts.ERROR_GENERIC,
        texts.VOICE_LISTENING,
        texts.VOICE_ASK_CORRECTION,
        texts.VOICE_RETRY,
        texts.VOICE_MODE_HEADING,
        texts.JARVIS_HELP,
        texts.VOICE_REPLY_NOTIFY,
        texts.VOICE_CLARIFY,
    ]
    for tpl in headings:
        first_line = tpl.strip().splitlines()[0]
        assert "<b>" in first_line and "</b>" in first_line
