# apps/render — Remotion render worker

Remotion 4 project + BullMQ worker (roadmap 1.5, 1.6; 2.4 stub).
Takes a render job from Redis, renders an MP4 (h264, 1080×1920, 30 fps), uploads it to
MinIO/S3 and returns the object URI as the job result.

```
src/
  index.ts / Root.tsx         registerRoot + <Composition> ReelsBasic, ReelsParallax
  props.ts                    zod props schema, brand defaults (docs/08), demo props
  compositions/               ReelsBasic.tsx, ReelsParallax.tsx
  components/                 Reel (shared layout), KenBurnsImage, ParallaxImage,
                              Subtitles, Background, Logo, CTA
  lib/                        captions (pageWords), kenBurns, timing, metadata, fonts, env
  render.ts                   bundle() once per process → selectComposition → renderMedia
  storage.ts                  S3/MinIO upload (forcePathStyle)
  job.ts                      job schema + processRenderJob()
  worker.ts                   BullMQ Worker (queue $RENDER_QUEUE, default "render")
  enqueue.ts                  manual producer (npm run enqueue)
  renderLocal.ts              npm run render:demo → out/demo.mp4
public/fonts/                 offline brand fonts (Plus Jakarta Sans 800, Manrope)
```

## Scripts

| Command | What |
|---|---|
| `npm run studio` | Remotion Studio (props editable via the zod schema) |
| `npm test` | vitest (`src/__tests__`) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run render:demo` | render `defaultProps` → `out/demo.mp4`, no Redis/S3 needed |
| `npm run worker` | start the BullMQ worker (`node --import tsx src/worker.ts`) |
| `npm run enqueue -- props.json [ReelsParallax] [--wait]` | push a job (bare props or a full job payload) |

`render:demo` env: `DEMO_SECONDS=2` (truncate timeline), `DEMO_COMPOSITION=ReelsParallax`,
`DEMO_PROPS=file.json`, `DEMO_OUT=name.mp4`.

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
  }
}
```

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
