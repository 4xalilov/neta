# AI Marketing & Content Engine + Jarvis — Claude Code uchun loyiha qoidalari

Bu fayl har bir Claude Code sessiyasida avtomatik o'qiladi. Ish boshlashdan oldin
`docs/03-roadmap.md` dagi joriy bosqichni top va `docs/STATUS.md` ni o'qi.

## Loyiha nima
Instagram uchun to'liq avtonom marketing tizimi:
1. **Content Engine** — audit → xotira (RAG) → 7 kunlik AIDA reja → o'zbekcha ssenariy → TTS + FLUX + Remotion Reels, ko'p agentli QA loop.
2. **Jarvis** — CRM ustida ishlaydigan ovozli/matnli menejer-agent: lidlarni qabul qiladi, egaga hisobot beradi, xodimlarga vazifa beradi, muddatni kuzatadi, kunlik hisobot yozadi.
3. **CRM/inbox/ovoz** — tayyor open-source: Twenty CRM, Chatwoot, LiveKit Agents (`docs/07-open-source-foundations.md`). Ularga faqat adapter orqali murojaat qilinadi.

Batafsil: `docs/01-architecture.md`, `docs/02-data-model.md`, `docs/06-jarvis-crm.md`, `docs/07-open-source-foundations.md`.

## Ish tartibi (majburiy)
- Har sessiya: `docs/STATUS.md` → keyingi bajarilmagan vazifani ol → bajar → testlar o'tsin → `STATUS.md` ni yangila → commit.
- Bir commit = bir vazifa. Commit xabari o'zbekcha yoki inglizcha, lekin aniq: `feat(writer): AIDA subgraph qo'shildi`.
- Vazifa noaniq bo'lsa, taxmin qilma — `STATUS.md` ga "SAVOL:" qatorini yoz va to'xta.
- Hech qachon API kalitlarini kodga yozma; faqat `.env` (`.env.example` ni yangilab bor).
- Yangi tashqi servis qo'shishdan oldin `docs/01-architecture.md` dagi "Ruxsat etilgan servislar" ro'yxatiga qara.

## Stack (o'zgartirish uchun docs/01-architecture.md ni yangila)
- Python 3.12, FastAPI, LangGraph, SQLAlchemy 2 (async), Alembic, pgvector
- Postgres 16 + pgvector, Redis 7 (navbat: arq), MinIO (S3)
- Node 20 + Remotion 4 (render worker, alohida konteyner)
- Telegram: aiogram 3
- LLM: qoralama — Gemini Flash / Claude Haiku; kritik va yakuniy — Claude Sonnet/Opus. Provayder `engine/llm.py` orqali, to'g'ridan-to'g'ri SDK chaqirma.
- Rasm: FLUX schnell (qoralama) → FLUX dev/pro (tasdiqlangan). Ovoz: `engine/integrations/tts.py` orqali (Azure / Google / ElevenLabs — adapter).
- Test: pytest + pytest-asyncio; Node tomonda vitest.

## Kod qoidalari
- Har LangGraph node — `apps/api/src/engine/graphs/` ichida alohida funksiya, `State` TypedDict bilan tiplangan.
- Har agent prompt — `apps/api/src/engine/agents/prompts/*.md` faylda, kodga qotirilmaydi.
- Kritik agentlar 0–10 ball + JSON sabab qaytaradi (`docs/04-agents.md` dagi rubrika). Ball < 8 → qayta yozish, max 3 aylanish.
- Har LLM chaqiriq `cost_tracker` orqali o'tadi (token va $ hisob).
- O'zbek tili qoidalari: `docs/05-uzbek-language.md`. TTS'ga yuboriladigan matn va subtitr matni BIR manbadan (`script.tts_text`).
- Twenty/Chatwoot'ga to'g'ridan-to'g'ri HTTP so'rov yozilmaydi — faqat `integrations/crm_adapter.py` va `integrations/chatwoot.py` orqali; adapterlar mock bilan testlanadi.
- Jarvis harakat darajalari (`docs/06-jarvis-crm.md`): `report` — avtonom, `assign_task` — avtonom, `call_lead` — dastlab `requires_approval=True`.

## Foydali buyruqlar
- `/next` — STATUS.md dan keyingi vazifani olib ishga tushirish
- `/qa <script_id>` — ssenariyni 3 kritik orqali o'tkazish
- `/uz-check <fayl>` — o'zbek tili tekshiruvi
- `/phase-review` — bosqich yakunida qabul mezonlarini tekshirish

## Qabul mezonlari umumiy
Vazifa "bajarildi" deyiladi faqat: testlar o'tdi, `docker compose up` ishlaydi, STATUS.md yangilandi.
