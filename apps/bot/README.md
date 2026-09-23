# apps/bot — Telegram bot (aiogram 3)

Professional Uzbek-language Telegram bot for the AI Marketing & Content Engine + Jarvis
(roadmap 0.5, Telegram side of 1.7 / 4.2 / 5.6). Screens follow
`docs/08-design-system.md` ("Telegram bot ekranlari").

## Local setup

```bash
uv venv --python 3.12 apps/bot/.venv
uv pip install --python apps/bot/.venv/bin/python -e "apps/bot[dev]"
cd apps/bot
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

Env vars (see `bot/settings.py`): `TELEGRAM_BOT_TOKEN`, `OWNER_TG_ID`,
`API_URL` (default `http://api:8000`), `REDIS_URL`, plus optional
`WEBHOOK_MODE=true` / `WEBHOOK_URL` / `WEBHOOK_PATH` / `WEBHOOK_HOST` /
`WEBHOOK_PORT` for webhook mode (polling is the default).

## API contract the FastAPI backend (`apps/api`) must implement

None of these endpoints exist yet — this is the contract `bot/api_client.py`
calls against. All requests/responses are JSON. `ApiClient` treats any
network error or non-2xx response as `ApiError`, which handlers turn into a
friendly Uzbek message (`texts.ERROR_GENERIC`) instead of crashing.

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/v1/workspaces` | `{owner_tg_id: int, name: str}` | `Workspace` |
| GET | `/v1/workspaces?owner_tg_id=<int>` | — | `Workspace`, or `404` if none exists yet |
| POST | `/v1/briefs` | `{workspace_id: str, text: str}` | `{job_id: str}` |
| GET | `/v1/jobs/{job_id}` | — | `Job` |
| POST | `/v1/scripts/{script_id}/approve` | `{hook_idx: int}` | `Script` |
| POST | `/v1/scripts/{script_id}/reject` | `{reason: str}` | `{ok: true}` |
| POST | `/v1/scripts/{script_id}/video-approve` | `{action: "publish"\|"schedule"}` | `{ok: true}` |
| GET | `/v1/workspaces/{workspace_id}/daily-report` | — | `Report` |
| POST | `/v1/jarvis-actions/{action_id}/decision` | `{decision: "yes"\|"no"\|"edit"}` | `{ok: true}` |
| PATCH | `/v1/workspaces/{workspace_id}/brand-profile` | any subset of `{pronoun, voice, register}` | `BrandProfile` |
| POST | `/v1/voice/command` | multipart form (see below) | `VoiceResult` |
| GET | `/v1/voice/history?chat_id=<int>&n=<int>` | — | `[VoiceHistoryItem]` |

Shapes (fields the bot reads; the API may add more):

```jsonc
// Workspace
{ "id": "ws_...", "name": "...", "brand_profile": { "pronoun": "siz", "voice": "madina", "register": "neutral" } }

// Job (brief -> script pipeline progress)
{ "status": "queued|running|done|error", "stage": "writer|tts|flux|render", "progress": 0, "error": null }
// terminal statuses the bot recognizes: done/completed/success -> finished; error/failed -> failed

// Script (approve_script response)
{ "id": "s_...", "hook_idx": 0, "status": "approved" }

// Report (daily_report response)
{ "leads": 14, "hot": 9, "sales": 3, "revenue": 4200000, "overdue": 2 }

// BrandProfile (update_brand_profile response)
{ "pronoun": "siz|sen", "voice": "madina|sardor", "register": "casual|neutral|formal" }

// VoiceResult (voice_command response)
{
  "transcript": "hammasiga ha", "intent": "approve_all", "confidence": 0.95,
  "reply_text": "Bajarildi, hammasiga ha deyildi.",
  "needs_confirmation": false,
  "actions": [{ "id": "a_...", "type": "message_lead", "level": 2, "status": "pending", "summary": "6 ta lidga yozish" }],
  "audio_url": null, "audio_b64": null, "job_id": null
}

// VoiceHistoryItem (voice_history response, list)
{ "role": "user|jarvis", "text": "...", "created_at": "2026-01-01T00:00:00Z" }
```

Notes / simplifications the bot makes (documented so the API side stays in
sync, per docs/06 "taste_memory"):

- **✏️ Tahrir** (script edit) and **🔄 Qayta** (regenerate) both currently go
  through `reject(script_id, reason)` — "Tahrir" sends the owner's free-text
  edit instructions as `reason`, "Qayta" sends a fixed
  `"qayta yozish so'raldi"` reason. Both feed the same `taste_memory` "nega?"
  loop from docs/03 §3.4. If the API needs to distinguish edit vs. reject vs.
  regenerate, add a `kind` field to the reject body later; the bot is easy to
  extend.
- **❌ Rad** on the video-approval screen also reuses `reject(script_id, reason)`
  (same taste_memory contract, just at the video stage).
- **✉️ Hammasiga yoz** / **👤 Xodimga eslat** on the daily-report screen call
  `jarvis_decision` with a synthetic `action_id` of `report:<workspace_id>:all`
  / `report:<workspace_id>:remind` and `decision="yes"`, since docs/06 does
  not define a separate endpoint for these two report actions.
- **✏️ Tahrir** on a Jarvis approval-request screen (`requires_approval`,
  docs/06 policy gate) calls `jarvis_decision(action_id, decision="edit")`
  with no extra text field — the owner's follow-up edit text is expected to
  arrive as a normal chat message that Jarvis correlates by conversation
  context; the bot has no dedicated "edit text" endpoint to send it to yet.

## Voice-first Jarvis (`bot/handlers/voice.py`, roadmap 5.10)

`ApiClient.voice_command(chat_id, *, audio=None, text=None, workspace_id=None,
role="owner")` POSTs `multipart/form-data` to **`/v1/voice/command`** — exactly
one of `audio` (raw ogg/opus bytes, as Telegram sends voice notes) or `text` is
included, alongside form fields `chat_id` (int), `workspace_id` (optional),
`fmt` (always `"ogg"`) and **`role`** (`"owner"` or `"staff"`). `role` is not
in the original 5.10 spec — it was added here so the API can tell an owner's
voice/text command apart from a staff member's, since both go through the
same endpoint. The JSON response is the `VoiceResult` shape documented above.

Entry points into this flow:

1. **Voice/audio message** (`F.voice | F.audio`, owner or staff) —
   `bot.download(file)` to bytes -> "🎙 Eshitdim, bajaryapman…" placeholder ->
   `voice_command(audio=...)` -> the placeholder is edited into the result
   screen.
2. **Owner's plain text**, only when **"🎙 Jarvis rejimi"** is on for that chat
   (see below) and no FSM state is active -> `voice_command(text=...)`, same
   placeholder-then-edit flow. Staff text and text typed while another FSM
   flow is in progress (e.g. a reject reason) are never routed this way.
3. **✏️ Tuzatish** on the result screen -> `VoiceStates.waiting_correction` ->
   the next message's text is re-sent as `voice_command(text=<correction>)`.

The result screen (`texts.VOICE_RESULT`, `keyboards.voice_result_kb`) is
`🗣 «transcript»` (italic) + `reply_text`, plus:
- **✅ Ha / ❌ Yo'q** — only when `needs_confirmation` is true or `actions`
  contains an item with `status == "pending"`; the buttons carry that action's
  `id` and call `jarvis_decision(action_id, decision="yes"|"no")`.
- **✏️ Tuzatish** / **🔁 Qayta ayting** — always shown.

If `audio_url` or `audio_b64` is present, a voice note is also sent
(`message.answer_voice`, decoding `audio_b64` into a `BufferedInputFile` when
present, else passing the `audio_url` string straight through to Telegram).
If `job_id` is present (the command kicked off a brief pipeline), the bot
sends a fresh brief-progress placeholder and reuses
`handlers/brief.py::poll_job`/`brief_progress_kb` to track it to completion.

**"🎙 Jarvis rejimi"** is a per-chat on/off flag, stored in Redis as
`chat:{chat_id}:voice_mode` (`"on"`/`"off"`, default **on** for the owner;
`bot/voice_mode.py`). It has two entry points: the 📝/📅/📊/⚙️ menu's own
**🎙 Jarvis rejimi** row (`keyboards.voice_mode_kb`, a dedicated Yoqilgan/
O'chirilgan screen) and a toggle row on the **⚙️ Sozlamalar** screen itself
(`keyboards.settings_kb`'s extra row, action `voice_mode_toggle`). Toggling it
is owner-only (`middlewares.OWNER_ONLY_ACTIONS`).

**`/jarvis`** shows a help screen (`texts.JARVIS_HELP`) with the 5 example
commands from docs/03 §5.10 ("Azizga ayt, zakazni ertaga 3 gacha yopsin",
"hammasiga ha", "kechagi hisobotni ayt", "issiq lidlarga yoz", "fitnes klub
uchun 3 ta reels tayyorla").

## Redis notify format (API -> bot)

The API pushes screens to the bot by publishing JSON to the Redis pub/sub
channel **`tg:notify`**:

```json
{"chat_id": 123456789, "kind": "script|video|report|approval|voice_reply|clarify", "payload": {...}}
```

`bot/notify.py::build_notification(kind, payload)` is the pure renderer
(kind + payload -> `(text, keyboard)`) and is what actually decides the
screen; `run_notify_subscriber` just subscribes and calls
`bot.send_message(chat_id, text, reply_markup=keyboard)`.

Payload shape per `kind`:

```jsonc
// kind = "script"  (ssenariy tasdiq ekrani)
{
  "script_id": "s_...",
  "hooks": ["hook 1", "hook 2", "hook 3"],
  "selected_idx": 0,
  "body": "...", "cta": "...",
  "uz_score": 9, "brand_score": 8, "hook_score": 7
}

// kind = "video"  (video tasdiq ekrani)
{ "script_id": "s_...", "cost": "0.18", "vision_qa": "OK", "duration": 15 }

// kind = "report"  (Jarvis kunlik hisobot)
{ "workspace_id": "ws_...", "leads": 14, "hot": 9, "sales": 3, "revenue": 4200000, "overdue": 2 }

// kind = "approval"  (requires_approval so'rovi, LangGraph interrupt())
{ "action_id": "a_...", "description": "6 ta issiq lidga yozaymi?" }

// kind = "voice_reply"  (Jarvis's own reply pushed outside a request/response
// cycle, e.g. a background job's result) -> text message, and if `audio_url`
// is present the bot also sends it as a voice note (`bot.send_voice`)
{ "text": "6 ta issiq lidga yozildi.", "audio_url": "https://.../reply.ogg" }

// kind = "clarify"  (STT/intent confidence < 0.7 -> a clarifying question;
// same ✅/❌/✏️ keyboard as "approval", reusing `jarvis_decision`, when
// `action_id` is given)
{ "question": "Azizgami yoki Boburgami yozay?", "action_id": "a_..." }
```

## Screens implemented (`docs/08-design-system.md`)

1. `/start` — owner registers -> workspace created via `create_workspace`/
   `get_workspace` -> menu (`bot/handlers/start.py`). Non-owner chats get a
   staff menu.
2. **Menu** — 📝 Brif · 📅 Reja · 📊 Hisobot · ⚙️ Sozlamalar · 🎙 Jarvis rejimi
   (`keyboards.menu_kb`).
3. **Brief** — `/brief <text>` or FSM prompt; sends
   "⏳ Ssenariy yozilmoqda… (~2 daq)" and edits the same message every 5s
   (`brief_poll_interval_s`) up to 10 min (`brief_poll_timeout_s`) via
   `handlers/brief.py::poll_job`, polling `get_job`.
4. **Script approval** — 3-hook radio select (🔘/⚪), body, CTA, critic
   scores, ✅ Tasdiq · ✏️ Tahrir · 🔄 Qayta · ❌ Bekor
   (`handlers/approval.py`, `keyboards.script_approval_kb`). ❌ asks a reason
   via FSM then calls `reject`.
5. **Video approval** — ✅ Nashr · 🕒 Rejalashtir · ❌ Rad (reason via FSM)
   (`handlers/approval.py`, `keyboards.video_approval_kb`).
6. **Jarvis daily report** — leads/hot/sales/overdue numbers, ✉️ Hammasiga
   yoz · 👤 Xodimga eslat (`handlers/jarvis.py`, `keyboards.jarvis_report_kb`).
7. **Jarvis approval request** — ✅ Ha · ❌ Yo'q · ✏️ Tahrir ->
   `jarvis_decision` (`handlers/jarvis.py`, `keyboards.approval_request_kb`).
8. **Settings (⚙️)** — siz/sen, ovoz (Madina/Sardor), registr
   (erkin/neytral/rasmiy), 🎙 Jarvis rejimi toggle, saved via
   `update_brand_profile` / `bot/voice_mode.py`
   (`handlers/settings.py`, `keyboards.settings_kb`).
9. **Voice command result** — `🗣 «transcript»` + Jarvis's `reply_text`,
   optional ✅/❌, always ✏️ Tuzatish · 🔁 Qayta ayting
   (`handlers/voice.py`, `keyboards.voice_result_kb`). See "Voice-first
   Jarvis" above.
10. **🎙 Jarvis rejimi toggle** — Yoqilgan/O'chirilgan, per chat
    (`handlers/voice.py`, `keyboards.voice_mode_kb`).
11. **`/jarvis`** — help screen with 5 example voice commands
    (`handlers/voice.py`, `texts.JARVIS_HELP`).

All screens: HTML parse mode, first line bold heading with emoji, <= 6
lines, callback_data ASCII <= 64 bytes via `keyboards.CB`
(`cb:<action>:<id>:<arg>`), every callback handler calls `answer()`, and
navigation uses `edit_message_text` / `edit_message_reply_markup` instead of
sending new messages.

## Middlewares

- `LoggingMiddleware` — logs every incoming update.
- `OwnerOnlyMiddleware` — blocks approval/settings/jarvis/voice-mode-toggle
  callback actions from anyone other than `OWNER_TG_ID` (voice command
  actions themselves — ✏️ Tuzatish/✅/❌/🔁 — are open to staff too, since
  staff also use the voice flow).

## Redis usage

- `tg:notify` pub/sub channel — see above.
- `chat:{chat_id}:voice_mode` key (`"on"`/`"off"`) — the per-chat "🎙 Jarvis
  rejimi" flag (`bot/voice_mode.py`). Injected into the dispatcher as
  `dp["redis"]` (`bot/__main__.py`); every handler that reads/writes it takes
  an optional `redis` parameter defaulting to `None` (treated as "unavailable
  -> default to on"), so it degrades gracefully and stays easy to unit-test
  with a plain fake (`tests/conftest.py::FakeRedis`).
