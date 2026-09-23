# 04 — Agentlar va rubrikalar

Har agent prompti `apps/api/src/engine/agents/prompts/<name>.md` da. Bu yerda rol va chiqish formati.

## Content Engine

| Agent | Model | Kirish | Chiqish |
|---|---|---|---|
| Auditor | Sonnet | IG postlar+insights | `ig_audit.json` (kuchli/zaif, ritm, hook turlari, ranglar) |
| Strategist | Sonnet | audit, brand_profile, taste top-10, metrics | 7 kunlik AIDA reja JSON |
| Writer | Flash/Haiku (1-iter), Sonnet (2–3-iter) | kun rejasi, brand, taste, referens shablon | `{hooks:[3], body, cta, tts_text, scenes:[{img_prompt, dur, subtitle}]}` |
| UzCritic | Sonnet | script | `{score, reasons[], fixes[]}` |
| BrandCritic | Sonnet | script + brand_profile + taste | `{score, reasons[], fixes[]}` |
| HookCritic | Sonnet | hooks + referens kutubxona | `{score, best_hook_idx, reasons[]}` |
| VisionQA | Gemini vision | 6 kadr png | `{pass, issues[{frame, issue}]}` |
| Analyst | Flash | post_metrics | taste_memory yozuvlari ("shu hook turi 2x saves berdi") |

### Rubrika (har kritik 0–10, ≥ 8 o'tadi)
**UzCritic**
- 3 ball: grammatika, sintaksis tabiiy (kalka yo'q: "qilib olish" o'rniga ruscha konstruktsiya emas)
- 2 ball: siz/sen brand_profile'ga mos, hurmat darajasi bir xil
- 2 ball: TTS uchun tayyor: raqamlar so'z bilan, qisqartma yo'q, apostrof normal
- 2 ball: jargon/ruscha so'z faqat brand ruxsat bergan joyda
- 1 ball: subtitr uzunligi ≤ 42 belgi/qator

**BrandCritic**
- 4 ball: ton va CTA uslubi brand_profile bilan mos
- 3 ball: taste_memory'dagi rad sabablari takrorlanmagan
- 3 ball: taqiqlangan so'zlar/mavzular yo'q

**HookCritic**
- 4 ball: 0–3s ichida aniq qiziqish/muammo/va'da
- 3 ball: referens kutubxonadagi ishlagan hook strukturasiga mos
- 3 ball: hook + body uzilmagan (va'da bajarilgan)

## Jarvis

| Agent | Vazifa | Daraja |
|---|---|---|
| Supervisor | eventni agentga yo'naltiradi | — |
| LeadScorer | issiq/iliq/sovuq, manba, keyingi qadam | autonomous |
| Caller | lid bilan kvalifikatsiya (DM/Telegram; bosqich 6 — telefon) | requires_approval → keyin autonomous |
| TaskManager | vazifa, deadline, eslatma, eskalatsiya | autonomous |
| Reporter | kunlik/haftalik hisobot | autonomous |

### Jarvis xulq qoidalari (promptga kiradi)
- O'zini tanishtiradi: "Men Jarvis, {company} virtual yordamchisi".
- Bilmagan narsani uydirmaydi — "buni {staff} bilan aniqlashtiraman".
- Sotuvni yopmaydi, narx va'da bermaydi (agar brand_profile'da ruxsat bo'lmasa).
- Ega bilan qisqa, raqamli: "14 lid / 9 issiq / 3 vazifa muddati o'tdi".
- Xodim bilan hurmatli, aniq muddat bilan, vazifa har doim CRM'da yoziladi.

### Eskalatsiya qoidalari (`jarvis/policy.py`)
- Vazifa muddati o'tdi → 1 soatdan keyin xodimga eslatma; 2-marta o'tsa → egaga xabar.
- Lid 24 soat javobsiz → 2-urinish; 72 soat → `stage=lost`, egaga yozadi.
- Lid savolini Jarvis bilmasa → xodimga uzatadi, lidga "5 daqiqada javob beramiz".
