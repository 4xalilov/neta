import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { z } from "zod";
import { COMPOSITION_IDS } from "./lib/compositions";
import { reelsPropsSchema } from "./props";
import { renderReel } from "./render";
import { uploadFile } from "./storage";

/** BullMQ job `data` (see README "Job format"). */
export const renderJobSchema = z.object({
  jobId: z.string().min(1),
  workspaceId: z.string().min(1),
  composition: z.enum(COMPOSITION_IDS).default("ReelsBasic"),
  props: reelsPropsSchema,
  /** Object key inside S3_BUCKET, e.g. "renders/<workspace>/<job>.mp4". */
  outputKey: z.string().min(1).refine((k) => !k.startsWith("/"), "outputKey must not start with /"),
});
export type RenderJobData = z.input<typeof renderJobSchema>;

/** BullMQ job `returnvalue`. */
export interface RenderJobResult {
  videoUri: string;
  durationS: number;
  sizeBytes: number;
  renderMs: number;
}

export class InvalidJobError extends Error {
  override name = "InvalidJobError";
}

/** Validate → render to a temp file → upload → clean up. Throws on failure. */
export async function processRenderJob(
  raw: unknown,
  onProgress?: (progress: number) => void,
): Promise<RenderJobResult> {
  const parsed = renderJobSchema.safeParse(raw);
  if (!parsed.success) {
    throw new InvalidJobError(`Invalid render job: ${parsed.error.message}`);
  }
  const data = parsed.data;
  const dir = await mkdtemp(path.join(os.tmpdir(), `render-${data.jobId.replace(/[^\w-]/g, "_")}-`));
  const outputPath = path.join(dir, "out.mp4");
  const t0 = Date.now();
  try {
    const rendered = await renderReel({
      composition: data.composition,
      props: data.props,
      outputPath,
      onProgress,
    });
    const renderMs = Date.now() - t0;
    const { uri, sizeBytes } = await uploadFile(outputPath, data.outputKey);
    return {
      videoUri: uri,
      durationS: +rendered.durationS.toFixed(3),
      sizeBytes,
      renderMs,
    };
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}
