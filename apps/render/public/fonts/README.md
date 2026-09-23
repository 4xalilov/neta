# Offline fonts

Remotion loads these with `staticFile()` (see `src/lib/fonts.ts`), so rendering
needs **no network** for fonts. All 28 families are SIL OFL 1.1 (`OFL-<Family>.txt`
next to the files), taken from Google Fonts / Fontsource (`@fontsource-variable/*`,
`@fontsource/*` npm packages): `latin` + `latin-ext`, plus `cyrillic` and
`cyrillic-ext` (Uzbek Cyrillic Қ Ғ Ҳ) where the family has them. `var` files are
variable fonts (the weight column is the wght range); `400`/`700` files are static.
Not taken: Roboto Slab (Apache 2.0, not OFL) and Orbitron (no « » guillemets).

| Family | Weights | Files (subsets) | ʻ U+02BB | ʼ U+02BC | Uzbek Cyrillic | Themes |
|---|---|---|---|---|---|---|
| Plus Jakarta Sans | 200 800 | `PlusJakartaSans-800-*` (latin, latin-ext) | **no** → ‘ ’ | **no** → ‘ ’ | no | bold, hype, neon |
| Manrope | 200 800 | `Manrope-var-*` (latin, latin-ext, cyrillic) | **no** → ‘ ’ | **no** → ‘ ’ | no | bold, corporate, minimal, editorial, neon, luxury, suzani-red |
| Playfair Display | 400 900 | `PlayfairDisplay-var-*` (latin, latin-ext, cyrillic) | yes | yes | no | editorial, luxury, ramadan-night |
| Anton | 400 | `Anton-400-*` (latin, latin-ext) | yes | yes | no | hype |
| Bangers | 400 | `Bangers-400-*` (latin, latin-ext) | **no** → ‘ ’ | **no** → ‘ ’ | no | comic |
| Bebas Neue | 400 | `BebasNeue-400-*` (latin, latin-ext) | **no** → ‘ ’ | yes | no | noir, fitness-energy |
| Caveat | 400 700 | `Caveat-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | **no** → ‘ ’ | yes | yes | handwritten |
| Comfortaa | 300 700 | `Comfortaa-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | yes | yes | no | pastel |
| Cormorant Garamond | 300 700 | `CormorantGaramond-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | yes | yes | yes | dark-gold, beauty-soft |
| DM Serif Display | 400 | `DMSerifDisplay-400-*` (latin, latin-ext) | **no** → ‘ ’ | **no** → ‘ ’ | no | magazine-serif, suzani-red |
| Exo 2 | 100 900 | `Exo2-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | yes | yes | yes | cyber |
| Fraunces | 100 900 | `Fraunces-var-*` (latin, latin-ext) | **no** → ‘ ’ | yes | no | cafe-cream, nature |
| Fredoka | 300 700 | `Fredoka-var-*` (latin, latin-ext) | **no** → ‘ ’ | **no** → ‘ ’ | no | kids |
| Inter | 100 900 | `Inter-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | yes | yes | yes | sport-energy, medical-clean, swiss, tech-blue, academic, noir, earth, registan-blue, instagram-gradient, telegram-blue, estate-clean, fintech-gradient, glass |
| JetBrains Mono | 100 800 | `JetBrainsMono-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | **no** → ‘ ’ | yes | no | mono-kinetic, glitch-dark |
| Lora | 400 700 | `Lora-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | yes | yes | yes | academic, cafe-cream |
| Montserrat | 100 900 | `Montserrat-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | yes | yes | yes | magazine-serif, synthwave, dark-gold, navruz, ramadan-night, registan-blue, tiktok-dark, fintech-gradient, fitness-energy, beauty-soft |
| Nunito | 200 1000 | `Nunito-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | yes | yes | yes | comic, nature, candy, handwritten, kids, pastel, navruz |
| Oswald | 200 700 | `Oswald-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | yes | yes | yes | sport-energy, earth |
| Pacifico | 400 | `Pacifico-400-*` (latin, latin-ext, cyrillic, cyrillic-ext) | **no** → ‘ ’ | yes | yes | food-warm |
| PT Serif | 400 + 700 | `PTSerif-400, PTSerif-700-*` (latin, latin-ext, cyrillic, cyrillic-ext) | **no** → ‘ ’ | yes | yes | newspaper |
| Rubik | 300 900 | `Rubik-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | **no** → ‘ ’ | yes | no | sticker, medical-clean, glitch-dark, food-warm, bazaar-warm, telegram-blue |
| Russo One | 400 | `RussoOne-400-*` (latin, latin-ext, cyrillic) | **no** → ‘ ’ | **no** → ‘ ’ | no | synthwave |
| Space Grotesk | 300 700 | `SpaceGrotesk-var-*` (latin, latin-ext) | yes | yes | no | y2k, tech-blue, glass |
| Syne | 400 800 | `Syne-var-*` (latin, latin-ext) | **no** → ‘ ’ | **no** → ‘ ’ | no | y2k, instagram-gradient |
| Tenor Sans | 400 | `TenorSans-400-*` (latin, latin-ext, cyrillic) | **no** → ‘ ’ | yes | no | jewel, estate-clean |
| Unbounded | 200 900 | `Unbounded-var-*` (latin, latin-ext, cyrillic, cyrillic-ext) | yes | yes | no | sticker, bazaar-warm |
| Yeseva One | 400 | `YesevaOne-400-*` (latin, latin-ext, cyrillic, cyrillic-ext) | **no** → ‘ ’ | yes | no | jewel |


## Uzbek ʻ (U+02BB) / ʼ (U+02BC)

Checked per glyph against the actual `cmap` of each file by
`src/__tests__/fonts.test.ts` and `npm run theme:validate` (`src/lib/woff2.ts`).
Google's `latin` unicode-range lists U+02BB–02BC for every family, but many files
don't contain them. A missing glyph is painted as the visually identical ‘ / ’
(U+2018 / U+2019, which every family here has) by `uzbekSafe()` — per glyph, so a
font with ʼ but no ʻ keeps its own ʼ. Without the swap the browser would draw the
letter from a fallback font with a different weight. Only the painted glyph changes:
the text in props and `script.tts_text` stays the same.

## Adding a family

Download the woff2 subsets (`npm pack @fontsource-variable/<family>` or
`@fontsource/<family>`; `files/<family>-<subset>-wght-normal.woff2`) and the
`LICENSE` as `OFL-<Family>.txt`, register them in `LOCAL_FONTS` and
`FONT_UZ_GLYPHS` in `src/lib/fonts.ts`. The fonts test fails until
`FONT_UZ_GLYPHS` matches the files and the licence is OFL. If a family has no
local files, the compositions fall back to `@remotion/google-fonts` (downloads at
render time — fine in production, not in offline CI; `theme:validate` reports
`font_network` / `font_unavailable`).
