// Theme registry: every src/motion/styles/themes/*.json (docs/11 "Uslublar
// katalogi"), validated with the StyleTheme schema at load time. Themes are
// DATA: add a JSON file + `npm run themes:index`; DB-approved themes reach a
// render without a redeploy through `props.theme` (pickTheme below).
import { THEME_JSON } from "./themes/index";
import { renderThemeSchema, styleThemeSchema, THEME_FAMILIES, type RenderTheme, type StyleTheme } from "./schema";

function load(raw: readonly unknown[]): StyleTheme[] {
  const out: StyleTheme[] = [];
  for (const [i, json] of raw.entries()) {
    const r = styleThemeSchema.safeParse(json);
    if (!r.success) {
      const name = (json as { name?: unknown })?.name;
      throw new Error(`Invalid theme #${i} (${String(name)}): ${r.error.issues.map((x) => `${x.path.join(".")}: ${x.message}`).join("; ")}`);
    }
    out.push(r.data);
  }
  // Catalog order: family (THEME_FAMILIES order), then the family's original
  // themes (since) first, then name.
  const fam = (t: StyleTheme) => THEME_FAMILIES.indexOf(t.meta.family);
  return out.sort((a, b) => fam(a) - fam(b) || a.meta.since.localeCompare(b.meta.since) || a.name.localeCompare(b.name));
}

const LIST = load(THEME_JSON);

export const THEMES: Record<string, StyleTheme> = Object.fromEntries(LIST.map((t) => [t.name, t]));
export const THEME_NAMES: readonly string[] = LIST.map((t) => t.name);
export const DEFAULT_THEME = "bold";

/** Theme by name (case-insensitive); unknown → "bold". */
export function getTheme(name: string | null | undefined): StyleTheme {
  const key = (name ?? "").trim().toLowerCase();
  return THEMES[key] ?? THEMES[DEFAULT_THEME]!;
}

export interface PickedTheme {
  theme: RenderTheme;
  source: "override" | "style";
  /** Why an override was rejected (logged as a warning). */
  warning?: string;
}

/**
 * The theme a render uses: a valid full `override` (props.theme — e.g. a
 * DB-approved theme the bundle has never seen) wins over `style`; an invalid
 * override logs a warning and falls back to `style` (→ "bold" if unknown).
 */
export function pickTheme(style: string | null | undefined, override?: unknown): PickedTheme {
  if (override != null) {
    const r = renderThemeSchema.safeParse(override);
    if (r.success) return { theme: r.data, source: "override" };
    const warning = `[theme] invalid props.theme, falling back to style "${style ?? DEFAULT_THEME}": ${r.error.issues
      .slice(0, 5)
      .map((x) => `${x.path.join(".") || "(root)"}: ${x.message}`)
      .join("; ")}`;
    console.warn(warning);
    return { theme: getTheme(style), source: "style", warning };
  }
  return { theme: getTheme(style), source: "style" };
}
