// Theme quality gate, render side (roadmap 2.8). Pure Node — no browser:
// schema, offline fonts + Uzbek ʻ ʼ handling, WCAG contrast, consistency.
// The CLI (src/cli/validateTheme.ts) adds the catalog still for VisionQA.
import { FONT_UZ_GLYPHS, GOOGLE_FONT_FAMILIES, LOCAL_FONTS, fontHasWeight, uzbekSafe } from "./fonts";
import { familyCovers, missingFontFiles, uncoveredChars } from "./fontFiles";
import { styleThemeSchema, type StyleTheme } from "../motion/styles/schema";
import { hexToRgb, relativeLuminance, themeContrast, type ContrastCheck } from "../motion/styles/contrast";

export interface ThemeProblem {
  /** schema | font_unavailable | font_files_missing | font_weight | uzbek_glyphs | uzbek_table | contrast | anim_duplicate | pattern_missing | tone_mismatch | … */
  code: string;
  /** Dotted path in the theme JSON, when it applies. */
  path?: string;
  message: string;
}

export interface ThemeValidation {
  ok: boolean;
  name?: string;
  problems: ThemeProblem[];
  /** Non-blocking notes (network font, no Cyrillic, name already in the catalog…). */
  warnings: ThemeProblem[];
  contrast: ContrastCheck[];
  /** Parsed theme (defaults applied) when the schema passed. */
  theme?: StyleTheme;
}

/** Uzbek Latin sample (ʻ U+02BB in oʻ/gʻ, ʼ U+02BC tutuq) + Cyrillic sample. */
export const UZ_LATIN_SAMPLE = "Oʻzbekiston gʻalaba taʼlim — sifat, narx 30% arzon! «Yangi»";
export const UZ_CYRILLIC_SAMPLE = "Ўзбекистон ғалаба қувонч ҳаёт";

function checkFont(role: "display" | "body", spec: StyleTheme["fonts"]["display"], problems: ThemeProblem[], warnings: ThemeProblem[]) {
  const path = `fonts.${role}`;
  const fam = spec.family;
  if (!LOCAL_FONTS[fam]) {
    if (GOOGLE_FONT_FAMILIES.includes(fam))
      warnings.push({ code: "font_network", path, message: `${fam} has no offline files; it loads from Google Fonts at render time` });
    else
      problems.push({
        code: "font_unavailable",
        path: `${path}.family`,
        message: `${fam} is not an offline font (public/fonts). Available: ${Object.keys(LOCAL_FONTS).sort().join(", ")}`,
      });
    return;
  }
  const missing = missingFontFiles(fam);
  if (missing.length) {
    problems.push({ code: "font_files_missing", path: `${path}.family`, message: `${fam}: missing/unreadable ${missing.join(", ")}` });
    return;
  }
  if (!fontHasWeight(fam, spec.weight))
    problems.push({ code: "font_weight", path: `${path}.weight`, message: `${fam} has no weight ${spec.weight} (would be faux-bolded)` });
  if (spec.lightWeight != null && !fontHasWeight(fam, spec.lightWeight))
    warnings.push({ code: "font_weight", path: `${path}.lightWeight`, message: `${fam} has no weight ${spec.lightWeight}` });

  // Uzbek ʻ ʼ: the glyph table must match the files, and after uzbekSafe()
  // every non-ASCII character of the sample must exist in the font.
  const table = FONT_UZ_GLYPHS[fam];
  const okina = familyCovers(fam, 0x2bb);
  const tutuq = familyCovers(fam, 0x2bc);
  if (!table || table.okina !== okina || table.tutuq !== tutuq)
    problems.push({
      code: "uzbek_table",
      path: `${path}.family`,
      message: `FONT_UZ_GLYPHS["${fam}"] must be { okina: ${okina}, tutuq: ${tutuq} } (src/lib/fonts.ts)`,
    });
  const painted = uzbekSafe(UZ_LATIN_SAMPLE, fam);
  const text = spec.uppercase ? painted.toUpperCase() : painted;
  const bad = uncoveredChars(fam, text);
  if (bad.length)
    problems.push({
      code: "uzbek_glyphs",
      path: `${path}.family`,
      message: `${fam} cannot draw ${bad.map((c) => `${c} (U+${c.codePointAt(0)!.toString(16).toUpperCase().padStart(4, "0")})`).join(", ")} of the Uzbek sample`,
    });
  if (uncoveredChars(fam, UZ_CYRILLIC_SAMPLE).length)
    warnings.push({ code: "no_cyrillic", path: `${path}.family`, message: `${fam} lacks Uzbek Cyrillic (ў қ ғ ҳ); Cyrillic scripts fall back to another font` });
}

/**
 * Validate a theme candidate (parsed JSON). `existingNames`: catalog names —
 * a clash is a warning (the API decides whether it is an update).
 */
export function validateTheme(input: unknown, opts: { existingNames?: readonly string[] } = {}): ThemeValidation {
  const problems: ThemeProblem[] = [];
  const warnings: ThemeProblem[] = [];
  const r = styleThemeSchema.safeParse(input);
  if (!r.success) {
    for (const i of r.error.issues) problems.push({ code: "schema", path: i.path.join("."), message: i.message });
    const name = (input as { name?: unknown } | null)?.name;
    return { ok: false, name: typeof name === "string" ? name : undefined, problems, warnings, contrast: [] };
  }
  const t = r.data;

  checkFont("display", t.fonts.display, problems, warnings);
  checkFont("body", t.fonts.body, problems, warnings);

  const contrast = themeContrast(t);
  for (const c of contrast)
    if (!c.ok)
      problems.push({ code: "contrast", path: `colors`, message: `${c.pair}: ${c.fg} on ${c.bg} = ${c.ratio}:1 < ${c.min}:1` });

  if (t.defaultTextAnim === t.secondaryTextAnim)
    problems.push({ code: "anim_duplicate", path: "secondaryTextAnim", message: "secondaryTextAnim must differ from defaultTextAnim" });
  if (t.background.kind === "pattern" && !t.background.pattern)
    problems.push({ code: "pattern_missing", path: "background.pattern", message: 'background.kind "pattern" needs background.pattern' });
  const bgRgb = hexToRgb(t.colors.bg);
  if (bgRgb) {
    const lum = relativeLuminance([bgRgb[0], bgRgb[1], bgRgb[2]]);
    if (t.tone === "dark" && lum > 0.4)
      problems.push({ code: "tone_mismatch", path: "tone", message: `bg ${t.colors.bg} is light (L=${lum.toFixed(2)}) — set "tone": "light"` });
    if (t.tone === "light" && lum < 0.4)
      problems.push({ code: "tone_mismatch", path: "tone", message: `bg ${t.colors.bg} is dark (L=${lum.toFixed(2)}) — use "tone": "dark"` });
  }
  if (t.headline.hookSize < t.headline.size)
    warnings.push({ code: "headline_size", path: "headline.hookSize", message: "hookSize is smaller than size" });
  if (opts.existingNames?.includes(t.name))
    warnings.push({ code: "name_exists", path: "name", message: `"${t.name}" is already in the catalog` });

  return { ok: problems.length === 0, name: t.name, problems, warnings, contrast, theme: t };
}
