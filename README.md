# AI Marketing & Content Engine + Jarvis

Instagram uchun avtonom kontent dvigateli (o'zbekcha Reels: ssenariy → TTS → FLUX → Remotion, QA loop)
va Jarvis — CRM ustida ishlaydigan menejer-agent (lidlar, xodimlarga vazifa, muddatlar, hisobot).

## Tezkor boshlash

```bash
# 1. Konfiguratsiyani tayyorlash
cp .env.example .env

# 2. Infrastrukturani ishga tushirish
make up
make migrate

# 3. Sog'lik tekshirish
curl http://localhost:8000/health
```

## Servislar

| Servis    | Port      | Vazifa                                          |
|-----------|-----------|------------------------------------------------|
| api       | 8000      | FastAPI + LangGraph motori                      |
| bot       | —         | Telegram bot (aiogram)                          |
| render    | —         | Node.js + Remotion, video generatsiya worker    |
| postgres  | 5432      | pgvector bilan database                         |
| redis     | 6379      | Navbat (arq) + kesh                             |
| minio     | 9000/9001 | S3-compatible fayl saqlash                      |
| tts       | 8010*     | O'zbek ovozli sintez (GPU profili bilan)        |

*`make up-gpu` bilan ishga tushiriladi

## O'zbek ovozli sintez

TTS provayderi `.env` da `TTS_PROVIDER` bilan tanlanaladi. Tafsilotlar: [docs/09-tts-research.md](docs/09-tts-research.md)

| Provaydeir | Xarakteristika                                   | Qanday ishlashi                    |
|------------|--------------------------------------------------|-----------------------------------|
| **edge**   | Bepul, so'z-timing bor                          | Internet qo'shmasiz (Microsoft)    |
| **navoiy** | Self-hosted, GPU, $0 marginal                   | `make up-gpu`; `infra/tts/`        |
| **azure**  | Rasmiy, ~$0.006/30s Reels                       | API kaliti kerak                   |
| **aisha**  | Mahalliy, eng tabiiy o'zbek urg'u               | O'zbekistondan to'lov              |

## Hujjatlar

- [01 — Arxitektura](docs/01-architecture.md): Servislar, LangGraph graflar, xotira
- [02 — Data model](docs/02-data-model.md): Database jadvallar
- [03 — Yo'l xaritasi](docs/03-roadmap.md): Bosqichlar va qabul mezonlari
- [04 — Agentlar](docs/04-agents.md): Kritik rubrika va prompt qabuli
- [05 — O'zbek tili](docs/05-uzbek-language.md): TTS, transliteratsiya, normalizatsiya
- [06 — Jarvis/CRM](docs/06-jarvis-crm.md): Supervayzer, policy gate, CRM adapterlar
- [07 — Poydevorlar](docs/07-open-source-foundations.md): Twenty, Chatwoot, LiveKit
- [08 — Dizayn tizimi](docs/08-design-system.md): Remotion komponenti va stil
- [09 — TTS tadqiqoti](docs/09-tts-research.md): Provaydeir tahlili va tanlash
- [STATUS.md](docs/STATUS.md): Joriy bosqich va vazifalar

## Claude Code bilan ishlash

```bash
claude                    # loyiha papkasida
> /next                   # STATUS.md dan keyingi vazifa
> /qa <script_id>         # Skriptni QA loop orqali o'tkazish
```

## Testlar

Mahalliy ishlatish (containerlar siz):

```bash
make test-local
```

Yoki konteyner ichida:

```bash
docker compose exec api pytest -q
cd apps/render && npm test
```

Lint:

```bash
make lint
make fmt
```

## Stack

- **Backend:** Python 3.12 + FastAPI + LangGraph + SQLAlchemy + pgvector
- **Database:** PostgreSQL 16 + pgvector, Redis 7, MinIO (S3)
- **Video:** Node.js 20 + Remotion 4
- **LLM:** Gemini Flash (qoralama) / Claude Sonnet/Opus (kritik)
- **TTS:** Navoiy (self-hosted, recommended), Edge (free), Azure/Aisha (fallback)
- **Test:** pytest + pytest-asyncio (backend), vitest (Node)

## Litsenziya

Apache 2.0
