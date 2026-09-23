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
  styles/                 StyleTheme zod sxemasi, 7 ta tema, getTheme(), resolveLook(tema, brand)
  captions/               5 ta subtitr preseti
```

Hamma animatsiya faqat `spring()` / `interpolate()` bilan yozilgan (CSS keyframes yo'q), `fps`ga bog'liq.
Har bir matn preseti `exitFrame` orqali teskari (mirror) chiqish animatsiyasini qo'llaydi.

## Uslublar (`style`)

| Tema | Shrift | Ranglar | Matn (asosiy / ikkinchi / CTA) | O'tish | FX | Subtitr | Qachon |
|---|---|---|---|---|---|---|---|
| `bold` (standart) | Plus Jakarta Sans 800 | sariq `#FACC15` highlight, docs/08 fon | WordPop / Highlighter / BounceIn | zoomPunch | grain, vignette | karaoke | Universal: mahsulot, xizmat, aksiya |
| `minimal` | Manrope 700, chapga tekis | cyan `#22D3EE` | MaskWipe / TypeWriter / MaskWipe | fade | — | lineByLine | Dizayn, IT, "tinch" brend |
| `neon` | Plus Jakarta 800 | cyan + magenta `#E879F9` | Glitch / Scramble / Outline2Fill | glitchCut | chromatic, glow, particles, grain | bigWord | Tech, gaming, tungi hayot, yoshlar |
| `editorial` | Playfair Display 800 (serif) + Manrope | krem + amber `#F59E0B` | CharCascade / Highlighter / SlideMask | slice | grain, vignette | lineByLine | Moda, kafe, blog, ekspert kontent |
| `corporate` | Manrope 800 | indigo `#6366F1` | SlideMask / Counter / MaskWipe | slide | progressBar | pillGlass | B2B, moliya, ta'lim, klinika |
| `hype` | Anton (katta, UPPERCASE) | sariq + qizil | Kinetic / Counter / BounceIn | whipPan | shake, grain, progressBar | boxHighlight (Hormozi) | Sport, aksiya, "faqat bugun", energiya |
| `luxury` | Playfair Display 600 | qora + oltin `#D4AF37` | BlurFocus (sekin) / CharCascade / BlurFocus | fade 20 kadr | vignette, grain, particles, lensFlare | lineByLine | Zargarlik, parfyum, premium restoran, ko'chmas mulk |

`brand` (brand_profile) bilan birga ishlaydi: docs/08 standartidan **farq qiladigan** brand maydoni
(masalan `accent: "#FF5500"`) temadan ustun turadi, standart qiymatlar esa temaga qoldiriladi.
Noma'lum `style` → `bold`.

Render tezligi (13 s demo, bitta Chromium): bold ≈ 59 s, hype ≈ 55 s, neon ≈ 134 s (glow + zarrachalar).

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

1. **`style`** — `brand_profile.style` dan (yo'q bo'lsa soha bo'yicha: moda/kafe → editorial, premium → luxury,
   B2B/klinika → corporate, sport/aksiya → hype, tech/gaming → neon, dizayn/IT → minimal, qolgani → bold).
   Bir brendning barcha videolari bitta `style`da bo'lishi kerak (izchillik).
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

- Studio: `npm run studio` → **StyleCatalog** kompozitsiyasi (har tema 130 kadr: asosiy + ikkinchi preset, subtitr, fx).
- `npm run render:catalog` → `apps/render/out/catalog/<theme>.png` (scale 0.5). `CATALOG_SAFE=1` xavfsiz zonalarni bo'yab ko'rsatadi.

## Shriftlar va o'zbek ʻ ʼ

Oflayn shriftlar: Plus Jakarta Sans, Manrope, **Playfair Display** va **Anton** (OFL 1.1; Google Fonts
woff2, `apps/render/public/fonts/`). Test (`fonts.test.ts`, `fontsSupportUzbek`) woff2 fayllarining cmap
jadvalini haqiqatda o'qiydi:
Playfair Display va Anton'da ʻ (U+02BB) va ʼ (U+02BC) bor. **Plus Jakarta Sans va Manrope'da yo'q**
(Google `latin` unicode-range ularni ro'yxatda ko'rsatsa ham). Shuning uchun render paytida bu shriftlarda
ular ko'rinishi bir xil ‘ ’ (U+2018/2019) belgilariga almashtiriladi (`uzbekSafe`). Manba matn o'zgarmaydi.

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
