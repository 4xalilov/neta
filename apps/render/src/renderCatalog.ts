// npm run render:catalog — one PNG still per StyleTheme → out/catalog/<theme>.png
// plus a contact sheet of all of them → out/catalog/_sheet.png (CatalogSheet).
//   REMOTION_BROWSER=/path/to/chrome   preinstalled Chromium (see README)
//   CATALOG_THEMES=bold,neon           subset (default: all)
//   CATALOG_SCALE=0.5                  still scale (default 0.5 → 540×960)
//   CATALOG_FRAME=100                  frame inside the theme segment
//   CATALOG_SAFE=1                     paint the Instagram unsafe zones
//   CATALOG_CONCURRENCY=1              parallel tabs (>1 is not faster here: a cold tab stalls ~25 s)
//   CATALOG_SHEET=0                    skip the contact sheet
import path from "node:path";
import { APP_ROOT } from "./render";
import { THEME_NAMES } from "./motion/styles";
import { CATALOG_STILL_FRAME } from "./compositions/StyleCatalog";
import { openStillSession, pool, renderPng, renderThemeStill } from "./lib/stills";

async function main() {
  const themes = (process.env.CATALOG_THEMES || THEME_NAMES.join(","))
    .split(",")
    .map((s: string) => s.trim())
    .filter(Boolean);
  const scale = Number(process.env.CATALOG_SCALE || 0.5);
  const frame = Number(process.env.CATALOG_FRAME || CATALOG_STILL_FRAME);
  const showSafeArea = process.env.CATALOG_SAFE === "1";
  const concurrency = Number(process.env.CATALOG_CONCURRENCY || 1);
  const outDir = path.join(APP_ROOT, "out", "catalog");
  const t0 = Date.now();
  const session = await openStillSession();
  console.log(`bundle + browser ready in ${Date.now() - t0} ms`);
  try {
    const t1 = Date.now();
    const one = async (theme: string) => {
      const output = path.join(outDir, `${theme}${showSafeArea ? "-safe" : ""}.png`);
      const r = await renderThemeStill(session, { theme, output, scale, frame, showSafeArea });
      console.log(`✔ ${path.relative(process.cwd(), r.output)} — ${(r.bytes / 1024).toFixed(1)} KiB, ${r.ms} ms`);
    };
    // Warm-up: the first page load alone (several cold tabs at once stall ~25 s), then parallel tabs.
    if (themes.length) await one(themes[0]!);
    await pool(themes.slice(1), concurrency, one);
    console.log(`${themes.length} stills in ${((Date.now() - t1) / 1000).toFixed(1)} s (concurrency ${concurrency})`);
    if (process.env.CATALOG_SHEET !== "0") {
      const r = await renderPng(session, {
        id: "CatalogSheet",
        inputProps: { themes, columns: 6, cellScale: 0.25, frame },
        output: path.join(outDir, "_sheet.png"),
      });
      console.log(`✔ ${path.relative(process.cwd(), r.output)} — ${(r.bytes / 1024).toFixed(1)} KiB, ${r.ms} ms`);
    }
  } finally {
    await session.close();
  }
  console.log(`total ${((Date.now() - t0) / 1000).toFixed(1)} s`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
