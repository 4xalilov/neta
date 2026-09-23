import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { FONT_UZ_GLYPHS, LOCAL_FONTS, fontHasWeight, primaryFamily, uzbekSafe } from "../lib/fonts";
import { THEMES } from "../motion/styles";
import { cmapHas, woff2Cmap } from "../lib/woff2";

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
        // latin → "A", latin-ext → "Ā", cyrillic → "А", cyrillic-ext → "Қ"
        expect([0x41, 0x100, 0x410, 0x49a].some((cp) => cmapHas(cmap, cp)), f.file).toBe(true);
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

  it("FONT_UZ_GLYPHS (per-glyph ʻ/ʼ table) matches the real coverage of the woff2 files", () => {
    for (const row of listing) {
      expect(FONT_UZ_GLYPHS[row.family], `${row.family}: ${JSON.stringify(row)}`).toEqual({ okina: row.okina, tutuq: row.tutuq });
    }
    expect(Object.keys(FONT_UZ_GLYPHS).sort()).toEqual(Object.keys(LOCAL_FONTS).sort());
    // Snapshot of a few rows (update when fonts change).
    expect(FONT_UZ_GLYPHS).toMatchObject({
      "Plus Jakarta Sans": { okina: false, tutuq: false },
      Manrope: { okina: false, tutuq: false },
      "Playfair Display": { okina: true, tutuq: true },
      Anton: { okina: true, tutuq: true },
      Inter: { okina: true, tutuq: true },
      Rubik: { okina: false, tutuq: true },
      Bangers: { okina: false, tutuq: false },
    });
  });

  it("fonts without ʻ or ʼ have the ‘ ’ substitutes, so uzbekSafe() never falls back to another font", () => {
    for (const row of listing) {
      if (!(row.okina && row.tutuq)) expect(row.quotes, row.family).toBe(true);
    }
  });

  it("every offline family ships an OFL licence file", () => {
    for (const faces of Object.values(LOCAL_FONTS)) {
      const base = path.basename(faces[0]!.file).split("-")[0]!;
      const lic = path.join(PUBLIC, "fonts", `OFL-${base}.txt`);
      expect(existsSync(lic), lic).toBe(true);
      expect(readFileSync(lic, "utf8")).toMatch(/SIL Open Font License|SIL OPEN FONT LICENSE/);
    }
  });

  it("every theme font is available offline and renders Uzbek (natively or via substitution)", () => {
    for (const theme of Object.values(THEMES)) {
      for (const spec of [theme.fonts.display, theme.fonts.body]) {
        expect(LOCAL_FONTS[spec.family], `${theme.name}: ${spec.family}`).toBeDefined();
        expect(fontHasWeight(spec.family, spec.weight), `${theme.name}: ${spec.family} ${spec.weight}`).toBe(true);
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
    // per glyph: Rubik has ʼ but not ʻ
    expect(uzbekSafe("oʻzbek taʼlim", "Rubik")).toBe("o‘zbek taʼlim");
    expect(uzbekSafe("oʻzbek", "Some Unknown Font")).toBe("oʻzbek");
    expect(primaryFamily(`"Plus Jakarta Sans", Inter`)).toBe("Plus Jakarta Sans");
  });
});
