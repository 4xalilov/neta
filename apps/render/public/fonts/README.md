# Offline brand fonts

Remotion loads these with `staticFile()` (see `src/lib/fonts.ts`), so rendering
needs **no network** for fonts. They are the Google Fonts `woff2` subsets
(SIL OFL 1.1 — see `OFL-*.txt`):

| File | Family / weight | Subset | Used by themes |
|---|---|---|---|
| `PlusJakartaSans-800-latin.woff2` | Plus Jakarta Sans, variable 200–800 | latin | bold, neon (display), hype (captions) |
| `PlusJakartaSans-800-latin-ext.woff2` | Plus Jakarta Sans, variable 200–800 | latin-ext | |
| `Manrope-var-latin.woff2` | Manrope, variable 200–800 | latin | minimal, corporate, body text everywhere |
| `Manrope-var-latin-ext.woff2` | Manrope | latin-ext | |
| `Manrope-var-cyrillic.woff2` | Manrope | cyrillic | |
| `PlayfairDisplay-var-latin.woff2` | Playfair Display, variable 400–900 | latin | editorial, luxury |
| `PlayfairDisplay-var-latin-ext.woff2` | Playfair Display | latin-ext | |
| `PlayfairDisplay-var-cyrillic.woff2` | Playfair Display | cyrillic | |
| `Anton-400-latin.woff2` | Anton 400 (condensed poster) | latin | hype |
| `Anton-400-latin-ext.woff2` | Anton 400 | latin-ext | |

## Uzbek ʻ (U+02BB) / ʼ (U+02BC)

Checked against the actual `cmap` of each file by `src/__tests__/fonts.test.ts`
(`fontsSupportUzbek`):

| Family | ʻ ʼ natively | Rendering |
|---|---|---|
| Playfair Display | yes | as-is |
| Anton | yes | as-is |
| Plus Jakarta Sans | **no** | `uzbekSafe()` paints ‘ ’ (U+2018/2019, which these fonts have) |
| Manrope | **no** | same |

Google's `latin` unicode-range lists U+02BB–02BC, but Plus Jakarta Sans and
Manrope don't actually contain those glyphs. Without the swap the browser would
draw them from a fallback font with a different weight. Only the painted glyph
changes: the text in props and `script.tts_text` stays the same.

To refresh or add a family, download from Google Fonts
(`fonts.googleapis.com/css2?family=…` with a browser User-Agent lists the
per-subset woff2 URLs on fonts.gstatic.com; license text is in the
`@fontsource/<family>` npm package). Register the files in `LOCAL_FONTS` and
`FONT_UZ_GLYPHS` in `src/lib/fonts.ts`. The fonts test fails until
`FONT_UZ_GLYPHS` matches the files. If a family has no local files, the
compositions fall back to `@remotion/google-fonts` (downloads at render time,
fine in production but not in offline CI).
