"""All user-facing Uzbek strings (HTML parse mode).

Rules (docs/08-design-system.md): every message <= 6 lines, first line is a
bold heading with an emoji, numbers are spelled out explicitly (no vague
words). Callers use ``.format(...)`` on the templates below.
"""

# -- generic / errors ---------------------------------------------------
ERROR_GENERIC = (
    "⚠️ <b>Xatolik yuz berdi</b>\n"
    "Server bilan bog'lanib bo'lmadi. Birozdan so'ng qayta urinib ko'ring."
)
CANCELLED = "❌ <b>Bekor qilindi</b>"

# -- /start ---------------------------------------------------
WELCOME_OWNER = (
    "👋 <b>Xush kelibsiz!</b>\n"
    "Workspace tayyor: <b>{workspace_name}</b>\n"
    "Quyidagi menyudan boshlang."
)
WELCOME_STAFF = "👋 <b>Xush kelibsiz, {full_name}!</b>\nSiz xodim sifatida ro'yxatdan o'tdingiz."
MENU_HEADING = "📋 <b>Bosh menyu</b>\nKerakli bo'limni tanlang."

# -- brief ---------------------------------------------------
ASK_BRIEF = "📝 <b>Brif yuboring</b>\nReels uchun mavzu va g'oyani yozing."
BRIEF_STARTED = "⏳ <b>Ssenariy yozilmoqda…</b>\n(~2 daq)"
BRIEF_PROGRESS = "⏳ <b>Ssenariy yozilmoqda…</b>\nBosqich: {stage}\nJarayon: {progress}%"
BRIEF_DONE = "✅ <b>Ssenariy tayyor!</b>\nTasdiqlash uchun quyida ko'ring."
BRIEF_FAILED = "❌ <b>Xatolik</b>\nSsenariy yozib bo'lmadi: {error}"
BRIEF_TIMEOUT = "⌛ <b>Vaqt tugadi</b>\n10 daqiqada javob kelmadi. Qayta urinib ko'ring."

# -- script approval ---------------------------------------------------
SCRIPT_APPROVAL = (
    "🎬 <b>Ssenariy tasdiqlash</b>\n"
    "Hook: {hook}\n"
    "Matn: {body}\n"
    "CTA: {cta}\n"
    "Baholar: 🇺🇿 {uz_score} · 🎯 {brand_score} · 🪝 {hook_score}"
)
SCRIPT_APPROVED = "✅ <b>Ssenariy tasdiqlandi</b>\nHook #{hook_idx}"
ASK_REJECT_REASON = "✏️ <b>Sababni yozing</b>\nNega rad etyapsiz? Bir jumlada yozing."
SCRIPT_REJECTED = "❌ <b>Rad etildi</b>\nSabab saqlandi: {reason}"
SCRIPT_RETRY = "🔄 <b>Qayta yozilmoqda…</b>"

# -- video approval ---------------------------------------------------
VIDEO_APPROVAL = (
    "🎥 <b>Video tasdiqlash</b>\n"
    "Xarajat: ${cost}\n"
    "VisionQA: {vision_qa}\n"
    "Davomiyligi: {duration}s"
)
VIDEO_PUBLISHED = "✅ <b>Nashr qilindi</b>"
VIDEO_SCHEDULED = "🕒 <b>Rejalashtirildi</b>"
ASK_VIDEO_REJECT_REASON = "✏️ <b>Sababni yozing</b>\nVideoni nega rad etyapsiz?"
VIDEO_REJECTED = "❌ <b>Rad etildi</b>\nSabab: {reason}"

# -- jarvis daily report ---------------------------------------------------
JARVIS_REPORT = (
    "📊 <b>Kunlik hisobot</b>\n"
    "{leads} ta lid / {hot} ta issiq\n"
    "Sotuv: {sales} ta, {revenue} so'm\n"
    "Muddati o'tgan: {overdue} ta vazifa"
)
JARVIS_REPORT_ACK = "✉️ <b>Xabar yuborildi</b>\nIssiq lidlarga xabar yuborildi."
JARVIS_REMIND_ACK = "👤 <b>Eslatma yuborildi</b>\nXodimga eslatma yuborildi."

# -- jarvis approval request (requires_approval) ---------------------------------------------------
JARVIS_APPROVAL_REQUEST = "🤖 <b>Tasdiq so'rovi</b>\n{description}"
JARVIS_APPROVAL_YES = "✅ <b>Tasdiqlandi</b>"
JARVIS_APPROVAL_NO = "❌ <b>Rad etildi</b>"
JARVIS_APPROVAL_EDIT = "✏️ <b>Tahrirlash</b>\nO'zgartirishni yozing."

# -- settings ---------------------------------------------------
SETTINGS_HEADING = (
    "⚙️ <b>Sozlamalar</b>\n"
    "Murojaat: {pronoun}\n"
    "Ovoz: {voice}\n"
    "Registr: {register}"
)
SETTINGS_SAVED = "✅ <b>Saqlandi</b>"

PRONOUN_LABELS = {"siz": "Siz", "sen": "Sen"}
VOICE_LABELS = {"madina": "Madina", "sardor": "Sardor"}
REGISTER_LABELS = {"casual": "Erkin", "neutral": "Neytral", "formal": "Rasmiy"}

# -- voice-first Jarvis (roadmap 5.10) ---------------------------------------------------
VOICE_LISTENING = "🎙 <b>Eshitdim, bajaryapman…</b>"
VOICE_RESULT = "🗣 <i>«{transcript}»</i>\n{reply_text}"
VOICE_ASK_CORRECTION = "✏️ <b>Tuzatish</b>\nTo'g'ri matnni yozing."
VOICE_RETRY = "🔁 <b>Qayta ayting</b>\nOvozli xabar yuboring."

VOICE_MODE_HEADING = (
    "🎙 <b>Jarvis rejimi</b>\n"
    "Holat: {state}\n"
    "Yoqilganda, oddiy matn xabarlar ham buyruq sifatida qabul qilinadi."
)
VOICE_MODE_LABELS = {True: "Yoqilgan ✅", False: "O'chirilgan ❌"}

JARVIS_HELP = (
    "🎙 <b>Jarvis rejimi</b>\n"
    "• Azizga ayt, zakazni ertaga 3 gacha yopsin\n"
    "• hammasiga ha\n"
    "• kechagi hisobotni ayt\n"
    "• issiq lidlarga yoz\n"
    "• fitnes klub uchun 3 ta reels tayyorla"
)

# -- notify: voice_reply / clarify (API -> bot push, bot/notify.py) ---------------------------------------------------
VOICE_REPLY_NOTIFY = "🗣 <b>Jarvis</b>\n{text}"
VOICE_CLARIFY = "❓ <b>Aniqlashtirish</b>\n{question}"
