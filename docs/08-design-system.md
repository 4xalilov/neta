# 08 — Dizayn tizimi (barcha "oynalar" uchun yagona manba)

Yuzalar: (1) Telegram bot ekranlari, (2) Remotion Reels 1080×1920, (3) Twenty CRM / Chatwoot brendlash,
(4) kelajakdagi web-dashboard / Telegram Mini App. Hammasi shu tokenlardan foydalanadi.

## Uslub
Dark-first "AI SaaS": qora-ko'k fon, bitta yorqin aksent, yumshoq shisha kartalar, minimal chiziqlar.
Reels: qora/ko'k gradient fon, sariq so'z-highlight subtitr (TikTok uslubi), Ken Burns rasm harakati.

## Rang tokenlari
| Token | Hex | Ishlatilishi |
|---|---|---|
| `bg` | `#0B0F19` | asosiy fon |
| `surface` | `#131A2A` | karta, panel |
| `surface2` | `#1B2438` | hover, ikkinchi qatlam |
| `border` | `#26304A` | chiziqlar |
| `text` | `#E6EAF2` | asosiy matn |
| `muted` | `#8B95AD` | ikkinchi darajali matn |
| `primary` | `#6366F1` | asosiy aksent (indigo) |
| `accent` | `#22D3EE` | ikkinchi aksent (cyan) |
| `success` | `#10B981` | tasdiq, bajarildi |
| `warning` | `#F59E0B` | muddat yaqin |
| `danger` | `#EF4444` | kechikdi, xato |
| `subtitle` | `#FACC15` | Reels faol so'z (sariq), qora kontur |

Manbalar: https://www.realtimecolors.com/ , https://uicolors.app/generate , https://www.radix-ui.com/colors

## Shriftlar
- UI: **Manrope** (kirill + lotin, avto-apostrof) — https://fonts.google.com/specimen/Manrope
- Sarlavha / Reels: **Plus Jakarta Sans** 800 — https://fonts.google.com/specimen/Plus+Jakarta+Sans
- Zaxira: Inter. Remotion konteynerida shriftlar `apps/render/public/fonts/` ga offline yuklanadi
  (https://gwfh.mranftl.com/fonts/manrope?subsets=latin).
- ʻ (U+02BB) va ʼ (U+02BC) belgilarini shrift qo'llashi majburiy — render testida tekshiriladi.

## Telegram bot ekranlari (aiogram 3)
Qoidalar: har xabar ≤ 6 qator, birinchi qator qalin sarlavha + emoji, raqamlar aniq,
inline tugmalar 2–3 ta/qator, har doim "◀️ Orqaga" yoki "❌ Bekor", callback_data ≤ 64 bayt ASCII,
xabarni o'chirib yubormasdan `edit_message_text` bilan yangilash, har callback'ga `answer()`.
Ekranlar:
1. `/start` — ega ro'yxatdan o'tadi → workspace yaratiladi → menyu.
2. **Menyu** — 📝 Brif · 📅 Reja · 📊 Hisobot · ⚙️ Sozlamalar.
3. **Brif** — `/brief <matn>` yoki matn kiritish → "⏳ Ssenariy yozilmoqda… (~2 daq)" progress xabari tahrirlanib boradi.
4. **Ssenariy tasdiq** — hook (3 variant, radio tugma), body, CTA, kritik ballari (🇺🇿 9 · 🎯 8 · 🪝 7) → ✅ Tasdiq · ✏️ Tahrir · 🔄 Qayta · ❌ Bekor.
5. **Video tasdiq** — video + xarajat ($0.18) + VisionQA natijasi → ✅ Nashr · 🕒 Rejalashtir · ❌ Rad (sabab so'raladi → taste_memory).
6. **Jarvis hisobot** — "14 lid / 9 issiq / 3 muddat o'tdi" + tugmalar: ✉️ Hammasiga yoz · 👤 Xodimga eslat.
7. **Tasdiq so'rovi** (requires_approval) — harakat tavsifi → ✅ Ha · ❌ Yo'q · ✏️ Tahrir.
Havolalar: https://core.telegram.org/bots/features , https://papercraft.tmat.me/book/messages/buttons

## Remotion Reels tokenlari (`brand` prop)
```json
{ "font": "Plus Jakarta Sans", "color": "#E6EAF2", "accent": "#FACC15", "bg": "#0B0F19", "logoUrl": null }
```
- Kompozitsiya 1080×1920, 30 fps. Subtitr: so'zma-so'z, faol so'z `accent` rangda, 2 qator ≤ 42 belgi,
  pastdan 22% balandlikda (Instagram UI ustiga tushmasin), qora kontur 6px, `spring()` pop-in.
- Rasm: Ken Burns (scale 1.0→1.12, 4–6 s), sahnalar orasida `@remotion/transitions` fade 12 kadr.
- Havolalar: https://www.remotion.dev/templates/tiktok , https://www.remotion.dev/docs/transitions/ ,
  https://www.remotion.dev/docs/spring , https://remotion-bits.dev/docs/bits/ken-burns/

## Web / Mini App (bosqich 5.8, 7)
shadcn/ui + Tailwind + Motion; grafiklar Tremor bloklari; ikonkalar Lucide. Mini App'da `--tg-theme-*` o'zgaruvchilari.
https://ui.shadcn.com/blocks , https://blocks.tremor.so/ , https://motion.dev/ , https://docs.telegram-mini-apps.com/platform/theming
