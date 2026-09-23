# STATUS — joriy holat (Claude Code har sessiyada shu yerdan boshlaydi)

**Joriy bosqich:** 2 yakunlandi (2.4/2.6 dan tashqari) / 3 va 5 qisman; 5.10 ovozli boshqaruv kod tayyor
**Keyingi vazifa:** REAL SINOV — serverda `docker compose up`, `.env` kalitlari, birinchi haqiqiy Reels (1-bosqich qabul mezoni). Keyin 2.6 (hook A/B), 3.1–3.5, 4.1/4.3/4.4.

## Bajarilgan (kod + testlar; tashqi servislar mock bilan)
- 0.1–0.6: compose (healthcheck, minio-init, tts GPU profil), FastAPI, SQLAlchemy async (25 jadval) + Alembic 0001–0003, LLM router (gemini|anthropic, retry, JSON, fake), cost_tracker, aiogram 3 bot (8 ekran), CI.
- 1.1–1.7: Writer (motion maydonlari bilan), TTS adapter (edge/azure/navoiy/aisha, so'z-timing, fallback), o'zbek normalizator, FLUX/Depth + MinIO, Remotion ReelsBasic/ReelsParallax, BullMQ render worker, DaySubgraph (TTS∥FLUX → render → VisionQA → interrupt → publish), arq worker, /v1 API.
- 2.1–2.3, 2.5, 2.7, 2.8: 3 kritik + QA halqasi, eval 30 juft (`make eval-local` 100% fake), VisionQA skeleti, motion kutubxonasi (14 matn animatsiyasi, 5 subtitr preseti, 11 o'tish, 10 effekt), 45 uslub temasi JSON + `theme` override + `theme:validate` CLI, uslub bilimlar bazasi (`style_theme`, LLM taklifchi, kuchli model darvozasi, /v1/styles).
- 3.6–3.7: Obsidian vault indekslovchi + `/vault/graph` jonli bilim grafi.
- 4.2: interrupt() tasdiq (Telegram orqali).
- 5.1–5.5, 5.7, 5.8 (skelet): Twenty/Chatwoot adapterlar (yo'llar TAXMIN), LeadScorer/TaskManager/Reporter, supervisor + policy gate, webhook, `/crm` dashboard (KPI, voronka, ROI, Jarvis jurnali inline tasdiq, demo-seed), bot tasdiqlari real ijrochiga ulangan.
- 5.10 Ovozli boshqaruv: STT adapter (gemini/whisper/aisha/uzbekvoice/azure), niyat tahlili (16 intent) + o'zbek sana parser, owner_memory, ovozli javob (TTS→ogg), `/v1/voice/command`, bot ovoz rejimi (transkript, tuzatish, ✅/❌, voice note, 🎙 Jarvis rejimi, workspace eslab qolish), xodim vazifa ekrani + `/v1/tasks`.
- Hujjatlar: 08 dizayn tizimi, 09 TTS tadqiqoti, 10 vault, 11 motion kutubxonasi; roadmap 7.6–7.8 (montaj agenti, xom videodan Reels, musiqa agenti).

Testlar: API 416, bot 134, Remotion 121 — hammasi o'tadi. Ruff/typecheck toza.

## Bajarilmagan / tekshirilmagan
- Hech bir tashqi API real chaqirilmagan (Gemini/Claude, Edge/Azure TTS, fal.ai, Twenty, Chatwoot) — muhitda tarmoq bloklangan, kalitlar yo'q.
- Postgres/pgvector migratsiyalari real DB'da ishga tushirilmagan (faqat sqlite testlar). Docker daemon yo'q edi.
- Twenty/Chatwoot API yo'llari va versiyalari, Aisha TTS endpointi — TAXMIN, "verify" belgilangan.
- 2.4 parallaks oddiy (inpainting yo'q); 2.6 hook A/B yo'q; 3.1–3.5 (IG audit, taste pgvector qidiruv, referens) yo'q; 4.1/4.3/4.4/4.5 yo'q; 6-bosqich boshlanmagan.
- VisionQA video kadrlarini emas, sahna rasmlarini tekshiradi (kadr ajratish render worker'ga o'tadi).
- Xarajat nishoni (Reels ≤ $0.30) o'lchanmagan.

## Ochiq savollar (ega javob beradi)
- SAVOL: Bu bitta akkaunt uchunmi yoki agentlik (ko'p mijoz)? — Hozircha bitta workspace, `workspace_id` hamma jadvalda bor.
- SAVOL: Jarvis ovozi erkak/ayol? "siz"/"sen"? — Default: ayol ovoz (Madina), "siz". `scripts/tts-bench.ps1` bilan sinab tanlanadi.
- SAVOL: Xodimlar soni va Telegram'da ishlaydimi? — Default: ha, Telegram.
- SAVOL: Serverda GPU bormi? — Default: yo'q; Navoiy TTS/ACE-Step uchun bulut GPU (RunPod/Vast) yoki 12 GB VRAM kerak.
- SAVOL: Aisha AI TTS API hujjati/narxi — tekshirilsin.

## Jurnal
- 2026-09-24: loyiha skeleti yaratildi; qaror — Chatwoot + Twenty + LiveKit (docs/07).
- 2026-09-24: 0–2 bosqichlar kodi, 3.6–3.7, 5.x skelet, motion kutubxonasi (45 tema), uslub darvozasi, CRM dashboard, 5.10 ovozli boshqaruv — 38 commit, 671 test. Real servislar bilan sinov keyingi qadam.
