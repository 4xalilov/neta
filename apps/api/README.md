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

Tasdiq oqimi (bitta `interrupt` — video tayyor bo'lgach):
1. Kritiklardan o'tgach → `tg:notify` `script` (hook tanlash; `approve` faqat `hook_idx` ni saqlaydi).
2. Video tayyor → job `status=done, stage=awaiting_approval` → `tg:notify` `video`.
3. `video-approve` → `resume_brief(approve|schedule, hook_idx)` → `publish`.
4. `reject`: interrupt'da bo'lsa → `resume_brief(reject)`; graf hali ishlayotgan bo'lsa → `job_pending:{job}`
   (worker interrupt'ga yetishi bilan qo'llaydi); graf yo'q bo'lsa → to'g'ridan `taste_memory`.
   Sabab `"qayta yozish so'raldi"` (bot 🔄) yoki `retry=true` → shu brif bilan yangi job.

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
