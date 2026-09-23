# 07 — Tayyor open-source poydevorlar: nima olamiz, nima o'zimiz yozamiz

Qaror (2026-09-24): Jarvis'ni noldan yozmaymiz. Uch qismi uchun tayyor loyihalar olinadi,
biz faqat "miya"ni (LangGraph agentlar, policy, Telegram bot) va kontent dvigatelini yozamiz.

## Tanlovlar

| Qatlam | Tayyor loyiha | Nega | Litsenziya |
|---|---|---|---|
| Ovoz/telefon | **LiveKit Agents** | SIP birinchi darajali, WebRTC real vaqt sifati, barge-in, yozib olish, ko'p STT/TTS provayder plaginlari | Apache 2.0 |
| Xabar inbox (IG DM, komment, Telegram, sayt chat) | **Chatwoot** | Meta bilan rasmiy integratsiya, hamma kanal bitta inbox, webhook + API | MIT |
| CRM | **Twenty CRM** | Notion-uslub UI, kanban, GraphQL/REST API, custom obyektlar, tez "professional" ko'rinish | AGPL (self-host ok) |

Ko'rib chiqilgan va rad etilganlar:
- **Pipecat** — prototip uchun yaxshi, telefoniya plagin orqali; LiveKit yetuqroq. Tez sinov uchun ishlatish mumkin.
- **Vocode** — faqat Twilio/Vonage; O'zbekistonda mahalliy SIP kerak.
- **Bolna** — Hindiston bozoriga moslangan.
- **O'z HTMX CRM** — zaxira variant; Twenty muammo chiqarsa qaytamiz (`crm_adapter.py` orqali almashtirish oson).

## Yangi arxitektura

```
Instagram DM/komment ─┐
Telegram (mijoz)      ├─► Chatwoot inbox ──webhook──► Jarvis (LangGraph, BIZNIKI)
Sayt chat / forma    ─┘        ▲                          │ tools
                               │ reply API                │
Telefon (SIP trunk) ─► LiveKit Agents ◄──────────────────┤
                       (STT→LLM→TTS quvur)                │ GraphQL/REST
                                                          ▼
Ega / xodimlar ◄─── Telegram bot (BIZNIKI) ◄────────  Twenty CRM
                                                    (lead, task, campaign, call_log)
Content Engine (BIZNIKI) ──► Instagram ──► lidlar Chatwoot'ga tushadi
```

## Nima o'zimiz yozamiz (qisqargan ro'yxat)
- Jarvis miyasi: `jarvis/supervisor.py`, `lead_scorer`, `task_manager`, `reporter`, `policy.py`
- `integrations/chatwoot.py` — webhook qabul, javob yuborish, kontakt ↔ lead sinxron
- `integrations/crm_adapter.py` — Twenty API ustida yupqa qatlam (`create_lead`, `update_stage`, `create_task`, `list_overdue`)
- `jarvis/voice_agent.py` — LiveKit Agent: Jarvis system prompt + CRM tool'lar
- Telegram bot (ega/xodim), kunlik hisobot, tasdiq tugmalari
- Content Engine — o'zgarishsiz (docs/01)

## Ma'lumot egaligi
- **Twenty — asosiy manba** `lead`, `task`, `campaign`, `staff` uchun. Bizning Postgres'da faqat `jarvis_action`, `taste_memory`, `cost_log`, `post_metrics`, `call_log` (audio uri + transkript).
- Chatwoot contact_id ↔ Twenty person_id bog'lanishi `crm_link` jadvalida.
- Twenty API versiyasi pin qilinadi (`TWENTY_VERSION` .env), yangilash faqat adapter testlari o'tgach.

## Deploy talablari (VDS)
- RAM ≥ 8 GB (Chatwoot + Twenty + Postgres + Redis + bizniki), disk ≥ 60 GB.
- Har biri alohida docker-compose (chatwoot/, twenty/, livekit/) — `infra/` papkasida, bitta `make up-all`.
- Ichki tarmoq: hammasi bitta docker network, tashqariga faqat nginx (chat.domain, crm.domain, api.domain).
- LiveKit SIP: mahalliy operator biznes SIP trunk → LiveKit SIP service. Twilio O'zbekistonda cheklangan.

## Xavflar
- O'zbek STT — LiveKit hal qilmaydi, u faqat quvur. `evals/voice_test.md` 50 qo'ng'iroq testi majburiy (nomzodlar: Gemini Live, mahalliy uz STT; Whisper zaxira).
- Twenty tez o'zgaradi → faqat adapter orqali, to'g'ridan-to'g'ri so'rov yozilmaydi.
- Meta App Review (IG DM ruxsati) — Chatwoot hujjati bo'yicha 1–2 hafta; erta boshlash kerak (bosqich 3 bilan parallel).
- AGPL (Twenty): self-host va ichki foydalanish uchun muammo yo'q; SaaS sifatida sotilsa — yuridik tekshiruv.

## Roadmap'ga ta'siri (docs/03)
- 5.2 → "Chatwoot o'rnatish + IG/Telegram inbox ulash + webhook → Jarvis"
- 5.1, 5.8 → "Twenty o'rnatish, custom obyektlar (Lead, Task, Campaign), `crm_adapter.py` + testlar"
- 6.1–6.2 → "LiveKit self-host + SIP trunk + STT test"; 6.3–6.5 → "Jarvis voice agent LiveKit'da"
- Taxminiy muddat: 5–6 bosqich 4–5 hafta → 2–3 hafta.
