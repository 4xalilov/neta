# 06 — Jarvis + CRM

## Jarvis nima
CRM ustida ishlaydigan menejer-agent. Kanallar: Telegram (bosqich 5), telefon SIP (bosqich 6), CRM web.

## Kunlik hayoti (misol)
```
09:00  Reporter → Ega: "Kecha: 14 lid (Reels #12 dan 9), 3 sotuv 4.2 mln so'm, 2 vazifa muddati o'tdi (Aziz). Bugun issiq 6 lidga yozaymi?"
09:05  Ega: "Ha, Azizga ham eslat"
09:06  Caller → 6 lidga DM/Telegram: kvalifikatsiya (ehtiyoj, byudjet, muddat)
09:06  TaskManager → Aziz: "2 vazifa kechikdi: ... Bugun 13:00 gacha holatini yozing"
11:30  Lid javob berdi → Caller xulosa → lead.stage=contacted, score↑ → TaskManager → xodimga "uchrashuv belgilang, muddat: bugun 18:00"
13:00  Aziz javob bermadi → eslatma; 15:00 → egaga eskalatsiya
18:30  Xodim "bajarildi" → task.status=done → CRM
Har 48s Analytics → campaign ROI yangilanadi
```

## Event manbalari
- `lead.created` (webhook: IG lead-forma / DM / komment; sayt; qo'lda)
- `task.due_soon`, `task.overdue` (cron har 15 daq)
- `cron.daily_report` (09:00 workspace timezone)
- `owner.command` (Telegram matn/ovoz)
- `staff.reply` (Telegram)
- `lead.reply` (DM webhook / Telegram)
- `call.finished` (bosqich 6)

## Policy gate (`jarvis/policy.py`)
```python
LEVELS = {
  "send_report":     "autonomous",
  "assign_task":     "autonomous",
  "remind_staff":    "autonomous",
  "escalate_owner":  "autonomous",
  "message_lead":    "requires_approval",   # 2 hafta ijobiy natijadan keyin "autonomous"
  "call_lead":       "requires_approval",
  "change_deal":     "requires_approval",
}
```
`requires_approval` → LangGraph `interrupt()` → Telegram inline tugma (Ha / Yo'q / Tahrirlash).
Ega bitta xabar bilan "hammasiga ha" desa — batch approve.

## Deadline mantiqi
1. Ega buyruqda muddat aytdi → shu.
2. Aytmadi → `workspace.default_sla` (issiq lid: 2 soat, iliq: 24 soat, sovuq: 3 kun).
3. Jarvis egadan so'rashi kerak bo'lsa (noodatiy vazifa) → bitta savol, javob kelmasa default.

## CRM web-sahifa (bosqich 5.8)
Sahifalar:
- **Dashboard** — bugungi lidlar, sotuvlar, xarajat/lid, kampaniyalar ROI (chart)
- **Lidlar** — kanban (yangi → aloqa → uchrashuv → sotuv / yo'qotilgan), filtr: manba, xodim, harorat
- **Lid kartasi** — tarix (contact_event, call_log xulosa + audio), Jarvis xulosasi, vazifalar
- **Vazifalar** — xodim bo'yicha, muddat, kechikkanlar qizil
- **Xodimlar** — yuklama, bajarish %, o'rtacha javob vaqti
- **Kampaniyalar** — Reels → lid → sotuv voronkasi
- **Jarvis jurnali** — barcha `jarvis_action`, tasdiqlanmaganlar

Texnologiya: **Twenty CRM** (docs/07) — yuqoridagi sahifalar Twenty'ning obyekt ko'rinishlari va custom fieldlari bilan quriladi; faqat "Jarvis jurnali" va kampaniya ROI dashboardi bizning FastAPI'da (HTMX). Zaxira: to'liq HTMX CRM.

## Telefon rejimi (bosqich 6) — texnik eslatmalar
- SIP: mahalliy operator biznes SIP trunk (Twilio O'zbekistonda cheklangan). Asterisk/FreeSWITCH yoki LiveKit SIP.
- Pipeline: SIP → LiveKit → STT (nomzodlar: Gemini Live, mahalliy uz STT) → LLM (Sonnet, ≤ 1.2s) → TTS (Azure stream) → SIP.
- Latency nishoni ≤ 1.5s. Barge-in (lid gapirsa Jarvis to'xtaydi).
- Yozib olish va "suhbat yozib olinmoqda" ogohlantirish — qonuniy talab, o'chirma.
- Avval xodimlar, keyin lidlar.
