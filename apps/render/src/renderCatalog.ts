// npm run render:catalog — one PNG still per StyleTheme → out/catalog/<theme>.png
//   REMOTION_BROWSER=/path/to/chrome   preinstalled Chromium (see README)
//   CATALOG_THEMES=bold,neon           subset (default: all)
//   CATALOG_SCALE=0.5                  output scale (default 0.5 → 540×960)
//   CATALOG_FRAME=100                  frame inside the theme segment
//   CATALOG_SAFE=1                     paint the Instagram unsafe zones
import { mkdir, stat } from "node:fs/promises";
import path from "node:path";
import { renderStill, selectComposition } from "@remotion/renderer";
import { browserOptionsFromEnv } from "./lib/env";
import { APP_ROOT, getServeUrl } from "./render";
import { THEME_NAMES } from "./motion/styles/themes";
import { CATALOG_STILL_FRAME } from "./compositions/StyleCatalog";

async function main() {
  const themes = (process.env.CATALOG_THEMES || THEME_NAMES.join(","))
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const scale = Number(process.env.CATALOG_SCALE || 0.5);
  const frame = Number(process.env.CATALOG_FRAME || CATALOG_STILL_FRAME);
  const showSafeArea = process.env.CATALOG_SAFE === "1";
  const outDir = path.join(APP_ROOT, "out", "catalog");
  await mkdir(outDir, { recursive: true });
  const serveUrl = await getServeUrl();
  const { browserExecutable, chromeMode } = browserOptionsFromEnv();
  for (const theme of themes) {
    const t0 = Date.now();
    const inputProps = { themes: [theme], showSafeArea };
    const composition = await selectComposition({ serveUrl, id: "StyleCatalog", inputProps, browserExecutable, chromeMode });
    const output = path.join(outDir, `${theme}${showSafeArea ? "-safe" : ""}.png`);
    await renderStill({ composition, serveUrl, output, frame, scale, inputProps, browserExecutable, chromeMode, imageFormat: "png", overwrite: true });
    const { size } = await stat(output);
    console.log(`✔ ${path.relative(process.cwd(), output)} — ${(size / 1024).toFixed(1)} KiB, ${Date.now() - t0} ms`);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
