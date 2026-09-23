// Node-side rendering: bundle once per process, then selectComposition + renderMedia.
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import type { CompositionId } from "./lib/compositions";
import { browserOptionsFromEnv } from "./lib/env";
import type { ReelsProps } from "./props";

export const APP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

let bundlePromise: Promise<string> | null = null;

/**
 * Serve URL of the Remotion bundle. Uses REMOTION_SERVE_URL when set (a
 * prebuilt `npx remotion bundle` dir or a hosted bundle), otherwise webpack-
 * bundles src/index.ts once and caches the promise for the process lifetime.
 */
export function getServeUrl(): Promise<string> {
  if (process.env.REMOTION_SERVE_URL) return Promise.resolve(process.env.REMOTION_SERVE_URL);
  if (!bundlePromise) {
    bundlePromise = bundle({
      entryPoint: path.join(APP_ROOT, "src/index.ts"),
      rootDir: APP_ROOT,
      publicDir: path.join(APP_ROOT, "public"),
    }).catch((err) => {
      bundlePromise = null; // allow a retry on the next job
      throw err;
    });
  }
  return bundlePromise;
}

export interface RenderResult {
  outputPath: string;
  durationInFrames: number;
  fps: number;
  durationS: number;
}

export async function renderReel(opts: {
  composition: CompositionId;
  props: ReelsProps;
  outputPath: string;
  onProgress?: (progress: number) => void;
}): Promise<RenderResult> {
  const serveUrl = await getServeUrl();
  const { browserExecutable, chromeMode } = browserOptionsFromEnv();
  const inputProps = opts.props as unknown as Record<string, unknown>;
  const composition = await selectComposition({
    serveUrl,
    id: opts.composition,
    inputProps,
    browserExecutable,
    chromeMode,
  });
  await renderMedia({
    composition,
    serveUrl,
    codec: "h264",
    outputLocation: opts.outputPath,
    inputProps,
    browserExecutable,
    chromeMode,
    imageFormat: "jpeg",
    overwrite: true,
    concurrency: process.env.RENDER_CONCURRENCY ? Number(process.env.RENDER_CONCURRENCY) : null,
    onProgress: ({ progress }) => opts.onProgress?.(progress),
  });
  return {
    outputPath: opts.outputPath,
    durationInFrames: composition.durationInFrames,
    fps: composition.fps,
    durationS: composition.durationInFrames / composition.fps,
  };
}
