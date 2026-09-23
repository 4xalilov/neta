# apps/api — FastAPI + LangGraph Content Engine + arq worker

Roadmap: 1.1 (Writer), 1.7 (zanjir grafi), 2.1–2.2 (3 kritik + halqa), 2.5 (VisionQA skelet),
4.2 (DaySubgraph, checkpointer, `interrupt()` tasdiq).

```bash
cd apps/api
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests alembic
uvicorn engine.main:app --reload          # API
arq engine.worker.WorkerSettings          # graf worker (docker-compose: worker)
```

## DaySubgraph (`engine/graphs/day_subgraph.py`)

```
START → writer ─┬─ uz_critic ────┐
                ├─ brand_critic ─┼─→ collect ─(route_after_critics)─┬─→ writer   (min ball < 8 va iteration < 3)
                └─ hook_critic ──┘                                  └─→ asset_gen (min ball ≥ 8 yoki iteration ≥ 3)
asset_gen (TTS ∥ FLUX×N ∥ depth?) → render (BullMQ) → vision_qa → approval ⟂ interrupt()
approval ─(route_after_approval)─┬─→ publish → END   (approve | schedule)
                                 └─→ END             (reject → taste_memory)
```

| Node | Fayl | Nima qiladi |
|---|---|---|
| `writer` | `nodes/writer.py` | `writer.md` prompt; 0-iter `draft` tier, keyin `critic`; pydantic tekshiruv (3 hook, 3–6 sahna, 3–8 s); `to_tts_text`/`to_display_text`; `script` jadvali (brif uchun `content_plan status=adhoc`) |
| `uz_critic` / `brand_critic` / `hook_critic` | `nodes/critics.py` | parallel (fan-out), `{"reviews": [review]}` |
| `collect` | `nodes/critics.py` | join; `critic_review` qatorlari; `best_script/best_score` (kritiklar minimumi bo'yicha); halqa tugasa `script = best_script`, 3 iteratsiyada o'tmasa `errors` ga ogohlantirish |
| `asset_gen` | `nodes/asset_gen.py` | TTS → MinIO audio ∥ FLUX (`settings.flux_draft_tier`) ∥ depth (`plan_item.parallax`); Remotion props; `asset` qatorlari |
| `render` | `nodes/render.py` | `render_job` (queued) → BullMQ → poll (`render_poll_interval_s`, `render_timeout_s`=900) |
| `vision_qa` | `nodes/vision_qa.py` | `vision` tier, SAHNA RASMLARI bo'yicha (kadr ajratish render workerga ko'chadi — TODO 2.5) |
| `approval` | `nodes/approval.py` | `interrupt(payload)`; resume `{"decision": "approve"\|"reject"\|"schedule", "hook_idx", "reason"}`; `taste_memory` (approved/rejected) |
| `publish` | `nodes/publish.py` | stub: `script.status = approved\|scheduled` (IG nashri — 4.3) |

`reviews` reduceri: kritiklar ro'yxat qo'shadi, writer `None` qaytarib tozalaydi → `reviews`
doim joriy iteratsiya; to'liq tarix `review_history` da.

Checkpointer: `LANGGRAPH_CHECKPOINTER=postgres` → `AsyncPostgresSaver` (`DATABASE_URL`
`+asyncpg` siz), aks holda `MemorySaver` (resume faqat shu worker jarayonida ishlaydi).

Promptlar: `engine/agents/prompts/{writer,uz_critic,brand_critic,hook_critic,vision_qa}.md`,
`engine/agents/prompt_loader.render(name, **kw)` — joy-belgilar: `{brief} {plan_item}
{brand_profile} {taste} {references} {script} {previous_reviews} {address_form}
{allowed_loanwords}`; JSON sxemadagi `{}` lar xavfsiz.

## HTTP API (`/v1`, bot kontrakti — `apps/bot/README.md`)

| Method | Path | Body | Javob |
|---|---|---|---|
| GET | `/health` | — | `{status: "ok"}` |
| POST | `/v1/workspaces` | `{owner_tg_id, name}` | `Workspace` (owner bo'yicha idempotent; default brand_profile) |
| GET | `/v1/workspaces?owner_tg_id=` | — | `Workspace` yoki 404 |
| GET | `/v1/workspaces/{id}` | — | `Workspace` |
| PATCH | `/v1/workspaces/{id}/brand-profile` | istalgan maydonlar (`pronoun`, `voice`, `register`, ...) | birlashtirilgan `brand_profile` dict (`pronoun`↔`address_form`, `voice`→`tts_voice`) |
| POST | `/v1/briefs` | `{workspace_id, text, plan_item?}` | `{job_id}` — arq `run_brief` |
| GET | `/v1/jobs/{job_id}` | — | `{job_id, status, stage, progress, result: {script_id?, video_url?, workspace_id, cost_usd}, error}` |
| POST | `/v1/scripts/{id}/approve` | `{hook_idx}` | `Script` — faqat hook tanlovini saqlaydi |
| POST | `/v1/scripts/{id}/reject` | `{reason, retry?}` | `{ok, detail: resumed\|pending\|recorded, job_id?}` |
| POST | `/v1/scripts/{id}/video-approve` | `{action: publish\|schedule}` | `{ok}` — arq `resume_brief`; video tayyor bo'lmasa 409 |
| GET | `/v1/workspaces/{id}/daily-report` | — | `{leads, hot, sales, revenue, overdue, scripts, videos, cost_usd, cost_by_node, ...}` (stub, 5.8) |
| POST | `/v1/jarvis-actions/{action_id}/decision` | `{decision: yes\|no\|edit}` | `{ok}` — `jarvis_action` ga yozadi (stub); `report:<ws>:<all\|remind>` ham qabul qilinadi |

`engine/api/jarvis_routes.py` mavjud bo'lsa `main.py` uni ham ulaydi (Jarvis agenti).
Ovozli buyruqlar: `POST /v1/voice/command`, `GET /v1/voice/history` — pastda "Ovozli boshqaruv".

Tasdiq oqimi (bitta `interrupt` — video tayyor bo'lgach):
1. Kritiklardan o'tgach → `tg:notify` `script` (hook tanlash; `approve` faqat `hook_idx` ni saqlaydi).
2. Video tayyor → job `status=done, stage=awaiting_approval` → `tg:notify` `video`.
3. `video-approve` → `resume_brief(approve|schedule, hook_idx)` → `publish`.
4. `reject`: interrupt'da bo'lsa → `resume_brief(reject)`; graf hali ishlayotgan bo'lsa → `job_pending:{job}`
   (worker interrupt'ga yetishi bilan qo'llaydi); graf yo'q bo'lsa → to'g'ridan `taste_memory`.
   Sabab `"qayta yozish so'raldi"` (bot 🔄) yoki `retry=true` → shu brif bilan yangi job.

## Ovozli boshqaruv (roadmap 5.10) — `/v1/voice/*`

Ega gapiradi → Jarvis tinglaydi, bajaradi, ovoz bilan javob beradi. Oqim
(`engine/jarvis/voice.py::handle_owner_utterance`):

```
voice (ogg/opus) → integrations/stt.transcribe (gemini | whisper | aisha | uzbekvoice | azure,
  zaxira STT_FALLBACK) → normalize_apostrophes → owner_memory.remember(user)
  → jarvis/intents.parse_intent (draft tier, prompts/jarvis_intents.md, oxirgi N almashuv)
  → marshrut (supervisor / task_manager / reporter / DB so'rov) → javob matni
  → tts.synthesize → audio.mp3_to_ogg_opus (ffmpeg) → owner_memory.remember(jarvis)
```

### `POST /v1/voice/command` (multipart/form-data) — bot kontrakti

| Maydon | Tur | Izoh |
|---|---|---|
| `audio` | fayl (ixtiyoriy) | Telegram voice (`.oga`/ogg-opus); wav/mp3 ham bo'ladi. ≤ 20 MB |
| `text` | str (ixtiyoriy) | matnli buyruq yoki ✏️ tuzatilgan transkript. `audio` YOKI `text` majburiy (aks holda 422) |
| `chat_id` | int (ixtiyoriy) | ega Telegram chat id (default `OWNER_TG_ID`) — suhbat xotirasi kaliti |
| `workspace_id` | str (ixtiyoriy) | faol workspace. Berilmasa: xotiradagi oxirgi `select_workspace` → egadagi birinchi workspace |
| `fmt` | str (ixtiyoriy) | `ogg`/`oga`/`wav`/`mp3`; berilmasa fayl nomi/content-type/baytlardan aniqlanadi |

Javob (200):

```jsonc
{
  "transcript": "Azizga ayt, zakazni ertaga 3 gacha yopsin",   // ovozdan; text bo'lsa o'zi
  "intent": "assign_task", "confidence": 0.95,
  "entities": {"staff_name": "Aziz", "staff_id": "...", "task_title": "zakazni yopish",
               "due_text": "ertaga 3 gacha", "due_at": "2026-09-24T15:00:00+05:00"},
  "reply_text": "Azizga vazifa berildi: «zakazni yopish», muddat ertaga 15:00. Xabar yubordim.",
  "needs_confirmation": false,   // true — requires_approval harakat(lar) pending, tg:notify approval ham ketdi
  "clarify": false,              // true — Jarvis aniqlashtiruvchi savol berdi (reply_text = savol)
  "actions": [{"id": "...", "type": "assign_task", "status": "executed", "level": "autonomous", "task_id": "..."}],
  "audio_url": "http://minio:9000/assets/ws/<ws>/audio/<uuid>.ogg",  // javob ovozi (MinIO)
  "audio_b64": null,             // MinIO ishlamasa — base64 baytlar (audio_url = null)
  "audio_fmt": "ogg",            // "ogg" → sendVoice; "mp3"/"wav" (ffmpeg yo'q) → sendAudio; null → faqat matn
  "job_id": null,                // create_brief bo'lsa arq run_brief job id → GET /v1/jobs/{job_id} bilan kuzatiladi
  "workspace_id": "...",         // javobdan keyingi FAOL workspace — bot keyingi so'rovda shuni yuborsin
  "stt_provider": "gemini", "cost_usd": 0.0012
}
```

Bot uchun eslatma: transkriptni ko'rsating (✏️ tuzatish → shu endpointga `text` bilan qayta),
`needs_confirmation` bo'lsa approval ekranlari `tg:notify` orqali alohida keladi (har harakat
uchun `kind="approval"`, payload `description` bilan); ega "ha"/"hammasiga ha" deb OVOZDA ham
tasdiqlashi mumkin. Agentlik rejimi: `workspace_id` javobdagi qiymatga almashtirilsin.

`GET /v1/voice/history?chat_id=&n=20` → `[{id, role: user|jarvis, text, intent, intent_json,
workspace_id, created_at}]` (eskidan yangiga).

### Niyatlar (`engine/jarvis/intents.py`, `Intent.intent`)

| intent | nima qiladi |
|---|---|
| `daily_report` | `reporter.build_daily_report` (kecha; "bugungi" → bugun) + pending soni |
| `assign_task` | `propose_action("assign_task")` → `task_manager.create_task` + `crm.create_task` + xodimga `tg:notify kind="task"` |
| `remind_staff` | xodim aytilsa — uning ochiq vazifalari bo'yicha `kind="reminder"`; aytilmasa — har kechikkan vazifaga `task.overdue` |
| `approve` / `reject` | `supervisor.decide` — id aytilmasa oxirgi Jarvis javobidagi pending harakatlar, bo'lmasa eng yangisi |
| `approve_all` | `supervisor.batch_approve` |
| `message_lead` / `call_lead` | har lid uchun `propose_action` — policy gate: `requires_approval` → `pending` + `kind="approval"` (to'g'ridan bajarilmaydi) |
| `query_leads` / `query_tasks` | DB hisoblari → "Bugun 14 lid: 9 issiq, 5 iliq." |
| `create_brief` | `job_id` (arq `run_brief`); mijoz nomi aytilsa o'sha workspace'ga |
| `schedule_post` | hozircha faqat yo'naltiruvchi javob (video ekranidagi 🕒) |
| `update_settings` | `brand_profile` patch: `pronoun` siz/sen, `voice` madina/sardor (+`tts_voice`), `register` |
| `select_workspace` | faol workspace (difflib) — `workspace_id` javobda va xotirada |
| `smalltalk` / `unknown` | qisqa javob / `clarify_question` |

`confidence < INTENT_MIN_CONFIDENCE` (0.7) yoki majburiy ma'lumot yo'q → bitta o'zbekcha savol
(`clarify: true`), hech narsa bajarilmaydi. Muddat — `parse_uz_datetime(text, now, tz)`
(bugun/ertaga/indinga, hafta kunlari, "soat 3 da" → 15:00, "15:30", "2 soatdan keyin",
"3 kundan keyin", "tushgacha"; kun aytilib soat aytilmasa 18:00). Xodim/lid/workspace nomlari
DB qatorlariga `difflib` bilan moslanadi ("Azizga" → Aziz). Havolalar ("unga", "o'sha lidga",
"yana bir marta") — oxirgi `OWNER_MEMORY_TURNS` almashuv (`owner_memory` jadvali, migratsiya 0004).

### Yangi `tg:notify` kind (xodimga)

```jsonc
// kind = "task" — ega ovoz bilan vazifa berdi (chat_id = xodim tg_id)
{"task_id", "title", "due_at": "ISO UTC", "due": "ertaga 15:00", "staff_name", "workspace_id"}
// kind = "reminder" — (mavjud) remind_staff: {"staff_id", "staff_name", "title", "task_ids", "titles", "note"}
```

### Sozlamalar (.env)

`STT_PROVIDER=gemini` (draft tier modeli Gemini bo'lishi shart), `STT_FALLBACK=whisper`
(`pip install -e ".[stt-local]"` — faster-whisper, CPU int8), `WHISPER_MODEL=small`,
`UZBEKVOICE_API_KEY`, `INTENT_MIN_CONFIDENCE=0.7`, `VOICE_REPLY=true`, `OWNER_MEMORY_TURNS=10`,
`FFMPEG_BIN=ffmpeg` (api Dockerfile o'rnatadi; topilmasa javob mp3 bo'lib qaytadi).

TEKSHIRILMAGAN: `AishaSTT` endpoint (`{AISHA_URL}/api/v1/stt`) — taxmin; `UzbekvoiceSTT`
(`https://uzbekvoice.ai/api/v1/stt`, multipart `file` + `Authorization: <key>`, javob
`{result: {text}}`) — hujjatga qarab, haqiqiy kalit bilan sinalmagan; Gemini audio narxi —
$0.0001/s placeholder (token narxi 0 bo'lsagina ishlatiladi). Sinov: `evals/stt_test.md`
(50 buyruq) + `evals/stt_bench.py` (WER + niyat aniqligi; `--fake` oflayn).

## Job holati (Redis, `engine/jobs.py`)

`job:{job_id}` hash: `status` (queued|running|done|failed), `stage` (queued → writer → critics →
asset_gen → render → vision_qa → approval → awaiting_approval → published|scheduled|rejected),
`progress` (0–100), `script_id`, `video_url`, `cost_usd`, `error`, `chat_id`, `hook_idx`.
`script_job:{script_id}` → `job_id`. `job_id` = LangGraph `thread_id`.

## `tg:notify` (Redis pub/sub) — `{"chat_id": int, "kind": str, "payload": {...}}`

```jsonc
// kind = "script" — kritiklardan o'tgach (yoki 3 iteratsiyadan keyin eng yaxshisi)
{"script_id", "hooks": [3], "selected_idx", "body", "cta",
 "uz_score", "brand_score", "hook_score", "iteration", "warnings": []}
// kind = "video" — interrupt (ega qarori kutilmoqda)
{"script_id", "video_url", "cost": "0.18", "cost_usd": 0.18, "vision_qa": "OK ✅",
 "vision_qa_detail": {"pass", "issues": [{"frame", "issue"}]}, "duration": 15,
 "hooks", "selected_idx", "warnings"}
// kind = "error" — istalgan xato (bot noma'lum kind uchun ERROR_GENERIC ko'rsatadi)
{"job_id", "error"}
```

## Render navbati (`engine/render_queue.py`)

BullMQ queue `render` (`RENDER_QUEUE`), job name `render`, `opts.jobId = render_job.id`, data:
`{jobId, workspaceId, composition: ReelsBasic|ReelsParallax, props, outputKey: ws/<ws>/video/<uuid>.mp4}`.
Natija: job hash `finishedOn` + `returnvalue.videoUri` (yoki `failedReason`). Producer — pypi
`bullmq>=2,<3` (arq `redis<6` talab qiladi); Node `bullmq` 6.3.8 bilan moslik tekshirilgan.
Testlarda `render_queue.set_fake_queue()`.

## Xarajat

Har LLM/TTS/FLUX chaqirig'i `cost_tracker` → `engine/cost_sink.py` (API lifespan va worker
startup'da o'rnatiladi) → `cost_log`. Run xarajati (`cost_usd` holatda/xabarlarda) —
`cost_tracker.RECENT` dagi shu workspace yozuvlari `started_at` dan beri (bitta workspace'da
parallel runlar bir-birinikini ham ko'radi).

## Stub / keyinroq

- `publish`: IG nashri yo'q (4.3); `publish_to_ig=True` → `NotImplementedError`.
- `vision_qa`: videodan kadr emas, sahna rasmlari (kadr ajratish — render worker, 2.5).
- `daily-report`, `jarvis-actions/{id}/decision`: faqat DB hisob/yozuv (Jarvis 5.x).
- `taste` — so'nggi `TASTE_TOP_K` yozuv (pgvector top-k — 3.4); `references` — so'nggi 3 `reference_video.structure_json`.
- `WorkerSettings.cron_jobs` — bo'sh (4.4 analytics, 5.8 kunlik hisobot).
- Bot "script" ekranidagi ✅ grafni to'xtatmaydi — yakuniy qaror video ekranida.
