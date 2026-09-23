# Offline brand fonts

Remotion loads these with `staticFile()` (see `src/lib/fonts.ts`), so rendering
needs **no network** for fonts. They are the Google Fonts `woff2` subsets
(SIL OFL 1.1 — see `OFL-*.txt`):

| File | Family / weight | Subset |
|---|---|---|
| `PlusJakartaSans-800-latin.woff2` | Plus Jakarta Sans 800 (Reels headline/captions) | latin (includes Uzbek ʻ U+02BB, ʼ U+02BC) |
| `PlusJakartaSans-800-latin-ext.woff2` | Plus Jakarta Sans 800 | latin-ext |
| `Manrope-var-latin.woff2` | Manrope 200–800 (variable) | latin |
| `Manrope-var-latin-ext.woff2` | Manrope 200–800 (variable) | latin-ext |
| `Manrope-var-cyrillic.woff2` | Manrope 200–800 (variable) | cyrillic |

To refresh or add a family, download from Google Fonts / https://gwfh.mranftl.com/fonts
(`woff2`, subsets latin + latin-ext [+ cyrillic]) and register the files in
`LOCAL_FONTS` in `src/lib/fonts.ts`. If a family has no local files, the
compositions fall back to `@remotion/google-fonts` (downloads from
fonts.gstatic.com at render time — OK in production, not in offline CI).
