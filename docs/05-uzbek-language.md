# 05 — O'zbek tili qoidalari

`engine/uz/normalize.py` shu qoidalarni kodda amalga oshiradi. Testlar `tests/test_uz_normalize.py`.

## 1. Apostrof normalizatsiyasi
Kirish matnda `oʻ gʻ o' g' o‘ g‘ o` g`` uchraydi. Ichki standart: **U+02BB (ʻ)** — `oʻ`, `gʻ`.
Subtitr shrifti ʻ belgisini qo'llashini tekshir (Inter, Manrope — ha).
Tutuq belgisi (`ma'no`, `she'r`) — **U+02BC (ʼ)** ga normalizatsiya.

## 2. TTS uchun matn (`tts_text`)
- Raqamlar so'z bilan: `2026` → "ikki ming yigirma olti", `15%` → "o'n besh foiz", `1 500 000 so'm` → "bir million besh yuz ming so'm".
- Sana: `24-sentyabr` → "yigirma to'rtinchi sentyabr".
- Qisqartmalar ochiladi: `va h.k.` → "va hokazo", `t.r.` → "telefon raqami".
- Chet so'zlar transliteratsiya: `Instagram` → "Instagram" (Azure o'qiydi; agar buzsa → "Instagrám"), `Reels` → "Rils", `AI` → "sun'iy intellekt" yoki "ey-ay" (brand_profile tanlaydi).
- Ruscha so'zlar: agar brand ruxsat bersa lotin transliteratsiyada (`skidka`), aks holda o'zbekcha (`chegirma`).
- Jumla ≤ 18 so'z — TTS intonatsiyasi uchun.

## 3. Subtitr matni (`subtitle_json`)
- `tts_text` bilan bir manba; faqat raqamlar raqam ko'rinishida qoladi (ekranda "15%" chiroyliroq) — buning uchun `tts_text` va `display_text` ikkalasi saqlanadi, timing bir xil.
- ≤ 42 belgi/qator, ≤ 2 qator, so'z chegarasida uziladi.
- So'z darajasidagi timing TTS'ning word-boundary eventidan olinadi (Azure beradi); yo'q bo'lsa `forced alignment` (whisperX) zaxira.

## 4. Uslub tekshiruvi (UzCritic uchun eslatmalar)
- Kalkalar: "qilib chiqamiz" (ok), "amalga oshirishni boshlaymiz" (og'ir → "boshlaymiz").
- Siz/sen — brand_profile.address_form; aralashmaydi.
- Toshkent so'zlashuv uslubi vs adabiy — brand_profile.register: `casual|neutral|formal`.
- Hook uchun ishlaydigan qoliplar: savol ("Nega ... ?"), raqam ("3 ta xato ..."), qarama-qarshilik ("Hamma ... deydi, lekin ...").

## 5. TTS ovoz testi (bosqich 1.2)
`evals/tts_test.md` dagi 20 jumlani har nomzod ovozda sintez qil, ega 1–5 baholaydi:
apostrofli so'zlar, raqamlar, chet so'zlar, savol intonatsiyasi, uzun jumla, tez temp.
