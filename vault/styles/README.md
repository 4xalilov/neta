---
type: reference
tags: [style, style/catalog]
updated: 2026-09-23
---
# Uslub bilimlar bazasi (docs/03-roadmap.md 2.8)

Har bir `.md` fayl shu papkada — **tasdiqlangan yoki rad etilgan** bitta Reels
uslubi (`StyleTheme`, `style_theme` jadvali): `engine/styles/registry.py`
`write_vault_doc()` orqali avtomatik yoziladi, qo'lda tahrirlanmasin (keyingi
gate/import qayta yozadi).

Haqiqiy manba — Postgres `style_theme` jadvali va `apps/render/src/motion/
styles/`. Bu fayllar faqat **o'qish uchun ko'rinish**: Writer/Jarvis
promptlariga va bilim grafiga (`/vault/graph`, roadmap 3.7) tushishi uchun.

Har hujjatda: holat (`candidate`/`approved`/`rejected`), manba
(`builtin`/`llm`/`owner`/`import`), VisionQA ball, fon/aksent ranglar, ilhom
va (rad etilgan bo'lsa) sabablar. API: `GET /v1/styles`, `POST /v1/styles/
propose`, `POST /v1/styles/{id}/approve|reject`.
