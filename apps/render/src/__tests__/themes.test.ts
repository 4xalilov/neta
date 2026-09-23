import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";
import { THEME_NAMES, THEMES, getTheme, pickTheme, styleThemeSchema, themeContrast, THEME_FAMILIES, contrastRatio } from "../motion/styles";
import { parseReelsProps } from "../props";
import { renderThemesIndex, themeJsonFiles, THEMES_DIR, THEMES_INDEX, THEME_SCHEMA_FILE, themeJsonSchemaText } from "../lib/themeFiles";
import { validateTheme } from "../lib/themeValidate";
import { FONT_UZ_GLYPHS } from "../lib/fonts";
import { uncoveredChars } from "../lib/fontFiles";
import { PATTERNS } from "../motion/styles/patterns";
import { patternLayer } from "../components/patterns";
import { catalogLooks } from "../compositions/StyleCatalog";
import { sheetLayout } from "../compositions/CatalogSheet";

const scene = { imageUrl: "x.png", durationS: 2 };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

afterEach(() => vi.restoreAllMocks());

describe("theme registry (JSON data)", () => {
  it("loads ≥ 36 themes with unique names, one per JSON file", () => {
    expect(THEME_NAMES.length).toBeGreaterThanOrEqual(36);
    expect(new Set(THEME_NAMES).size).toBe(THEME_NAMES.length);
    const files = themeJsonFiles();
    expect(files.length).toBe(THEME_NAMES.length);
    for (const f of files) {
      const json = JSON.parse(readFileSync(`${THEMES_DIR}/${f}`, "utf8"));
      expect(`${json.name}.json`, "file name = theme name").toBe(f);
    }
  });

  it("every theme validates against the schema (incl. meta) and uses distinct motion presets", () => {
    for (const name of THEME_NAMES) {
      const t = THEMES[name]!;
      expect(styleThemeSchema.safeParse(t).success, name).toBe(true);
      expect(t.defaultTextAnim, name).not.toBe(t.secondaryTextAnim);
      expect(t.meta.description_uz.length, name).toBeGreaterThan(30);
      expect(t.meta.aida.length, name).toBeGreaterThan(0);
    }
  });

  it("covers every family and no two themes share the same look signature", () => {
    const fams = new Set(THEME_NAMES.map((n) => THEMES[n]!.meta.family));
    expect([...fams].sort()).toEqual([...THEME_FAMILIES].sort());
    const sig = (n: string) => {
      const t = THEMES[n]!;
      return [t.fonts.display.family, t.colors.bg, t.colors.accent, t.captionPreset, t.defaultTextAnim, t.defaultTransition].join("|");
    };
    expect(new Set(THEME_NAMES.map(sig)).size).toBe(THEME_NAMES.length);
  });

  it("passes the WCAG contrast gate (text/bg, text/surface, accent/bg, onHighlight/highlight ≥ 4.5)", () => {
    for (const name of THEME_NAMES) {
      const failing = themeContrast(THEMES[name]!).filter((c) => !c.ok);
      expect(failing, name).toEqual([]);
    }
    expect(contrastRatio("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
    expect(contrastRatio("#FFFFFF", "#FFFFFF")).toBeCloseTo(1, 5);
  });

  it("every theme passes the render-side quality gate (fonts, Uzbek glyphs, consistency)", () => {
    for (const name of THEME_NAMES) {
      const v = validateTheme(THEMES[name]);
      expect(v.problems, name).toEqual([]);
    }
  });

  it("the generated index.ts is up to date with the folder", () => {
    expect(readFileSync(THEMES_INDEX, "utf8")).toBe(renderThemesIndex(themeJsonFiles()));
  });

  it("getTheme keeps its API", () => {
    expect(getTheme("Dark-Gold").name).toBe("dark-gold");
    expect(getTheme("nope").name).toBe("bold");
  });

  it("every pattern has a tile (retroGrid is drawn by ThemeBackground)", () => {
    for (const p of PATTERNS) {
      const l = patternLayer(p, "#FFD166");
      if (p === "retroGrid") expect(l).toBeNull();
      else expect(l!.image.length, p).toBeGreaterThan(20);
    }
  });
});

describe("JSON Schema export", () => {
  it("schemas/style-theme.schema.json is generated and matches the zod schema", () => {
    const file = readFileSync(THEME_SCHEMA_FILE, "utf8");
    expect(file).toBe(themeJsonSchemaText());
    const js = JSON.parse(file);
    expect(js.$schema).toContain("2020-12");
    expect(js.required).toEqual(expect.arrayContaining(["name", "fonts", "colors", "meta"]));
    expect(js.properties.meta.properties.family.enum).toEqual([...THEME_FAMILIES]);
    expect(js.properties.colors.properties.bg.pattern).toBeDefined();
  });
});

describe("runtime theme override (props.theme)", () => {
  it("a valid full theme wins over style — even one the bundle has never seen", () => {
    const custom = { ...clone(THEMES.navruz!), name: "db-approved-42", label: "DB 42", meta: undefined };
    const props = parseReelsProps({ scenes: [scene], style: "neon", theme: custom });
    expect(props.theme?.name).toBe("db-approved-42");
    const picked = pickTheme(props.style, props.theme);
    expect(picked.source).toBe("override");
    expect(picked.theme.name).toBe("db-approved-42");
    expect(picked.theme.colors.bg).toBe(THEMES.navruz!.colors.bg);
  });

  it("an invalid theme warns and falls back to style", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const broken = { ...clone(THEMES.navruz!), defaultTextAnim: "Explode", colors: { bg: "blue" } };
    const props = parseReelsProps({ scenes: [scene], style: "neon", theme: broken });
    expect(props.theme).toBeNull();
    expect(warn).toHaveBeenCalled();
    expect(pickTheme(props.style, props.theme).theme.name).toBe("neon");
    // pickTheme itself also guards raw (unparsed) props
    const raw = pickTheme("hype", broken);
    expect(raw).toMatchObject({ source: "style", theme: { name: "hype" } });
    expect(raw.warning).toMatch(/invalid props.theme/);
  });

  it("no theme → style as before", () => {
    const props = parseReelsProps({ scenes: [scene], style: "luxury" });
    expect(props.theme ?? null).toBeNull();
    expect(pickTheme(props.style, props.theme).theme.name).toBe("luxury");
  });

  it("StyleCatalog accepts theme objects (theme:validate still)", () => {
    const looks = catalogLooks(["bold"], [{ ...clone(THEMES.kids!), name: "kids-v2" }, { junk: true }]);
    expect(looks.map((l) => l.theme.name)).toEqual(["bold", "kids-v2", "bold"]);
    expect(looks[1]!.scrimRgb).not.toBe("0,0,0"); // light tone → bg-coloured scrims
  });

  it("CatalogSheet grid is 6 columns", () => {
    const l = sheetLayout(45, 6, 0.25);
    expect(l.rows).toBe(8);
    expect(l.cw).toBe(270);
    expect(l.width % 2).toBe(0);
  });
});

describe("theme:validate core", () => {
  it("returns problems for a broken theme", () => {
    const bad = clone(THEMES.navruz!) as Record<string, any>;
    bad.fonts.display.family = "Comic Sans MS";
    bad.fonts.body = { ...bad.fonts.body, family: "PT Serif", weight: 500 };
    bad.colors.text = "#2A4F5A";
    bad.secondaryTextAnim = bad.defaultTextAnim;
    bad.tone = "light";
    const v = validateTheme(bad);
    expect(v.ok).toBe(false);
    const codes = v.problems.map((p) => p.code);
    expect(codes).toEqual(expect.arrayContaining(["font_unavailable", "font_weight", "contrast", "anim_duplicate", "tone_mismatch"]));
    expect(v.problems.find((p) => p.code === "contrast")!.message).toMatch(/text\/bg/);
  });

  it("reports schema errors with paths, and warns on a name clash", () => {
    const v = validateTheme({ name: "Bad Name!", colors: {} });
    expect(v.ok).toBe(false);
    expect(v.problems.every((p) => p.code === "schema")).toBe(true);
    expect(v.problems.map((p) => p.path)).toEqual(expect.arrayContaining(["name", "meta"]));
    const clash = validateTheme(THEMES.bold, { existingNames: THEME_NAMES });
    expect(clash.ok).toBe(true);
    expect(clash.warnings.map((w) => w.code)).toContain("name_exists");
  });

  it("flags a stale ʻ/ʼ table and fonts that cannot draw the Uzbek sample", () => {
    const saved = { ...FONT_UZ_GLYPHS.Rubik! };
    try {
      // Pretend Rubik has ʻ: uzbekSafe stops substituting it, but the file has no U+02BB glyph.
      FONT_UZ_GLYPHS.Rubik = { okina: true, tutuq: true };
      const codes = validateTheme(THEMES["medical-clean"]).problems.map((p) => p.code);
      expect(codes).toEqual(expect.arrayContaining(["uzbek_table", "uzbek_glyphs"]));
    } finally {
      FONT_UZ_GLYPHS.Rubik = saved;
    }
    expect(validateTheme(THEMES["medical-clean"]).problems).toEqual([]);
    expect(uncoveredChars("Syne", "«№»")).toEqual(["№"]);
    // Latin-only family → warning, not a problem
    expect(validateTheme(THEMES.bold).warnings.map((w) => w.code)).toContain("no_cyrillic");
  });
});
