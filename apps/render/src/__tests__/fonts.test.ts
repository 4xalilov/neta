import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { FONT_UZ_GLYPHS, LOCAL_FONTS, primaryFamily, uzbekSafe } from "../lib/fonts";
import { THEMES } from "../motion/styles/themes";
import { cmapHas, woff2Cmap } from "./woff2";

const PUBLIC = path.resolve(__dirname, "../../public");
const OKINA = 0x02bb; // ʻ  (oʻ, gʻ)
const TUTUQ = 0x02bc; // ʼ  (tutuq belgisi)
const LSQUO = 0x2018; // ‘  substitute for ʻ
const RSQUO = 0x2019; // ’  substitute for ʼ

/** Code point coverage of a family = union over its local files. */
function covers(family: string, cp: number): boolean {
  return LOCAL_FONTS[family]!.some((f) => cmapHas(woff2Cmap(readFileSync(path.join(PUBLIC, f.file))), cp));
}

describe("offline font files", () => {
  it("every LOCAL_FONTS file exists and parses", () => {
    for (const faces of Object.values(LOCAL_FONTS)) {
      for (const f of faces) {
        const p = path.join(PUBLIC, f.file);
        expect(existsSync(p), p).toBe(true);
        const cmap = woff2Cmap(readFileSync(p));
        // latin → "A", latin-ext → "Ā", cyrillic → "А"
        expect([0x41, 0x100, 0x410].some((cp) => cmapHas(cmap, cp)), f.file).toBe(true);
      }
    }
  });
});

describe("fontsSupportUzbek", () => {
  // The listing the owner asked for: which brand/theme fonts draw ʻ ʼ natively.
  const listing = Object.keys(LOCAL_FONTS).map((family) => ({
    family,
    okina: covers(family, OKINA),
    tutuq: covers(family, TUTUQ),
    quotes: covers(family, LSQUO) && covers(family, RSQUO),
  }));

  it("FONT_UZ_GLYPHS matches the real glyph coverage of the woff2 files", () => {
    for (const row of listing) {
      expect(FONT_UZ_GLYPHS[row.family], `${row.family}: ${JSON.stringify(row)}`).toBe(row.okina && row.tutuq);
    }
    // Snapshot of the current state (update when fonts change).
    expect(Object.fromEntries(listing.map((r) => [r.family, r.okina && r.tutuq]))).toEqual({
      "Plus Jakarta Sans": false,
      Manrope: false,
      "Playfair Display": true,
      Anton: true,
    });
  });

  it("fonts without ʻ ʼ have the ‘ ’ substitutes, so uzbekSafe() never falls back to another font", () => {
    for (const row of listing) {
      if (!(row.okina && row.tutuq)) expect(row.quotes, row.family).toBe(true);
    }
  });

  it("every theme font is available offline and renders Uzbek (natively or via substitution)", () => {
    for (const theme of Object.values(THEMES)) {
      for (const spec of [theme.fonts.display, theme.fonts.body]) {
        expect(LOCAL_FONTS[spec.family], `${theme.name}: ${spec.family}`).toBeDefined();
        const text = uzbekSafe("Oʻzbekiston, gʻalaba, taʼlim", spec.family);
        for (const ch of Array.from(text)) {
          const cp = ch.codePointAt(0)!;
          if (cp > 0x7f) expect(covers(spec.family, cp), `${spec.family} U+${cp.toString(16)}`).toBe(true);
        }
      }
    }
  });

  it("uzbekSafe swaps only for fonts that lack the glyphs", () => {
    expect(uzbekSafe("oʻzbek taʼlim", "Plus Jakarta Sans")).toBe("o‘zbek ta’lim");
    expect(uzbekSafe("oʻzbek", `"Manrope", Inter, sans-serif`)).toBe("o‘zbek");
    expect(uzbekSafe("oʻzbek", "Playfair Display")).toBe("oʻzbek");
    expect(uzbekSafe("oʻzbek", "Some Unknown Font")).toBe("oʻzbek");
    expect(primaryFamily(`"Plus Jakarta Sans", Inter`)).toBe("Plus Jakarta Sans");
  });
});
