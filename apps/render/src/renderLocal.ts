// npm run render:demo — renders defaultProps to out/demo.mp4 (no Redis / S3).
//   REMOTION_BROWSER=/path/to/chrome  use a preinstalled Chromium (no download)
//   DEMO_SECONDS=2                    truncate the demo timeline
//   DEMO_COMPOSITION=ReelsParallax    composition id (default ReelsBasic)
//   DEMO_PROPS=props.json             render these props instead of defaultProps
import { mkdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import type { CompositionId } from "./lib/compositions";
import { defaultProps, parseReelsProps, truncateProps } from "./props";
import { APP_ROOT, renderReel } from "./render";

async function main() {
  const composition = (process.env.DEMO_COMPOSITION || "ReelsBasic") as CompositionId;
  let props = process.env.DEMO_PROPS
    ? parseReelsProps(JSON.parse(await readFile(process.env.DEMO_PROPS, "utf8")))
    : defaultProps;
  const seconds = Number(process.env.DEMO_SECONDS || 0);
  if (seconds > 0) props = truncateProps(props, seconds);

  const outDir = path.join(APP_ROOT, "out");
  await mkdir(outDir, { recursive: true });
  const outputPath = path.join(outDir, process.env.DEMO_OUT || "demo.mp4");
  const t0 = Date.now();
  let last = -10;
  const res = await renderReel({
    composition,
    props,
    outputPath,
    onProgress: (p) => {
      const pct = Math.floor(p * 100);
      if (pct >= last + 10) {
        last = pct;
        process.stdout.write(`\rrendering ${composition}: ${pct}%`);
      }
    },
  });
  const { size } = await stat(outputPath);
  console.log(
    `\n✔ ${path.relative(process.cwd(), outputPath)} — ${res.durationS.toFixed(2)} s, ` +
      `${res.durationInFrames} frames @ ${res.fps} fps, ${(size / 1024).toFixed(1)} KiB, ${Date.now() - t0} ms`,
  );
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
