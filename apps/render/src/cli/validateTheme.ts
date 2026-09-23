// npm run theme:validate -- <theme.json> [--still out.png] [--no-still]
//
// Quality gate for a theme candidate (roadmap 2.8, render side). Prints ONE
// JSON object on stdout (logs go to stderr):
//   {"ok":true,  "name":"…", "still":"/abs/out.png", "warnings":[…], "contrast":[…]}
//   {"ok":false, "name":"…", "problems":[{"code","path","message"}…], "still":"…"|null, …}
// Exit code 0 = ok, 1 = problems, 2 = usage / render error.
// The still (StyleCatalog frame, 540×960) is rendered whenever the schema
// passes — also when other checks fail — so VisionQA / a human can look at it.
import { readFileSync } from "node:fs";
import path from "node:path";
import { validateTheme } from "../lib/themeValidate";
import { THEME_NAMES } from "../motion/styles";
import { APP_DIR, THEMES_DIR } from "../lib/themeFiles";

function out(obj: unknown, code: number): never {
  process.stdout.write(JSON.stringify(obj, null, 2) + "\n");
  process.exit(code);
}

async function main() {
  const args = process.argv.slice(2);
  const file = args.find((a, i) => !a.startsWith("--") && args[i - 1] !== "--still");
  const stillArg = args.includes("--still") ? args[args.indexOf("--still") + 1] : undefined;
  const noStill = args.includes("--no-still");
  if (!file) out({ ok: false, problems: [{ code: "usage", message: "usage: theme:validate -- <theme.json> [--still out.png] [--no-still]" }] }, 2);

  const abs = path.resolve(process.cwd(), file!);
  let json: unknown;
  try {
    json = JSON.parse(readFileSync(abs, "utf8"));
  } catch (e) {
    out({ ok: false, problems: [{ code: "json", message: `cannot read ${abs}: ${(e as Error).message}` }], still: null }, 1);
  }
  // A theme already in the catalog folder is validated in place (no clash warning).
  const inCatalog = path.dirname(abs) === THEMES_DIR;
  const v = validateTheme(json, { existingNames: inCatalog ? [] : THEME_NAMES });

  let still: string | null = null;
  if (v.theme && !noStill) {
    const output = path.resolve(process.cwd(), stillArg ?? path.join(APP_DIR, "out", "validate", `${v.theme.name}.png`));
    // Keep stdout pure JSON: Remotion / bundler logs → stderr.
    const log = console.log;
    console.log = (...a: unknown[]) => console.error(...a);
    try {
      const { openStillSession, renderThemeStill } = await import("../lib/stills");
      const s = await openStillSession();
      try {
        const r = await renderThemeStill(s, { theme: json as Record<string, unknown>, output });
        still = r.output;
        console.error(`still ${r.output} (${r.ms} ms)`);
      } finally {
        await s.close();
      }
    } catch (e) {
      console.log = log;
      out({ ok: false, name: v.name, problems: [...v.problems, { code: "render", message: String((e as Error).message ?? e) }], warnings: v.warnings, contrast: v.contrast, still: null }, 2);
    }
    console.log = log;
  }
  const { theme: _t, ...rest } = v;
  void _t;
  if (v.ok) out({ ok: true, name: v.name, still, warnings: v.warnings, contrast: v.contrast }, 0);
  out({ ...rest, still }, 1);
}

main().catch((e) => out({ ok: false, problems: [{ code: "internal", message: String(e?.stack ?? e) }] }, 2));
