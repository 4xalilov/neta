// WCAG 2.x contrast for theme colour roles (pure — used by tests and theme:validate).
import type { RenderTheme } from "./schema";

/** #rgb / #rrggbb / #rrggbbaa → [r, g, b, a] (0–255, a 0–1); null if not hex. */
export function hexToRgb(hex: string): [number, number, number, number] | null {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i.exec(hex.trim());
  if (!m) return null;
  let h = m[1]!;
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const n = (i: number) => parseInt(h.slice(i, i + 2), 16);
  return [n(0), n(2), n(4), h.length === 8 ? n(6) / 255 : 1];
}

/** Alpha-composite `fg` over opaque `base`. */
function over(fg: [number, number, number, number], base: [number, number, number]): [number, number, number] {
  const a = fg[3];
  return [0, 1, 2].map((i) => fg[i]! * a + base[i]! * (1 - a)) as [number, number, number];
}

export function relativeLuminance([r, g, b]: [number, number, number]): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/**
 * Contrast ratio (1–21) of `fg` on `bg`. Translucent colours are composited:
 * `bg` over `backdrop` (default black), then `fg` over the result.
 */
export function contrastRatio(fg: string, bg: string, backdrop: [number, number, number] = [0, 0, 0]): number {
  const f = hexToRgb(fg);
  const b = hexToRgb(bg);
  if (!f || !b) return NaN;
  const bgRgb = over(b, backdrop);
  const l1 = relativeLuminance(over(f, bgRgb));
  const l2 = relativeLuminance(bgRgb);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

export interface ContrastCheck {
  /** "text/bg", "accent/bg", … */
  pair: string;
  fg: string;
  bg: string;
  ratio: number;
  min: number;
  ok: boolean;
}

/**
 * The colour pairs a theme paints (docs/11 "Sifat darvozasi"):
 *   text/bg, text/surface (headlines, CTA card), accent/bg (caption active
 *   word, *keyword*), onHighlight/highlight (caption box, marker) ≥ 4.5;
 *   muted/bg ≥ 3 (secondary copy, large text); highlight/bg ≥ 1.25 (the
 *   marker / caption box must stand out from the background at all).
 */
export function themeContrast(theme: Pick<RenderTheme, "colors" | "tone">, minText = 4.5): ContrastCheck[] {
  const c = theme.colors;
  const backdrop: [number, number, number] = theme.tone === "light" ? [255, 255, 255] : [0, 0, 0];
  const pairs: [string, string, string, number][] = [
    ["text/bg", c.text, c.bg, minText],
    ["text/surface", c.text, c.surface, minText],
    ["accent/bg", c.accent, c.bg, minText],
    ["onHighlight/highlight", c.onHighlight, c.highlight, minText],
    ["muted/bg", c.muted, c.bg, 3],
    ["highlight/bg", c.highlight, c.bg, 1.25],
  ];
  return pairs.map(([pair, fg, bg, min]) => {
    const ratio = Math.round(contrastRatio(fg, bg, backdrop) * 100) / 100;
    return { pair, fg, bg, ratio, min, ok: ratio >= min };
  });
}
