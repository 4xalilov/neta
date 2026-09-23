# 11 — Motion kutubxonasi (Remotion Reels uchun "After Effects" darajasi)

Maqsad: Writer/graph har bir video uchun **`style`** (tema) va har bir sahna uchun **`textAnim`**
tanlaydi. Natija esa professional motion-dizayner qilgandek, bir xil uslubda chiqadi. Kod:
`apps/render/src/motion/` (props: `apps/render/src/props.ts`, to'liq prop tavsifi: `apps/render/README.md`).

```
motion/
  easings.ts  timing.ts   egri chiziqlar (expo/back/anticipate/overshoot), spring presetlari, stagger/presence
  text/                   14 ta matn animatsiyasi + registry (TEXT_PRESETS, meta)
  fx/                     vinyetka, plyonka donasi, light leak, silkinish, xromatik, nur, zarrachalar…
  transitions/            maxsus o'tishlar + @remotion/transitions built-in, pickTransition()
  layout/                 SafeArea (Instagram xavfsiz zonasi), LowerThird, Chip, Card, Divider, ImageFrame
  styles/                 StyleTheme zod sxemasi, themes/*.json (45 ta tema, maʼlumot), registry (getTheme, pickTheme),
                          resolveLook(tema, brand), contrast (WCAG), patterns (fon naqshlari)
  captions/               5 ta subtitr preseti
```

Hamma animatsiya faqat `spring()` / `interpolate()` bilan yozilgan (CSS keyframes yo'q), `fps`ga bog'liq.
Har bir matn preseti `exitFrame` orqali teskari (mirror) chiqish animatsiyasini qo'llaydi.

## Uslublar (`style`) — oʻsib boruvchi katalog (roadmap 2.8)

Temalar **kod emas, maʼlumot**: har biri `apps/render/src/motion/styles/themes/<name>.json` fayli, yuklanishda
zod `StyleTheme` sxemasi bilan tekshiriladi (`styles/registry.ts`). Roʻyxat `themes/index.ts` da aniq importlar
bilan turadi — uni `npm run themes:index` generatsiya qiladi (Remotion webpack bundle, vitest va tsx bir xil
roʻyxatni koʻradi; `import.meta.glob` ishlatilmaydi). `getTheme(name)` API oʻzgarmadi; noma'lum nom → `bold`.

Har tema: shriftlar (sarlavha/matn, ofline), docs/08 rang rollari (`bg surface text muted primary accent
highlight onHighlight`), `tone` (`dark` | `light` — yorugʻ temalarda scrim va kontur qora emas, `bg` rangida),
subtitr preseti + uslubi, matn animatsiyalari (asosiy / ikkinchi / CTA), oʻtish, fx steki, fon
(`brand | mesh | solid | gradient | pattern`), sarlavha oʻlchamlari, karta, Ken Burns, temp va **`meta`**:

```jsonc
"meta": {
  "family": "uzbek",                     // bold|minimal|editorial|neon|luxury|warm|playful|uzbek|social|finance|fitness|beauty
  "mood": ["festive", "springlike"],     // inglizcha teglar
  "niches": ["holiday-promo", "restaurant"],
  "aida": ["attention", "desire"],       // qaysi AIDA bosqichiga mos
  "description_uz": "Navroʻz bayrami: …", // Writer / ega uchun izoh
  "since": "2026-09"                     // katalog versiyasi
}
```

Fon naqshlari (`background.pattern`, SVG/CSS bilan chizilgan, rasm fayli yoʻq): `ikat` (abr), `adras`, `suzani`,
`girih` (Samarqand yulduz toʻri), `stars` (hilol + yulduz), `dots`, `grid`, `lines`, `stripes`, `halftone`,
`confetti`, `scanlines`, `paper`, `retroGrid` (synthwave ufq + quyosh), `waves`.

### Katalog: 45 ta tema

☀ = yorugʻ (`tone: "light"`), (BOSH) = katta harflar. AIDA: A = attention, I = interest, D = desire, Ac = action.
Kontakt varaq: `npm run render:catalog` → `apps/render/out/catalog/_sheet.png`.

**Bold / Hype**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `bold` | Plus Jakarta Sans / Manrope | `#0B0F19` · `#FACC15` · brand | WordPop / Highlighter / BounceIn | zoomPunch | grain, vignette | karaoke | energetic, confident | retail, services, promo, universal | A Ac |
| `hype` | Anton (BOSH) / Plus Jakarta Sans | `#0A0A0A` · `#FACC15` · brand | Kinetic / Counter / BounceIn | whipPan | shake, grain, progressBar | boxHighlight | energetic, urgent, loud | sport, sale, events, fast-promo | A Ac |
| `comic` ☀ | Bangers (BOSH) / Nunito | `#FFF1B8` · `#C8101F` · halftone naqsh | Split3D / Highlighter / BounceIn | zoomPunch | shake | bigWord | funny, loud, bright | kids, games, snacks, education-fun | A |
| `sport-energy` | Oswald (BOSH) / Inter | `#06121F` · `#D7FF1F` · stripes naqsh | WordPop / Counter / Outline2Fill | whipPan | shake, progressBar, grain | boxHighlight | energetic, competitive, fast | sport-club, sportswear, marathon, esports | A Ac |
| `sticker` | Unbounded / Rubik | `#1A1033` · `#B6F23B` · confetti naqsh | BounceIn / Highlighter / Outline2Fill | maskCircle | grain | boxHighlight | playful, loud, youthful | streetwear, youth, cafe, events | A I |
| `y2k` | Syne (BOSH) / Space Grotesk | `#0D0221` · `#FF77E9` · mesh | Outline2Fill / Scramble / BounceIn | flip | chromatic, particles, grain | pillGlass | retro, playful, trendy | fashion, music, streetwear, beauty | A I |

**Minimal / Corporate**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `corporate` | Manrope / Manrope | `#0B0F19` · `#818CF8` · brand | SlideMask / Counter / MaskWipe | slide | progressBar | pillGlass | trustworthy, professional | b2b, finance, education, clinic | I D |
| `minimal` | Manrope / Manrope | `#0E1116` · `#22D3EE` · solid | MaskWipe / TypeWriter / MaskWipe | fade | — | lineByLine | calm, modern | design, it, architecture, consulting | I D |
| `medical-clean` ☀ | Rubik / Inter | `#EFF8F9` · `#0F766E` · gradient | MaskWipe / Counter / SlideMask | slide | progressBar | pillGlass | trustworthy, calm, clean | clinic, dentistry, pharmacy, laboratory | I D |
| `mono-kinetic` | JetBrains Mono (BOSH) / JetBrains Mono | `#0A0A0A` · `#FFFFFF` · solid | Kinetic / TypeWriter / Split3D | none | grain | boxHighlight | minimal, rhythmic, raw | agency, podcast, tech, personal-brand | A I |
| `swiss` ☀ | Inter / Inter | `#F4F4EF` · `#C8000F` · grid naqsh | SlideMask / Highlighter / MaskWipe | wipe | — | lineByLine | rational, clean, bold | design-studio, architecture, agency, b2b | I D |
| `tech-blue` | Space Grotesk / Inter | `#030B1F` · `#38BDF8` · grid naqsh | Scramble / Counter / MaskWipe | maskCircle | progressBar, vignette | boxHighlight | smart, modern, precise | it, saas, startup, edtech | I D |

**Editorial**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `editorial` | Playfair Display / Manrope | `#14110F` · `#F59E0B` · solid | CharCascade / Highlighter / SlideMask | slice | grain, vignette | lineByLine | stylish, thoughtful | fashion, cafe, blog, expert | I D |
| `academic` ☀ | Lora / Inter | `#F7F4EC` · `#8C2F39` · lines naqsh | MaskWipe / Counter / SlideMask | fade | — | pillGlass | calm, credible, scholarly | education, courses, tutoring, university | I D |
| `magazine-serif` | DM Serif Display / Montserrat | `#120C10` · `#FF8FA3` · mesh | Split3D / Highlighter / MaskWipe | iris | vignette, lightLeak | karaoke | chic, glossy, confident | fashion, beauty, lifestyle, boutique | I D |
| `newspaper` ☀ | PT Serif / PT Serif | `#F4F1EA` · `#B3121B` · paper naqsh | TypeWriter / Highlighter / SlideMask | flip | grain | lineByLine | serious, informative, classic | news, media, blog, expert | I |

**Neon / Cyber**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `neon` | Plus Jakarta Sans / Manrope | `#05010F` · `#22D3EE` · mesh | Glitch / Scramble / Outline2Fill | glitchCut | chromatic, glow, particles, grain | bigWord | electric, nocturnal, techy | tech, gaming, nightlife, youth | A I |
| `cyber` | Exo 2 (BOSH) / Exo 2 | `#020409` · `#00FFA3` · scanlines naqsh | Scramble / Glitch / TypeWriter | glitchCut | chromatic, glow, grain | boxHighlight | futuristic, edgy, techy | gaming, cybersecurity, it, esports | A I |
| `glitch-dark` | Rubik (BOSH) / JetBrains Mono | `#000000` · `#FF2E63` · solid | Glitch / Kinetic / Scramble | glitchCut | chromatic, shake, grain | bigWord | aggressive, dark, rebellious | music, nightclub, streetwear, gaming | A |
| `synthwave` | Russo One (BOSH) / Montserrat | `#12002B` · `#FF6EC7` · retroGrid naqsh | Split3D / Scramble / Outline2Fill | maskCircle | glow, grain, particles | karaoke | nostalgic, dreamy, retro | music, nightlife, events, gaming | A I |

**Luxury**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `luxury` | Playfair Display / Manrope | `#07070A` · `#D4AF37` · mesh | BlurFocus / CharCascade / BlurFocus | fade | vignette, grain, particles, lensFlare | lineByLine | premium, elegant, slow | jewelry, perfume, premium-restaurant, real-estate | D |
| `dark-gold` | Cormorant Garamond (BOSH) / Montserrat | `#0B0A08` · `#E0B84F` · gradient | CharCascade / BlurFocus / MaskWipe | fade | particles, vignette, lensFlare | karaoke | opulent, exclusive, slow | jewelry, watches, premium-restaurant, hotel | D |
| `jewel` | Yeseva One / Tenor Sans | `#03140F` · `#6EE7B7` · mesh | BlurFocus / Highlighter / CharCascade | fade | particles, lensFlare, vignette | pillGlass | precious, elegant, rich | jewelry, cosmetics, premium-gifts, wedding | D Ac |
| `noir` | Bebas Neue (BOSH) / Inter | `#050505` · `#FF3B4E` · solid | SlideMask / TypeWriter / BlurFocus | iris | grain, vignette | lineByLine | mysterious, cinematic, moody | film, photography, barbershop, perfume | A D |

**Warm / Natural**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `cafe-cream` ☀ | Fraunces / Lora | `#F6EEE3` · `#9C4A1A` · dots naqsh | CharCascade / TypeWriter / SlideMask | fade | grain, lightLeak | lineByLine | cozy, soft, homely | coffee-shop, bakery, bookstore, handmade | I D |
| `earth` | Oswald / Inter | `#1C130E` · `#F59E6B` · gradient | Split3D / Counter / MaskWipe | slide | grain, vignette | karaoke | grounded, honest, warm | construction, furniture, ceramics, tourism | I D |
| `food-warm` | Pacifico / Rubik | `#1A0D05` · `#FFB23F` · gradient | BounceIn / Counter / Highlighter | zoomPunch | lightLeak, grain, vignette | boxHighlight | appetizing, warm, friendly | restaurant, fast-food, bakery, delivery | D Ac |
| `nature` | Fraunces / Nunito | `#0F1A12` · `#A3E635` · waves naqsh | SlideMask / Highlighter / BounceIn | wipe | lightLeak, grain | karaoke | fresh, natural, organic | eco, organic-food, farm, garden | I D |

**Playful**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `candy` | Nunito / Nunito | `#2D0A2E` · `#FF8AD8` · confetti naqsh | WordPop / Outline2Fill / BounceIn | maskCircle | particles, glow | boxHighlight | sweet, vivid, fun | sweets, desserts, cosmetics, toys | A D |
| `handwritten` ☀ | Caveat / Nunito | `#FFFDF6` · `#1D4ED8` · lines naqsh | TypeWriter / Highlighter / MaskWipe | wipe | grain | karaoke | personal, friendly, honest | personal-brand, tutoring, coaching, blog | I |
| `kids` ☀ | Fredoka / Nunito | `#FFF8E1` · `#C8103A` · dots naqsh | BounceIn / Counter / WordPop | flip | particles | bigWord | fun, bright, cheerful | kindergarten, toys, kids-education, kids-clothes | A I |
| `pastel` ☀ | Comfortaa / Nunito | `#FDF2F8` · `#A21CAF` · mesh | WordPop / Split3D / BounceIn | slide | particles | pillGlass | sweet, gentle, dreamy | kids-clothes, gifts, beauty, dessert | I D |

**Oʻzbek madaniyati**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `bazaar-warm` | Unbounded / Rubik | `#2A1004` · `#FFB627` · adras naqsh | Kinetic / Counter / Highlighter | whipPan | lightLeak, grain, shake | boxHighlight | lively, abundant, loud | market, grocery, textile, souvenirs | A Ac |
| `navruz` | Montserrat / Nunito | `#042F3A` · `#FFD166` · ikat naqsh | SlideMask / Highlighter / BounceIn | maskCircle | particles, lightLeak | karaoke | festive, springlike, joyful | holiday-promo, restaurant, retail, tourism | A D |
| `ramadan-night` | Playfair Display / Montserrat | `#0A1030` · `#F2D48A` · stars naqsh | CharCascade / Highlighter / BlurFocus | fade | particles, vignette | lineByLine | serene, spiritual, warm | charity, iftar-restaurant, holiday-greeting, retail | I D |
| `registan-blue` | Montserrat (BOSH) / Inter | `#06184A` · `#5EC8F2` · girih naqsh | SlideMask / Counter / MaskWipe | iris | lensFlare, grain | pillGlass | majestic, proud, calm | tourism, hotel, education, culture | I D |
| `suzani-red` | DM Serif Display / Manrope | `#3A0A0E` · `#FFC857` · suzani naqsh | Outline2Fill / Highlighter / BounceIn | slice | grain, vignette | karaoke | rich, traditional, warm | textile, handmade, wedding, souvenirs | I D |

**Social-native**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `instagram-gradient` | Syne / Inter | `#1A0B2E` · `#FEDA75` · gradient | BounceIn / Highlighter / Outline2Fill | slide | lightLeak | karaoke | trendy, vibrant, social | smm, influencer, online-shop, beauty | A Ac |
| `telegram-blue` ☀ | Rubik / Inter | `#EAF4FC` · `#0B6FB0` · dots naqsh | TypeWriter / Counter / BounceIn | slide | progressBar | pillGlass | friendly, clear, helpful | telegram-channel, news, services, education | I Ac |
| `tiktok-dark` | Montserrat (BOSH) / Montserrat | `#000000` · `#25F4EE` · solid | WordPop / Glitch / BounceIn | zoomPunch | chromatic, shake, progressBar | karaoke | fast, viral, bold | ugc, entertainment, youth, e-commerce | A |

**Koʻchmas mulk / Moliya**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `estate-clean` ☀ | Tenor Sans (BOSH) / Inter | `#F4F6F8` · `#8A6A20` · gradient | MaskWipe / Counter / SlideMask | wipe | — | lineByLine | premium, trustworthy, airy | real-estate, construction, interior, mortgage | I D |
| `fintech-gradient` | Montserrat / Inter | `#070B1E` · `#34D399` · mesh | Split3D / Counter / MaskWipe | clockWipe | progressBar, particles | pillGlass | innovative, secure, smart | bank, fintech, insurance, investing | I D |

**Fitnes**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `fitness-energy` | Bebas Neue (BOSH) / Montserrat | `#0B0B0B` · `#FF6B1A` · gradient | Kinetic / Counter / WordPop | whipPan | shake, grain, progressBar | boxHighlight | intense, motivating, powerful | gym, personal-trainer, nutrition, crossfit | A Ac |

**Goʻzallik**

| Tema | Shrift (sarlavha / matn) | Fon · aksent | Matn (asosiy / ikkinchi / CTA) | Oʻtish | FX | Subtitr | Kayfiyat | Nisha | AIDA |
|---|---|---|---|---|---|---|---|---|---|
| `beauty-soft` ☀ | Cormorant Garamond / Montserrat | `#FBF0EE` · `#A8325E` · mesh | BlurFocus / Highlighter / MaskWipe | fade | lightLeak, particles | lineByLine | soft, feminine, calm | beauty-salon, cosmetics, spa, nails | D |
| `glass` | Space Grotesk / Inter | `#0C1024` · `#7DD3FC` · mesh | BlurFocus / Split3D / Outline2Fill | slide | lensFlare, grain | pillGlass | modern, airy, sleek | cosmetics, gadgets, apps, design | I D |

Asl 7 tema (`bold minimal neon editorial corporate hype luxury`) koʻrinishi saqlangan (faqat `corporate.highlight`
`#6366F1` → `#4F46E5`: oq matn bilan kontrast 4.47 → 6.3).

`brand` (brand_profile) bilan birga ishlaydi: docs/08 standartidan **farq qiladigan** brand maydoni
(masalan `accent: "#FF5500"`) temadan ustun turadi, standart qiymatlar esa temaga qoldiriladi.

### Qayta deploy'siz yangi tema: `props.theme`

Render props'ida ixtiyoriy **`theme`** — toʻliq `StyleTheme` obyekti (masalan `style_theme` jadvalidan
`approved` tema; `meta` bu yerda ixtiyoriy). Toʻgʻri boʻlsa `style` dan ustun turadi; notoʻgʻri boʻlsa
ogohlantirish (`console.warn`) yoziladi va `style` ishlatiladi — job yiqilmaydi (`pickTheme()`).
Shu yoʻl bilan API bundle'da yoʻq temani ham render qila oladi.

### Sifat darvozasi (render tomoni): `npm run theme:validate`

```bash
npm run theme:validate -- candidate.json [--still out.png] [--no-still]
```

stdout'ga bitta JSON chiqaradi (loglar stderr'da), exit 0 = ok, 1 = muammo, 2 = foydalanish/render xatosi:

```jsonc
{"ok": true,  "name": "…", "still": "/abs/out.png", "warnings": [...], "contrast": [...]}
{"ok": false, "name": "…", "problems": [{"code": "contrast", "path": "colors", "message": "text/bg: … 1.61:1 < 4.5:1"}], "still": "…"}
```

Tekshiruvlar (`src/lib/themeValidate.ts`, `validateTheme()`):
- `schema` — JSON Schema / zod (`apps/render/schemas/style-theme.schema.json`, `npm run themes:schema`);
- `font_unavailable`, `font_files_missing`, `font_weight` — shrift ofline bormi, kerakli ogʻirlik bormi;
- `uzbek_table`, `uzbek_glyphs` — ʻ/ʼ jadvali fayllarga mos, oʻzbekcha namuna (`Oʻzbekiston gʻalaba taʼlim … «Yangi»`)
  `uzbekSafe()` dan keyin toʻliq chiziladi; oʻzbek kirill (ў қ ғ ҳ) yoʻq boʻlsa — faqat ogohlantirish;
- `contrast` — WCAG: `text/bg`, `text/surface`, `accent/bg` (subtitr faol soʻzi), `onHighlight/highlight`
  (subtitr qutisi, marker) ≥ 4.5; `muted/bg` ≥ 3; `highlight/bg` ≥ 1.25 (marker fonda koʻrinsin);
- `anim_duplicate`, `pattern_missing`, `tone_mismatch` (qora fon + `light` tone va aksincha).

Sxema oʻtsa, StyleCatalog kadri (540×960) har doim render qilinadi — Python tomoni undan keyin VisionQA
(kuchli vision model, rubrika ≥ 8) ishlatadi.

Render tezligi (13 s demo, bitta Chromium): bold ≈ 59 s, hype ≈ 55 s, neon ≈ 134 s (glow + zarrachalar).
Katalog: 45 kadr ≈ 35 s (≈ 0.8 s/kadr, bitta brauzer) + kontakt varaq ≈ 2.5 s; `theme:validate` bitta kadr bilan ≈ 5 s (bundle kesh bilan).

## Matn animatsiyalari (`textAnim`)

Sarlavhada `*yulduzcha*` bilan kalit so'z belgilanadi (`"Bugun *50%* chegirma"`): u aksent rangda,
Highlighter'da marker ostida bo'ladi. Belgi bo'lmasa Highlighter raqamli yoki eng uzun so'zni tanlaydi.

| Preset | Nima qiladi | AIDA / intent |
|---|---|---|
| `WordPop` | So'zma-so'z scale + blur-in, stagger, motion-blur izi (`@remotion/motion-blur` Trail) | Attention — hook, sarlavha |
| `CharCascade` | Har harf niqob ortidan pastdan ko'tariladi | Interest — sarlavha, iqtibos |
| `MaskWipe` | Aksent chiziq qatorma-qator yurib matnni ochadi | Desire/Action — sarlavha, CTA |
| `TypeWriter` | Harfma-harf yoziladi, miltillovchi kursor | Interest — muammo, savol |
| `SlideMask` | Qatorlar niqob ortidan sirg'alib chiqadi (editorial) | Interest — sarlavha, isbot |
| `Glitch` | 6 kadr RGB-split + titroq, keyin tinchlanadi | Attention — hook (tech/neon) |
| `Counter` | Raqam 0 dan sanaladi, format saqlanadi ("15%", "1 500 000 so'm") | Interest/Desire — isbot, narx |
| `Highlighter` | Kalit so'z ortida marker chiziladi | Interest/Desire — isbot, taklif |
| `Split3D` | So'zlar 3D rotateX bilan yiqilib turadi | Interest — sarlavha, taklif |
| `Scramble` | Tasodifiy belgilar haqiqiy harflarga aylanadi | Attention — hook, "sir" |
| `Kinetic` | Katta-kichik ritm, qalin/ingichka almashadi | Attention/Action — hook, aksiya |
| `Outline2Fill` | Kontur matn, keyin rang bilan to'ladi | Desire/Action — taklif, CTA |
| `BounceIn` | Spring overshoot bilan sakrab kiradi + motion-blur | Action — CTA |
| `BlurFocus` | Sekin fokus: blur 20→0, harf oralig'i torayadi | Desire — premium sarlavha |

Hook turlari bo'yicha: **savol/muammo** → TypeWriter, Glitch · **raqam/natija** → Counter, Kinetic ·
**shok/aksiya** → Kinetic, Glitch, WordPop · **sir/qiziqish** → Scramble · **premium** → BlurFocus, CharCascade.

## O'tishlar (`transition`, sahnaga KIRISH)

| Nomi | Tavsif | Mos |
|---|---|---|
| `zoomPunch` | Eski kadr kameraga otiladi, oq chaqnash, yangi kadr zoom'dan tushadi | bold; hook → interest keskin burilish |
| `whipPan` | Tez gorizontal surilish, yo'nalishli motion-blur (SVG blur "x 0") | hype, energiya, ro'yxat |
| `glitchCut` | Gorizontal tasmalar siljiydi + RGB, 8 kadr | neon, tech |
| `maskCircle` | Aksent halqali doira-niqob ochilishi | mahsulot "reveal", natija |
| `slice` | Vertikal bo'laklar ketma-ket tushadi | editorial, katalog |
| `fade` / `slide` / `wipe` / `flip` / `iris` / `clockWipe` | `@remotion/transitions` built-in (WebGL'siz) | minimal, corporate, luxury |
| `none` | To'g'ridan-to'g'ri kesim | ritmik montaj |

Uzunlik tema bo'yicha (8–20 kadr), qo'shni sahnadan uzun bo'lmaydi. Sahnalar audio vaqt chizig'iga
aniq tushadi (`lib/timing.ts` `transitionList` / `sequenceFramesVar`).

## FX (`fx`)

| Nomi | Tavsif | Mos |
|---|---|---|
| `grain` | Jonli plyonka donasi (`@remotion/noise` + feTurbulence) | deyarli hammasi, "kino" hissi |
| `vignette` | Burchaklar qorayadi, diqqat markazga | luxury, editorial |
| `lightLeak` | Iliq yorug'lik sizishi sahna boshida (CSS; WebGL varianti `@remotion/light-leaks`, WebGL yo'q bo'lsa avtomatik CSS) | lifestyle, kafe, iliq kayfiyat |
| `particles` | Suzuvchi zarrachalar / oltin chang | luxury, neon |
| `lensFlare` | Yengil linza chaqnashi | luxury, quyoshli kadrlar |
| `progressBar` | Tepada ingichka progress chizig'i (retention) | corporate, hype, ta'lim |
| `shake` | Sahna boshida kamera zarbasi + yengil qo'l titrashi | hype, "shok" hook |
| `chromatic` | Kesimda RGB-ajralish portlashi (12 kadr) | neon, glitch |
| `glow` | Sarlavha atrofida neon nur | neon |

Tema fx stekiga sahnaning `fx` ro'yxati **qo'shiladi**; noma'lum nomlar e'tiborga olinmaydi.
Qo'shimcha komponentlar (propsda emas, kompozitsiyalar uchun): `GradientMesh` fon, `LowerThird`,
`Chip/Badge`, `Card` (shisha), `Divider`, `ImageFrame`, `SafeArea` (debug overlay bilan).

## Subtitr presetlari (`captionPreset`)

| Preset | Tavsif | Mos |
|---|---|---|
| `karaoke` | 2 qator, faol so'z aksent rangda + pop (docs/08 standarti) | bold, universal |
| `boxHighlight` | Faol so'z aksent rangli yumaloq quti ichida (Hormozi) | hype, sotuv |
| `pillGlass` | Muzli shisha tabletka fonida, aytilmagan so'zlar xira | corporate, ta'lim |
| `bigWord` | Bir vaqtda bitta ulkan so'z | neon, qisqa kuchli gaplar |
| `lineByLine` | Bitta qator niqobdan chiqadi, pastida aksent chiziq | minimal, editorial, luxury |

Tanlov tartibi: sahna `captionPreset` → props `captionPreset` → `theme.captionPreset`.
Hammasi pastdan 22% da, Instagram UI ustiga tushmaydi.

## Joylashuv (safe area)

Instagram Reels UI: tepa 14%, past 22%, yon 5% (`motion/layout/safeArea.ts`). Hook va sarlavhalar
xavfsiz zonaning yuqori qismida joylashadi. CTA kartasi subtitr bandidan yuqorida, subtitr esa pastdan 22% da turadi.
Shrift o'lchami matn uzunligiga qarab avtomatik kichrayadi (`fitFontSize`, tema `maxLines`).
Sarlavha ostida kontrast uchun yumshoq qora gradient (scrim) chiqadi.

## Writer qanday tanlaydi

1. **`style`** — `brand_profile.style` dan (yo'q bo'lsa katalog `meta` bo'yicha: `niches` soha bilan, `mood`
   brend ohangi bilan, `aida` post maqsadi bilan mos temani tanlaydi; masalan kafe → `cafe-cream`, klinika →
   `medical-clean`, sport zal → `fitness-energy`, bayram → `navruz`/`ramadan-night`, qolgani → bold).
   Bir brendning barcha videolari bitta `style`da bo'lishi kerak (izchillik). Katalogda yo'q, lekin
   tasdiqlangan tema → `theme` (toʻliq obyekt).
2. **`hookText`** — 0–3 s katta hook (≤ 6 so'z, kalit so'z `*…*` da). Animatsiyasi `scenes[0].textAnim`
   yoki tema standarti. `hookText` bo'lsa 0-sahna `title`i ko'rsatilmaydi.
3. **Sahna `title` + `textAnim`** — sahna niyatiga qarab:
   - hook / attention → `WordPop`, `Kinetic`, `Glitch` (`Scramble` sir uchun)
   - muammo → `TypeWriter`, `SlideMask`
   - isbot / raqam → `Counter` (sarlavhada raqam bo'lishi shart), `Highlighter`
   - taklif / desire → `Highlighter`, `Split3D`, `Outline2Fill`, `BlurFocus` (premium)
   - CTA → `BounceIn`, `MaskWipe` (props `cta` kartasi `theme.ctaTextAnim` bilan o'zi chiqadi)
   Bo'sh qoldirilsa tema standarti ishlatiladi, bu har doim to'g'ri tanlov.
4. **`transition`** — odatda bo'sh (tema standarti). Faqat urg'u uchun: natija ko'rsatilishida
   `maskCircle`, keskin burilishda `zoomPunch`, ro'yxatda `whipPan`.
5. **`fx`** — kamdan-kam: "shok" sahnaga `["shake"]`, iliq lifestyle sahnaga `["lightLeak"]`.
6. **`kenBurns`** — keng manzara `left`/`right`, detal/mahsulot `in`, yakuniy umumiy kadr `out`.

Enum qiymat noto'g'ri bo'lsa, props sxemasi uni `null` qiladi (tema standarti ishlatiladi). Render job shu sababli yiqilmaydi.
Sarlavha/hook matnida yulduzchadan tashqari markup ishlatilmaydi. Subtitr matni esa `script.tts_text` dan olinadi.

## Ko'rib chiqish

- Studio: `npm run studio` → **StyleCatalog** (har tema 130 kadr: asosiy + ikkinchi preset, subtitr, fx) va
  **CatalogSheet** (hamma tema 6 ustunli toʻrda, 100-kadrda "muzlatilgan").
- `npm run render:catalog` → `apps/render/out/catalog/<theme>.png` (scale 0.5) + `out/catalog/_sheet.png`
  (kontakt varaq). `CATALOG_THEMES=a,b` qism, `CATALOG_SAFE=1` xavfsiz zonalarni bo'yab ko'rsatadi, `CATALOG_SHEET=0`.

### Yangi tema qo'shish

1. `apps/render/src/motion/styles/themes/<name>.json` (nom = fayl nomi, `a-z0-9-`), mavjud temadan nusxa olish qulay.
2. `npm run themes:index` (index.ts qayta generatsiya).
3. `npm run theme:validate -- src/motion/styles/themes/<name>.json` → `ok: true` va kadrni ko'rib chiqish.
4. `npm test` (katalog, kontrast, shriftlar, index yangiligi), `npm run render:catalog`.

## Shriftlar va o'zbek ʻ ʼ

28 ta ofline shrift oilasi (hammasi SIL OFL 1.1, `apps/render/public/fonts/`, har biriga `OFL-*.txt`):
Plus Jakarta Sans, Manrope, Playfair Display, Anton, Bangers, Bebas Neue, Caveat, Comfortaa, Cormorant Garamond,
DM Serif Display, Exo 2, Fraunces, Fredoka, Inter, JetBrains Mono, Lora, Montserrat, Nunito, Oswald, Pacifico,
PT Serif, Rubik, Russo One, Space Grotesk, Syne, Tenor Sans, Unbounded, Yeseva One (Google Fonts / Fontsource
woff2; iloji bo'lsa `cyrillic` va `cyrillic-ext` — oʻzbek kirill Қ Ғ Ҳ — bilan). Roboto Slab (Apache 2.0) va
Orbitron (« » yoʻq) ataylab olinmadi.

Test (`fonts.test.ts`) va `theme:validate` woff2 fayllarining cmap jadvalini haqiqatda o'qiydi
(`src/lib/woff2.ts`). Jadval `FONT_UZ_GLYPHS` endi **har belgi uchun alohida**: koʻp shriftda ʼ (U+02BC) bor,
lekin ʻ (U+02BB) yoʻq (Rubik, Caveat, Fraunces, PT Serif, Bebas Neue, JetBrains Mono, Pacifico, Tenor Sans,
Yeseva One); Plus Jakarta Sans, Manrope, Bangers, DM Serif Display, Fredoka, Russo One, Syne'da ikkalasi ham
yoʻq; qolganlarida (Playfair, Anton, Inter, Montserrat, Nunito, Oswald, Lora, Exo 2, Cormorant, Comfortaa,
Space Grotesk, Unbounded) ikkalasi bor. Yoʻq belgi render paytida ko'rinishi bir xil ‘ (U+2018) / ’ (U+2019)
ga almashtiriladi (`uzbekSafe`). Manba matn o'zgarmaydi.

## Ko'rib chiqilgan paketlar va litsenziyalar

| Paket | Versiya | Litsenziya | Qaror |
|---|---|---|---|
| `remotion`, `@remotion/transitions`, `@remotion/google-fonts`, `@remotion/light-leaks` (+ `@remotion/effects`) | 4.0.527 | **Remotion License**: jismoniy shaxslar, **≤ 3 xodimli** kompaniyalar va notijorat tashkilotlar uchun (tijoriy ham) bepul; kattaroq tijoriy kompaniyaga **Company License** kerak (remotion.pro) | Ishlatiladi |
| `@remotion/motion-blur` | 4.0.527 | MIT | Ishlatiladi (`Trail`: WordPop, BounceIn) |
| `@remotion/noise` | 4.0.527 | MIT | Ishlatiladi (grain, shake, particles, mesh, light leak) |
| `@remotion/zod-types` | 4.0.527 | MIT | Ishlatiladi (rang maydonlari) |
| `@remotion/shapes`, `@remotion/paths`, `@remotion/animation-utils` | 4.0.527 | MIT | Ko'rib chiqildi, kerak bo'lmadi (marker/doira CSS/SVG bilan yozildi) |
| `@remotion/lottie`, `@remotion/fonts` | 4.0.527 | — | O'rnatilmadi (Lottie asset yo'q; shriftlar o'zimizning FontFace loaderda) |
| `remotion-animated` | 2.2.0 | MIT | Ishlatilmadi: oddiy `<Animated>` wrapper, `spring/interpolate` bilan o'zimiz yozdik |
| `remotion-bits` | 0.2.1 | MIT | Ishlatilmadi: 0.x, `three` + MCP SDK kabi og'ir bog'liqliklar |
| `remotion-captions-themes` | 1.0.8 | MIT (LICENSE fayli; package.json da `license` maydoni yo'q) | Ishlatilmadi: yetilmagan, xom TS manba. G'oyalar (Hormozi box, pill) o'zimizning presetlarda |

Eslatma: Remotion License o'zbek biznesi uchun muhim. Neta 3 kishidan ko'p xodimli tijoriy tashkilotga
aylansa, Remotion Company License sotib olinishi kerak. Bu litsenziya bizning mijozlarimizga
(video buyurtmachilarga) emas, render qiluvchi tomonga (bizga) tegishli.
