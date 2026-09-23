# 01 — Arxitektura

## Umumiy sxema

```
┌──────────────────────── Telegram bot (aiogram) ─────────────────────────┐
│  Ega ◄─ hisobot / tasdiq        Xodimlar ◄─ vazifa / eslatma            │
└───────────────┬─────────────────────────────────────────┬───────────────┘
                │                                         │
        ┌───────▼─────────┐                      ┌────────▼─────────┐
        │  FastAPI (api)  │◄─── webhooks ────────│ Instagram Graph  │
        │  REST + jobs    │      (lead, DM,      │ / lead-forma /   │
        └───────┬─────────┘       comment)       │ sayt formasi     │
                │                                └──────────────────┘
   ┌────────────┼──────────────────┐
   │            │                  │
┌──▼───────┐ ┌──▼───────────┐ ┌────▼──────────┐
│ Content  │ │   Jarvis     │ │  CRM (Postgres│
│ Engine   │ │  supervisor  │ │  + web-sahifa)│
│ LangGraph│ │  LangGraph   │ └───────────────┘
└──┬───────┘ └──┬───────────┘
   │            │
   │   ┌────────┴──── Redis/arq navbat ────────────┐
   │   │                                            │
┌──▼───▼────┐  ┌──────────────┐  ┌──────────────┐  ┌▼───────────┐
│ LLM router│  │ TTS adapter  │  │ FLUX adapter │  │ Remotion   │
│ (Gemini / │  │ Azure/Google/│  │ (fal/replic.)│  │ render     │
│  Claude)  │  │ ElevenLabs   │  │              │  │ worker     │
└───────────┘  └──────────────┘  └──────────────┘  └────────────┘
                     Aktivlar → MinIO (S3)
```

## Tayyor poydevorlar (docs/07)
Jarvis uchun: **Chatwoot** (IG DM/komment/Telegram/sayt inbox), **Twenty CRM** (lead/task/campaign, UI),
**LiveKit Agents** (telefon SIP, STT→LLM→TTS quvur). Biz faqat Jarvis miyasi, adapterlar va Telegram botni yozamiz.

## Konteynerlar (docker-compose)
| Servis   | Vazifa                                  |
|----------|-----------------------------------------|
| api      | FastAPI + LangGraph, arq worker         |
| bot      | Telegram bot (aiogram), api'ga REST     |
| render   | Node + Remotion, navbatdan vazifa oladi |
| chatwoot | inbox (infra/chatwoot, alohida compose) |
| twenty   | CRM (infra/twenty, alohida compose)     |
| livekit  | ovoz + SIP (infra/livekit, bosqich 6)   |
| postgres | pgvector bilan                          |
| redis    | navbat + kesh                           |
| minio    | video/rasm/audio                        |

## Content Engine grafi

```
Intake → Audit → BrandProfile → Strategy(AIDA 7 kun)
   └─ har kun uchun DaySubgraph:
        Writer → [UzCritic ∥ BrandCritic ∥ HookCritic]
              → score<8 ? Writer (max 3) : AssetGen
        AssetGen: TTS ∥ FLUX(schnell→dev) ∥ DepthMap
              → RemotionCompose → VisionQA
              → interrupt(): Telegram tasdiq
              → Publish/Schedule
Analytics(48h) → TasteMemory
```

Checkpointer: Postgres (`langgraph-checkpoint-postgres`) — jarayon uzilsa davom etadi.

## Jarvis grafi

```
Event (yangi lid / muddat / cron 09:00 / ega buyrug'i)
  → Supervisor (qaysi agent?)
     ├─ LeadScorer → CRM yoz → Ega'ga xabar ("14 lid, 9 issiq, qo'ng'iroq qilaymi?")
     ├─ Caller (bosqich 2: telefon; bosqich 1: Telegram/DM matn) → call_log
     ├─ TaskManager → xodimga vazifa, deadline, eslatma, eskalatsiya
     └─ Reporter → kunlik hisobot (matn + ovozli)
  → Policy gate: action.level == "requires_approval" ? interrupt() : bajar
```

## Xotira (3 qatlam)
1. `brand_profile` — JSON, har promptga to'liq kiradi (ton, taqiqlangan so'zlar, CTA, siz/sen).
2. `taste_memory` — pgvector; har tasdiq/rad "nega" izohi bilan; kritiklar top-k o'qiydi.
3. `reference_library` — referens videolar strukturasi: `[{t:0-3,role:"hook",text:...},...]`.

Jarvis uchun qo'shimcha: `staff_memory` (xodim odatlari), `lead_memory` (suhbat tarixi).

## Ruxsat etilgan tashqi servislar
Gemini API, Anthropic API, fal.ai yoki Replicate (FLUX, Depth Anything), Azure Speech / Google TTS / ElevenLabs, Instagram Graph API (Chatwoot orqali), Telegram Bot API, Chatwoot API, Twenty API, LiveKit. Bosqich 6: mahalliy SIP trunk.
Boshqa servis qo'shish — avval shu ro'yxatga yozib, sababini ko'rsat.

## Xarajat nishoni
Bitta 30s Reels ≤ $0.30 (LLM + TTS + 4–6 rasm). Bitta Jarvis lid-qo'ng'iroq (bosqich 2) ≤ $0.10.
