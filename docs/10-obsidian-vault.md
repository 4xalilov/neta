# 10 — Obsidian vault: ega yozadigan bilim qatlami

Maqsad: ega kod va bazaga tegmasdan, oddiy Markdown bilan brend bilimini, Jarvis qoidalarini va
kontent arxivini boshqaradi. API `vault/` papkasini indekslaydi, agentlar shu bilimdan foydalanadi.
CRM'da esa vault jonli "bilim grafi" sifatida ko'rinadi (marketing uchun chiroyli, mijozga ko'rsatsa bo'ladi).

## Struktura
```
vault/
  README.md                 — qoidalar (qisqa)
  brand/
    profile.md              — ton, siz/sen, register, ranglar (frontmatter → brand_profile)
    products.md             — mahsulot/xizmatlar, narx siyosati
    forbidden.md            — taqiqlangan so'zlar va mavzular
    faq.md                  — tez-tez so'raladigan savollar (Jarvis javoblari)
  jarvis/
    sop/first-message.md    — lidga birinchi xabar
    sop/pricing.md          — narx so'ralsa
    sop/escalation.md       — eskalatsiya
    staff/<ism>.md          — xodim xotirasi (staff_memory)
  content/
    references/<nom>.md     — referens videolar strukturasi
    2026-W39/plan.md        — 7 kunlik AIDA reja
    2026-W39/day-1.md       — ssenariy + ballar + natija (frontmatter)
  reports/
    2026-09-24.md           — Jarvis kunlik hisoboti (avtomatik yoziladi)
  templates/                — Obsidian shablonlari
```

## Frontmatter kelishuvi
```yaml
---
type: brand|sop|staff|reference|plan|script|report
tags: [hook/savol, aida/attention]
updated: 2026-09-24
score: 9          # script uchun
reach: 12400      # nashrdan keyin
---
```
`type` va `tags` grafda rang va guruhni belgilaydi (docs/08 tokenlari: brand=primary, sop=accent, script=success, report=muted).

## Indekslash (`engine/vault/indexer.py`)
- Har 10 daqiqa (arq cron) yoki `POST /v1/vault/reindex`: o'zgargan fayllar (mtime/hash) → bo'laklarga bo'lib embedding → `vault_note` jadvali (path, type, tags, title, links, hash, embedding vector(768)).
- `[[wikilink]]` lar `links` ustunida — graf qirralari shundan quriladi.
- Writer/kritiklar `vault.search(query, types=[...], k=5)` orqali top-k o'qiydi; Jarvis `sop` va `faq` ni promptga to'liq oladi.
- Kunlik hisobot `reports/` ga yoziladi (Jarvis → vault, teskari yo'nalish).

## Jonli graf (`/vault/graph`, roadmap 3.7)
- FastAPI sahifa + WebSocket `/ws/vault`: indekslovchi har o'zgarishda `{event: added|updated|removed, node, links}` yuboradi.
- Force-graph (d3-force yoki `force-graph` kutubxonasi), dark-first docs/08 palitrasi, yangi tugun `spring` bilan "portlab" chiqadi, hover'da sarlavha, click'da yon panelda Markdown.
- Tepada jonli hisoblagichlar: fayllar soni, oxirgi yangilanish, bugungi yangi yozuvlar.
- Sinxron: ega Obsidian'da `obsidian-git` bilan push qiladi → server `git pull` cron → indekslovchi → graf yangilanadi.
