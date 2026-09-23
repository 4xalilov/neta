// npm run themes:index [-- --check] — regenerate src/motion/styles/themes/index.ts
// from the *.json files in that folder (--check: exit 1 if it is out of date).
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { renderThemesIndex, themeJsonFiles, THEMES_INDEX } from "../lib/themeFiles";

const files = themeJsonFiles();
const next = renderThemesIndex(files);
let prev = "";
try {
  prev = readFileSync(THEMES_INDEX, "utf8");
} catch {
  prev = "";
}
const rel = path.relative(process.cwd(), THEMES_INDEX);
if (process.argv.includes("--check")) {
  if (prev !== next) {
    console.error(`✘ ${rel} is out of date — run npm run themes:index`);
    process.exit(1);
  }
  console.log(`✔ ${rel} up to date (${files.length} themes)`);
} else {
  writeFileSync(THEMES_INDEX, next);
  console.log(`✔ ${rel} — ${files.length} themes${prev === next ? " (unchanged)" : ""}`);
}
