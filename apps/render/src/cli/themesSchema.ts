// npm run themes:schema [-- --check] — write schemas/style-theme.schema.json
// (JSON Schema of StyleTheme for the Python candidate pipeline).
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { THEME_SCHEMA_FILE, themeJsonSchemaText } from "../lib/themeFiles";

const next = themeJsonSchemaText();
let prev = "";
try {
  prev = readFileSync(THEME_SCHEMA_FILE, "utf8");
} catch {
  prev = "";
}
const rel = path.relative(process.cwd(), THEME_SCHEMA_FILE);
if (process.argv.includes("--check")) {
  if (prev !== next) {
    console.error(`✘ ${rel} is out of date — run npm run themes:schema`);
    process.exit(1);
  }
  console.log(`✔ ${rel} up to date`);
} else {
  mkdirSync(path.dirname(THEME_SCHEMA_FILE), { recursive: true });
  writeFileSync(THEME_SCHEMA_FILE, next);
  console.log(`✔ ${rel}${prev === next ? " (unchanged)" : ""}`);
}
