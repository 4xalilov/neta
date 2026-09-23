// Manual test helper: npm run enqueue -- props.json [ReelsBasic|ReelsParallax] [--wait]
import { readFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { pathToFileURL } from "node:url";
import { Job, Queue, QueueEvents } from "bullmq";
import { Redis } from "ioredis";
import type { RenderJobData, RenderJobResult } from "./job";
import type { CompositionId } from "./lib/compositions";

export const DEFAULT_JOB_OPTS = {
  attempts: 2,
  backoff: { type: "exponential", delay: 10_000 },
  removeOnComplete: { age: 7 * 24 * 3600, count: 1000 },
  removeOnFail: { age: 14 * 24 * 3600 },
} as const;

export async function enqueueRender(data: RenderJobData, redisUrl = process.env.REDIS_URL || "redis://localhost:6379/0") {
  const connection = new Redis(redisUrl, { maxRetriesPerRequest: null });
  const queue = new Queue<RenderJobData, RenderJobResult>(process.env.RENDER_QUEUE || "render", { connection });
  try {
    return await queue.add("render", data, { ...DEFAULT_JOB_OPTS, jobId: data.jobId });
  } finally {
    await queue.close();
    await connection.quit();
  }
}

async function main() {
  const args = process.argv.slice(2).filter((a) => a !== "--");
  const file = args.find((a) => !a.startsWith("--"));
  if (!file) {
    console.error("usage: npm run enqueue -- <props.json> [ReelsBasic|ReelsParallax] [--wait]");
    process.exit(2);
  }
  const composition = (args.find((a) => a.startsWith("Reels")) ?? "ReelsBasic") as CompositionId;
  const json = JSON.parse(await readFile(file, "utf8"));
  // Accept either bare props or a full job payload.
  const jobId = json.jobId ?? randomUUID();
  const data: RenderJobData = json.props
    ? json
    : { jobId, workspaceId: "manual", composition, props: json, outputKey: `renders/manual/${jobId}.mp4` };
  const job = await enqueueRender(data);
  console.log(`enqueued job ${job.id} on "${process.env.RENDER_QUEUE || "render"}" → ${data.outputKey}`);

  if (args.includes("--wait")) {
    const connection = new Redis(process.env.REDIS_URL || "redis://localhost:6379/0", { maxRetriesPerRequest: null });
    const name = process.env.RENDER_QUEUE || "render";
    const queue = new Queue<RenderJobData, RenderJobResult>(name, { connection });
    const eventsConnection = connection.duplicate();
    const events = new QueueEvents(name, { connection: eventsConnection });
    try {
      const j = await Job.fromId<RenderJobData, RenderJobResult>(queue, job.id!);
      console.log("result:", await j!.waitUntilFinished(events));
    } finally {
      await events.close();
      await queue.close();
      await eventsConnection.quit();
      await connection.quit();
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
