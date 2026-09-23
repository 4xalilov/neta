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

## Redis notify format (API -> bot)

The API pushes screens to the bot by publishing JSON to the Redis pub/sub
channel **`tg:notify`**:

```json
{"chat_id": 123456789, "kind": "script|video|report|approval", "payload": {...}}
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
```

## Screens implemented (`docs/08-design-system.md`)

1. `/start` — owner registers -> workspace created via `create_workspace`/
   `get_workspace` -> menu (`bot/handlers/start.py`). Non-owner chats get a
   staff menu.
2. **Menu** — 📝 Brif · 📅 Reja · 📊 Hisobot · ⚙️ Sozlamalar (`keyboards.menu_kb`).
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
   (erkin/neytral/rasmiy), saved via `update_brand_profile`
   (`handlers/settings.py`, `keyboards.settings_kb`).

All screens: HTML parse mode, first line bold heading with emoji, <= 6
lines, callback_data ASCII <= 64 bytes via `keyboards.CB`
(`cb:<action>:<id>:<arg>`), every callback handler calls `answer()`, and
navigation uses `edit_message_text` / `edit_message_reply_markup` instead of
sending new messages.

## Middlewares

- `LoggingMiddleware` — logs every incoming update.
- `OwnerOnlyMiddleware` — blocks approval/settings/jarvis callback actions
  from anyone other than `OWNER_TG_ID`.
