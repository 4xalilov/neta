// BullMQ render worker (roadmap 1.6): queue → Remotion mp4 → MinIO/S3.
//   npm run worker     (node --import tsx src/worker.ts)
import { pathToFileURL } from "node:url";
import { UnrecoverableError, Worker, type Job } from "bullmq";
import { Redis } from "ioredis";
import { InvalidJobError, processRenderJob, type RenderJobData, type RenderJobResult } from "./job";
import { getServeUrl } from "./render";

export const QUEUE_NAME = process.env.RENDER_QUEUE || "render";

/** BullMQ processor. Invalid payloads fail permanently; everything else throws → retry. */
export async function processor(job: Job<RenderJobData, RenderJobResult>): Promise<RenderJobResult> {
  let last = -1;
  try {
    const result = await processRenderJob(job.data, (p) => {
      const pct = Math.floor(p * 100);
      if (pct >= last + 5) {
        last = pct;
        void job.updateProgress(pct);
      }
    });
    console.log(`[render] job ${job.id} ok`, JSON.stringify(result));
    return result;
  } catch (err) {
    console.error(`[render] job ${job.id} failed (attempt ${job.attemptsMade + 1}):`, err);
    if (err instanceof InvalidJobError) throw new UnrecoverableError(err.message);
    throw err;
  }
}

export function startWorker(): Worker<RenderJobData, RenderJobResult> {
  const url = process.env.REDIS_URL || "redis://localhost:6379/0";
  const connection = new Redis(url, { maxRetriesPerRequest: null });
  const worker = new Worker<RenderJobData, RenderJobResult>(QUEUE_NAME, processor, {
    connection,
    concurrency: Number(process.env.RENDER_WORKER_CONCURRENCY || 1),
    // Renders are long; keep the lock alive generously.
    lockDuration: 5 * 60_000,
  });
  worker.on("ready", () => console.log(`[render] worker listening on queue "${QUEUE_NAME}" (${url})`));
  worker.on("error", (err) => console.error("[render] worker error", err));

  const shutdown = async () => {
    console.log("[render] shutting down…");
    await worker.close();
    await connection.quit();
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
  return worker;
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  // Warm the webpack bundle before taking jobs.
  getServeUrl()
    .then((u) => console.log(`[render] bundle ready: ${u}`))
    .catch((e) => console.error("[render] bundling failed", e));
  startWorker();
}
