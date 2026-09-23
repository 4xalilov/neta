// Node-only: glyph coverage of the offline font files in public/fonts
// (fonts test, theme:validate). Never import from composition code.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { LOCAL_FONTS } from "./fonts";
import { cmapHas, woff2Cmap } from "./woff2";

export const PUBLIC_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../public");

const cmaps = new Map<string, Buffer | null>();

/** Decompressed cmap of a public/ font file (cached); null if missing/unreadable. */
export function fileCmap(file: string): Buffer | null {
  if (!cmaps.has(file)) {
    const p = path.join(PUBLIC_DIR, file);
    let cmap: Buffer | null = null;
    try {
      if (existsSync(p)) cmap = woff2Cmap(readFileSync(p));
    } catch {
      cmap = null;
    }
    cmaps.set(file, cmap);
  }
  return cmaps.get(file)!;
}

/** Missing files of a local family (empty = all present). */
export function missingFontFiles(family: string): string[] {
  return (LOCAL_FONTS[family] ?? []).filter((f) => fileCmap(f.file) === null).map((f) => f.file);
}

/** Does any local file of `family` map code point `cp` to a glyph? */
export function familyCovers(family: string, cp: number): boolean {
  return (LOCAL_FONTS[family] ?? []).some((f) => {
    const c = fileCmap(f.file);
    return c !== null && cmapHas(c, cp);
  });
}

/** Code points of `text` (non-ASCII only) the family cannot draw. */
export function uncoveredChars(family: string, text: string): string[] {
  const out = new Set<string>();
  for (const ch of Array.from(text)) {
    const cp = ch.codePointAt(0)!;
    if (cp > 0x7f && !/\s/.test(ch) && !familyCovers(family, cp)) out.add(ch);
  }
  return [...out];
}
