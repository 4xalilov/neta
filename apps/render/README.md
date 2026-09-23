# apps/render — Remotion render worker

Remotion 4 project + BullMQ worker (roadmap 1.5, 1.6; 2.4 stub).
Takes a render job from Redis, renders an MP4 (h264, 1080×1920, 30 fps), uploads it to
MinIO/S3 and returns the object URI as the job result.

```
src/
  index.ts / Root.tsx         registerRoot + <Composition> ReelsBasic, ReelsParallax, StyleCatalog
  props.ts                    zod props schema, brand defaults (docs/08), demo props
  compositions/               ReelsBasic.tsx, ReelsParallax.tsx, StyleCatalog.tsx (review), CatalogSheet.tsx (contact sheet)
  components/                 Reel (shared themed layout), Headline, CTA, KenBurnsImage,
                              ParallaxImage, ThemeBackground, Background, Subtitles, Logo
  motion/                     motion library (docs/11-motion-library.md):
    easings.ts timing.ts        expo/back/anticipate/overshoot curves, spring presets, stagger/presence
    text/                       14 text-reveal presets + registry (WordPop, Kinetic, Counter…)
    fx/                         Vignette, FilmGrain, LightLeak, Shake, ChromaticAberration, Glow,
                                ProgressBar, Particles, GradientMesh, LensFlare
    transitions/                zoomPunch, whipPan, glitchCut, maskCircle, slice + built-ins, pickTransition()
    layout/                     SafeArea (IG safe zones), LowerThird, Chip/Badge, Card, Divider, ImageFrame
    styles/                     StyleTheme zod schema, themes/*.json (45 themes as DATA) + generated themes/index.ts,
                                registry (getTheme, pickTheme), resolveLook(theme, brand), contrast (WCAG), patterns
    captions/                   caption presets karaoke / boxHighlight / pillGlass / bigWord / lineByLine
  lib/                        captions (pageWords), kenBurns, timing, metadata, fonts, env,
                              woff2/fontFiles (cmap glyph checks), themeFiles, themeValidate, stills (Node-side)
  cli/                        themesIndex.ts, themesSchema.ts, validateTheme.ts
  render.ts                   bundle() once per process → selectComposition → renderMedia
  storage.ts                  S3/MinIO upload (forcePathStyle)
  job.ts                      job schema + processRenderJob()
  worker.ts                   BullMQ Worker (queue $RENDER_QUEUE, default "render")
  enqueue.ts                  manual producer (npm run enqueue)
  renderLocal.ts              npm run render:demo → out/demo.mp4
  renderCatalog.ts            npm run render:catalog → out/catalog/<theme>.png + out/catalog/_sheet.png
schemas/style-theme.schema.json   JSON Schema of a theme (generated; the Python side validates candidates with it)
public/fonts/                 28 offline OFL font families (see public/fonts/README.md)
```

## Scripts

| Command | What |
|---|---|
| `npm run studio` | Remotion Studio (props editable via the zod schema) |
| `npm test` | vitest (`src/__tests__`) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run render:demo` | render `defaultProps` → `out/demo.mp4`, no Redis/S3 needed |
| `npm run render:catalog` | one PNG still per StyleTheme → `out/catalog/<theme>.png` (scale 0.5, 540×960) + contact sheet `out/catalog/_sheet.png` (6 columns) |
| `npm run themes:index` | regenerate `src/motion/styles/themes/index.ts` from the `*.json` files (`-- --check`: fail if stale) |
| `npm run themes:schema` | write `schemas/style-theme.schema.json` (JSON Schema draft 2020-12; `-- --check`) |
| `npm run theme:validate -- <theme.json> [--still out.png] [--no-still]` | render-side quality gate for a theme candidate (see below) |
| `npm run worker` | start the BullMQ worker (`node --import tsx src/worker.ts`) |
| `npm run enqueue -- props.json [ReelsParallax] [--wait]` | push a job (bare props or a full job payload) |

`render:demo` env: `DEMO_SECONDS=2` (truncate timeline), `DEMO_COMPOSITION=ReelsParallax`,
`DEMO_PROPS=file.json`, `DEMO_OUT=name.mp4`.

`render:catalog` env: `CATALOG_THEMES=bold,neon` (subset), `CATALOG_SCALE=0.5`,
`CATALOG_FRAME=100` (frame inside each 130-frame theme segment), `CATALOG_SAFE=1`
(paints the Instagram unsafe zones; writes `<theme>-safe.png`), `CATALOG_SHEET=0` (skip the sheet),
`CATALOG_CONCURRENCY=1` (parallel tabs are not faster here). One bundle + one browser for the whole run:
45 stills ≈ 35 s + sheet ≈ 2.5 s. It uses the same `REMOTION_BROWSER` / `REMOTION_CHROME_MODE` handling as the worker:

```bash
REMOTION_BROWSER=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run render:catalog
```

In Studio, the **StyleCatalog** composition plays every theme for 130 frames, showing its hook preset,
its secondary preset, caption preset, fx stack and default transition over a demo scene. **CatalogSheet**
shows all of them at once (frame 100, 6-column grid).

## Themes are data (roadmap 2.8)

Every theme is `src/motion/styles/themes/<name>.json`, validated with the zod `StyleTheme` schema when the
registry loads (`src/motion/styles/registry.ts`); `getTheme(name)` is unchanged (unknown → `bold`). The list
of imports lives in the generated `themes/index.ts` (explicit JSON imports — works in Remotion's webpack,
vitest and tsx). Catalog, families, moods, niches and AIDA fit: docs/11-motion-library.md.

**Add a theme**

1. Copy a similar JSON to `src/motion/styles/themes/<name>.json` (`name` = file name, `a-z0-9-`), fill `meta`.
2. `npm run themes:index`
3. `npm run theme:validate -- src/motion/styles/themes/<name>.json` and look at the still it prints.
4. `npm test` (registry, contrast, fonts, index freshness) and `npm run render:catalog`.

A new font: put the woff2 subsets + `OFL-<Family>.txt` in `public/fonts/`, register it in `LOCAL_FONTS` and
`FONT_UZ_GLYPHS` (`src/lib/fonts.ts`); `fonts.test.ts` tells you the correct ʻ/ʼ values.

**`theme:validate` contract** — prints one JSON object on stdout (logs on stderr):

```jsonc
// exit 0
{ "ok": true, "name": "navruz-2", "still": "/abs/out/validate/navruz-2.png", "warnings": [ … ], "contrast": [ { "pair": "text/bg", "ratio": 13.6, "min": 4.5, "ok": true }, … ] }
// exit 1 (exit 2 = usage / render error)
{ "ok": false, "name": "navruz-2", "problems": [ { "code": "contrast", "path": "colors", "message": "text/bg: #2A4F5A on #042F3A = 1.61:1 < 4.5:1" } ], "warnings": [ … ], "contrast": [ … ], "still": "/abs/…png" }
```

Problem codes: `json`, `schema` (with `path`), `font_unavailable`, `font_files_missing`, `font_weight`,
`uzbek_table`, `uzbek_glyphs`, `contrast` (text/bg, text/surface, accent/bg, onHighlight/highlight ≥ 4.5;
muted/bg ≥ 3; highlight/bg ≥ 1.25), `anim_duplicate`, `pattern_missing`, `tone_mismatch`, `render`.
Warnings: `font_network`, `no_cyrillic`, `headline_size`, `name_exists`. The still (StyleCatalog frame 100,
540×960; default `out/validate/<name>.png`) is rendered whenever the schema passes, so the Python side can run
VisionQA on it. The core is `validateTheme()` in `src/lib/themeValidate.ts`.

## Environment

| Var | Default | Meaning |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | BullMQ connection |
| `RENDER_QUEUE` | `render` | queue name |
| `S3_ENDPOINT` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` / `S3_BUCKET` | – | MinIO/S3 target (path-style) |
| `S3_REGION` | `us-east-1` | |
| `REMOTION_BROWSER` | – | path to a preinstalled Chrome/Chromium; unset → Remotion's chrome-headless-shell (downloaded by `npx remotion browser ensure`, needs egress to `remotion.media`) |
| `REMOTION_CHROME_MODE` | auto | `chrome-for-testing` when `REMOTION_BROWSER` is set (full Chrome ≥ 132 has no `--headless=old`), else `headless-shell` |
| `REMOTION_SERVE_URL` | – | prebuilt bundle (`npx remotion bundle`) to skip webpack at startup |
| `RENDER_CONCURRENCY` | Remotion default | frames rendered in parallel (browser tabs) |
| `RENDER_WORKER_CONCURRENCY` | `1` | jobs processed in parallel |

Local render with a preinstalled browser (what CI/dev containers do):

```bash
REMOTION_BROWSER=/opt/pw-browsers/chromium-1194/chrome-linux/chrome DEMO_SECONDS=2 npm run render:demo
```

ffmpeg/ffprobe are bundled with Remotion (`@remotion/compositor-linux-x64-*`); use
`npx remotion ffprobe out/demo.mp4` to inspect output.

## Props (`src/props.ts`)

```jsonc
{
  "audioUrl": "https://minio/.../voice.mp3",   // optional / null → silent video
  "cta": "Obuna boʻling!",                      // optional; card slides up in the last 2.5 s
  "scenes": [                                   // ≥ 1
    {
      "imageUrl": "https://…/scene1.png",       // any URL the browser can load (presigned MinIO, data: URI…)
      "depthUrl": "https://…/scene1_depth.png", // optional; ReelsParallax only (white = near)
      "durationS": 4.5,                          // > 0
      "words": [ { "w": "Salom!", "start": 0.12, "end": 0.55 } ],
      "subtitle": "…"                            // optional static caption if the scene has no words
    }
  ],
  "brand": {                                     // every field optional → docs/08 tokens
    "font": "Plus Jakarta Sans", "color": "#E6EAF2", "accent": "#FACC15",
    "bg": "#0B0F19", "surface": "#131A2A", "logoUrl": null
  },

  // ── motion library (all optional; old props render exactly with the "bold" theme) ──
  "style": "bold",                // any catalog theme name (docs/11, 45 themes); unknown → bold
  "theme": null,                  // optional FULL StyleTheme object (schemas/style-theme.schema.json, meta optional):
                                  // valid → wins over `style` (DB-approved themes without redeploy); invalid → warning, `style` is used
  "hookText": "Bugun *50%* chegirma", // big hook 0–3 s (scene 0 textAnim or theme.defaultTextAnim)
  "captionPreset": null           // karaoke | boxHighlight | pillGlass | bigWord | lineByLine; null → theme
}
```

Per scene (all optional):

```jsonc
{
  "title": "*1 500 000* soʻm",    // headline for the first 2.5 s of the scene; *stars* = accent/marker word
  "textAnim": "Counter",          // WordPop | CharCascade | MaskWipe | TypeWriter | SlideMask | Glitch | Counter |
                                  // Highlighter | Split3D | Scramble | Kinetic | Outline2Fill | BounceIn | BlurFocus
  "transition": "whipPan",        // INTO this scene: fade | slide | wipe | flip | iris | clockWipe | zoomPunch |
                                  // whipPan | glitchCut | maskCircle | slice | none
  "fx": ["shake", "lightLeak"],   // added to the theme stack: grain | vignette | lightLeak | particles | lensFlare |
                                  // progressBar | shake | chromatic | glow
  "kenBurns": "left",             // in | out | left | right | none
  "captionPreset": "bigWord"      // overrides props/theme preset for this scene's words
}
```

- **Lenient enums**: an unknown `textAnim` / `transition` / `kenBurns` / `captionPreset`
  becomes `null`, which means the theme default. The job does not fail. Unknown
  `fx` names and unknown `style` names (→ `bold`) are ignored the same way. An invalid `theme`
  object is dropped (`null`, warning in the log) and `style` is used.
- **Theme vs brand**: a `brand` field that differs from the docs/08 default was set on
  purpose and wins over the theme (e.g. `style:"neon"` with `brand.accent:"#FF5500"`
  keeps orange). Brand fields left at their defaults take the theme colours and fonts.
- **Text placement**: the hook and titles go in the upper safe area, the CTA card sits above the
  caption band, and captions sit 22 % from the bottom. Everything stays inside the Instagram
  safe zone (top 14 %, bottom 22 %, sides 5 %; `motion/layout/safeArea.ts`). Font size
  is auto-fitted (`fitFontSize`) to the theme's `maxLines`.
- If `hookText` is set, scene 0's `title` is not shown (the hook covers it). A title that
  would overlap the CTA (last 2.5 s) is shortened or dropped.
- Render cost with `REMOTION_BROWSER` Chromium, 13 s demo: bold ≈ 59 s, hype ≈ 55 s,
  neon ≈ 134 s (glow + particles + chromatic bursts).

- `words[].start/end` are **seconds from the composition start** (i.e. the TTS audio
  timeline), not from the scene start. Put each word in the scene during which it is spoken;
  caption pages never span a scene cut.
- Duration = `round(sum(durationS) × 30)` frames (`calculateMetadata`). Scene cross-fades
  (12 frames) are compensated so scene *i* starts exactly at `sum(durationS[<i]) s`.
- Captions: pages of ≤ 2 lines and ≤ 42 chars (≈ 21 per line), broken at word boundaries and
  after pauses > 0.8 s; active word in `brand.accent`, others `brand.color`, 6 px black stroke,
  22 % from the bottom. Text must come from `script.tts_text` (CLAUDE.md).
- Optional fields accept `null` (Python `None`).

## Job format (Redis / BullMQ)

Queue: `$RENDER_QUEUE` (default `render`), keys prefix `bull:render:*`. Job **name**:
`"render"`. Job **data**:

```json
{
  "jobId": "4f0c…",                        // also pass as opts.jobId (idempotent enqueue)
  "workspaceId": "ws_123",
  "composition": "ReelsBasic",             // or "ReelsParallax"; default ReelsBasic
  "props": { …see above… },
  "outputKey": "renders/ws_123/4f0c….mp4"   // key inside S3_BUCKET, no leading "/"
}
```

Job **returnvalue** (on `completed`):

```json
{ "videoUri": "s3://assets/renders/ws_123/4f0c….mp4", "durationS": 15.0, "sizeBytes": 3398211, "renderMs": 48046 }
```

Failures: any render/upload error is thrown → BullMQ retries (use `attempts: 2`). An invalid
payload (schema error) fails immediately with `UnrecoverableError` — `failedReason` starts with
`Invalid render job:`. Progress (0–100) is reported via `job.progress`.

### Python producer (`pip install "bullmq>=3.2"`)

Python `bullmq` 3.x ships the same Lua scripts as Node `bullmq` 6 (this worker); verified
end-to-end with `bullmq==3.2.6` → worker → S3.

```python
from bullmq import Queue, Job

queue = Queue("render", {"connection": settings.REDIS_URL})
job = await queue.add(
    "render",
    {"jobId": job_id, "workspaceId": ws_id, "composition": "ReelsBasic",
     "props": props, "outputKey": f"renders/{ws_id}/{job_id}.mp4"},
    {"jobId": job_id, "attempts": 2, "backoff": {"type": "exponential", "delay": 10000},
     "removeOnComplete": {"age": 604800}, "removeOnFail": {"age": 1209600}},
)
# later / polling:
state = await queue.getJobState(job_id)            # "waiting" | "active" | "completed" | "failed" …
result = (await Job.fromId(queue, job_id)).returnvalue   # dict above when completed
```

(Alternatively `QueueEvents("render", …)` + `job.waitUntilFinished(events)`.)

## Docker

`Dockerfile`: `node:22-bookworm`, Chrome shared libs, `npm ci --omit=dev`,
`npx remotion browser ensure` (downloads chrome-headless-shell at build time into
`node_modules/.remotion`), `CMD node --import tsx src/worker.ts`.
If `remotion.media` is not reachable at build time:
`docker build --build-arg REMOTION_BROWSER=/usr/bin/chromium apps/render` (uses Debian's
chromium). System ffmpeg is optional: `--build-arg WITH_FFMPEG=1`.
