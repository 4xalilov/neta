# 03 — Yo'l xaritasi: 0 dan tayyor mahsulotgacha

Har bosqich = qabul mezonlari bilan. Claude Code `/next` orqali `STATUS.md` dagi
keyingi ochiq vazifani oladi. Bosqichni o'tkazib yuborma.

---

## Bosqich 0 — Poydevor (1–2 kun)
- [ ] 0.1 `docker-compose.yml`: postgres(pgvector), redis, minio, api ishga tushadi
- [ ] 0.2 FastAPI skelet, `/health`, settings (pydantic-settings), `.env.example`
- [ ] 0.3 SQLAlchemy async + Alembic; `workspace`, `brand_profile`, `script`, `asset`, `cost_log` migratsiyasi
- [ ] 0.4 `engine/llm.py` — provider router (gemini|anthropic), `cost_tracker` bilan
- [ ] 0.5 Telegram bot skelet: `/start`, ega ro'yxatdan o'tadi, workspace yaratiladi
- [ ] 0.6 pytest ishlaydi, CI (GitHub Actions) lint+test
**Qabul:** `docker compose up` → `/health` 200, bot `/start`ga javob beradi.

## Bosqich 1 — Yuruvchi skelet: brif → 1 Reels (1 hafta)
- [ ] 1.1 `Writer` node: brif + brand_profile → 1 ssenariy (hook/body/cta/tts_text) JSON
- [ ] 1.2 TTS adapter (`integrations/tts.py`): Azure uz-UZ birinchi; 20 jumlalik urg'u testi `evals/tts_test.md`
- [ ] 1.3 O'zbek matn normalizatori (`engine/uz/normalize.py`): apostrof, raqam→so'z, transliteratsiya
- [ ] 1.4 FLUX adapter: prompt → rasm (schnell), MinIO'ga yozish
- [ ] 1.5 Remotion loyihasi: `ReelsBasic` kompozitsiya (1080×1920, rasm + Ken Burns + kinetik subtitr + audio)
- [ ] 1.6 Render worker: navbatdan `render_job` → mp4 → MinIO
- [ ] 1.7 Zanjir grafi: Writer → TTS ∥ FLUX → Render → Telegram'ga video
**Qabul:** Telegram'da `/brief <matn>` yozilsa 5 daqiqada 15s video keladi, xarajat ≤ $0.20 (cost_log).

## Bosqich 2 — Sifat: QA loop + o'zbek tili (1 hafta)
- [ ] 2.1 `UzCritic`, `BrandCritic`, `HookCritic` agentlari, rubrika `docs/04-agents.md`
- [ ] 2.2 Writer ↔ Critics halqasi, max 3 iteratsiya, `critic_review` yoziladi
- [ ] 2.3 Eval dataset: `evals/scripts/` 30 juft yaxshi/yomon; `make eval` kritik aniqligini o'lchaydi
- [ ] 2.4 Depth Anything → parallax qatlami Remotion'da (`ReelsParallax`)
- [ ] 2.5 VisionQA node: render kadrlarini Gemini vision tekshiradi (matn kesilgan? yuz buzilgan?)
- [ ] 2.6 Hook A/B: 3 hook, 2 variant video
**Qabul:** eval'da kritiklar ≥ 85% mos; ega 10 videodan ≥ 7 tasini birinchi urinishda tasdiqlaydi.

## Bosqich 3 — Xotira va audit (1 hafta)
- [ ] 3.1 Instagram Graph ulash (OAuth), so'nggi 50 post + insights → `ig_audit`
- [ ] 3.2 Audit agenti → `brand_profile` avtomatik qoralama, ega Telegram'da tasdiqlaydi
- [ ] 3.3 Referens video: URL/fayl → Gemini (audio+video) → `structure_json` + embedding
- [ ] 3.4 `taste_memory`: har tasdiq/rad → "nega?" so'raladi → pgvector; kritiklar top-5 o'qiydi
- [ ] 3.5 Ovozli xabar orqali did o'rganish (Telegram voice → Gemini → taste_memory)
- [ ] 3.6 Obsidian vault (`vault/`, docs/10): brend bilimi, SOP, kontent arxivi; `engine/vault/` indekslovchi (frontmatter + embedding → pgvector, `vault_note` jadvali), o'zgargan faylni 10 daqiqada qayta indekslash, `obsidian-git` sinxron
- [ ] 3.7 CRM "Bilim grafi" jonli sahifasi (`/vault/graph`): WebSocket orqali vault fayllari real vaqtda animatsiyali graf (force-graph), yangi fayl "portlab" paydo bo'ladi, teglar rang bilan, tanlangan fayl matni yon panelda; docs/08 tokenlari
**Qabul:** yangi ssenariy avvalgi rad sabablarini takrorlamaydi (eval bilan tekshiriladi); vault'dagi yangi fayl 10 daqiqada Writer promptiga tushadi va grafda ko'rinadi.

## Bosqich 4 — 7 kunlik AIDA reja + nashr (1 hafta)
- [ ] 4.1 `Strategy` node: audit + xotira → 7 kunlik reja (A/I/D/A taqsimoti, format, hook turi)
- [ ] 4.2 Har kun uchun DaySubgraph, Postgres checkpointer, `interrupt()` tasdiq
- [ ] 4.3 Instagram nashr / rejalashtirish (Graph API `media_publish`)
- [ ] 4.4 Analytics node (48h cron) → `post_metrics` → taste_memory'ga "nima ishladi"
- [ ] 4.5 Haftalik hisobot egaga (Telegram)
**Qabul:** dushanba reja → hafta davomida 7 post avtomatik chiqadi, ega faqat tasdiqlaydi.

## Bosqich 5 — CRM + Jarvis (Telegram/Chatwoot rejimi) (2 hafta)
Poydevor: Chatwoot + Twenty CRM (docs/07). Meta App Review'ni 3-bosqichdan boshlab yuritish.
- [ ] 5.1 `infra/twenty/` — Twenty CRM self-host; custom obyektlar: Lead, Task, Campaign, Staff; `TWENTY_VERSION` pin
- [ ] 5.2 `infra/chatwoot/` — Chatwoot self-host; Instagram (DM+komment), Telegram, sayt chat inboxlari; webhook → `/webhooks/chatwoot`
- [ ] 5.3 `integrations/crm_adapter.py` (Twenty) + `integrations/chatwoot.py`; `crm_link` jadvali; adapter testlari (mock)
- [ ] 5.4 `LeadScorer` agenti: issiq/iliq/sovuq + manba (post_id → Campaign) → Twenty'ga yozadi
- [ ] 5.5 Jarvis supervisor grafi + policy gate (`level`), `jarvis_action` jurnali
- [ ] 5.6 Ega bilan dialog (Telegram): "14 lid, 9 issiq, hammasiga yozaymi?" → tasdiq → Chatwoot orqali kvalifikatsiya
- [ ] 5.7 `TaskManager`: xodimga vazifa (Telegram + Twenty Task), deadline (egadan/SLA), eslatma, eskalatsiya
- [ ] 5.8 `Reporter`: kunlik 09:00 hisobot (matn + TTS ovozli), kampaniya ROI (Twenty + post_metrics)
- [ ] 5.9 `staff_memory`: xodim odatlari; `lead_memory`: suhbat xulosalari
**Qabul:** IG DM'dan lid → 2 daqiqada egaga xabar va Twenty'da karta; vazifa muddati o'tsa eskalatsiya; kunlik hisobot keladi.

## Bosqich 6 — Jarvis telefon rejimi (LiveKit) (2–3 hafta)
- [ ] 6.1 `infra/livekit/` — LiveKit server + SIP service self-host; mahalliy operator SIP trunk, test raqami
- [ ] 6.2 STT nomzodlar (Gemini Live, mahalliy uz STT, Whisper zaxira) — 50 real qo'ng'iroq testi `evals/voice_test.md`
- [ ] 6.3 `jarvis/voice_agent.py` — LiveKit Agent: Jarvis system prompt + CRM tool'lar (lead o'qish, task yaratish, xulosa yozish)
- [ ] 6.4 Avval xodimlarga qo'ng'iroq (vazifa berish, holat so'rash)
- [ ] 6.5 Lidga qo'ng'iroq skripti + `requires_approval` → 2 haftadan keyin avtonom
- [ ] 6.6 Yozib olish, transkript, xulosa → `call_log` + Twenty'da activity
**Qabul:** xodim Jarvis qo'ng'irog'ini 9/10 holatda tushunadi; lid suhbati ≥ 70% muvaffaqiyatli kvalifikatsiya; latency ≤ 1.5s.

## Bosqich 7 — Mustahkamlash (davomiy)
- [ ] 7.1 Kommentariya-javob agenti
- [ ] 7.2 Trend skaneri (o'zbek Reels formatlari)
- [ ] 7.3 Multi-tenant (agentlik rejimi), billing
- [ ] 7.4 Monitoring: Langfuse/OpenTelemetry, xarajat dashboardi, alertlar
- [ ] 7.5 Backup, deploy skripti (VDS), README to'liq

---
**Tartib qoidasi:** Bosqich N tugamay N+1 boshlanmaydi. Istisnolar: 6.1–6.2 (SIP/STT testi) 5-bosqich bilan, Meta App Review (5.2 uchun) 3-bosqich bilan parallel.
