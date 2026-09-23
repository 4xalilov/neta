// Theme × brand → the concrete look a Reel renders with.
import { BRAND_DEFAULTS, type Brand } from "../../props";
import { ensureFont } from "../../lib/fonts";
import type { CaptionLook } from "../captions/Captions";
import type { TextStyle } from "../text/types";
import type { RenderTheme } from "./schema";
import { hexToRgb } from "./contrast";

export interface ResolvedFont {
  family: string;
  /** CSS stack (loaded via ensureFont). */
  stack: string;
  weight: number;
  lightWeight: number;
  uppercase: boolean;
  letterSpacing: number;
  charEm: number;
}

export interface Look {
  theme: RenderTheme;
  display: ResolvedFont;
  body: ResolvedFont;
  colors: RenderTheme["colors"];
  /** "r,g,b" for scrims / text shadows: black (dark tone) or the theme bg (light tone). */
  scrimRgb: string;
  /** TextStyle for a headline of `size` px (theme headline defaults). */
  text: (size: number, overrides?: Partial<TextStyle>) => TextStyle;
  caption: CaptionLook;
}

/**
 * Brand (workspace brand_profile) vs theme: a brand field that differs from the
 * docs/08 default was customised on purpose and wins; untouched defaults let
 * the theme decide. So `{style:"neon"}` gets neon colours, but
 * `{style:"neon", brand:{accent:"#FF5500"}}` keeps the brand's orange.
 */
export function resolveLook(theme: RenderTheme, brand: Brand): Look {
  const custom = <K extends keyof typeof BRAND_DEFAULTS>(k: K) => brand[k] != null && brand[k] !== BRAND_DEFAULTS[k];
  const colors = {
    ...theme.colors,
    text: custom("color") ? brand.color : theme.colors.text,
    accent: custom("accent") ? brand.accent : theme.colors.accent,
    highlight: custom("accent") ? brand.accent : theme.colors.highlight,
    bg: custom("bg") ? brand.bg : theme.colors.bg,
    surface: custom("surface") ? brand.surface : theme.colors.surface,
  };
  const font = (spec: RenderTheme["fonts"]["display"], family: string): ResolvedFont => ({
    family,
    stack: ensureFont(family),
    weight: spec.weight,
    lightWeight: spec.lightWeight ?? spec.weight,
    uppercase: spec.uppercase,
    letterSpacing: spec.letterSpacing,
    charEm: spec.charEm,
  });
  const display = custom("font")
    ? { ...font(theme.fonts.display, brand.font), weight: 800, uppercase: false, charEm: 0.62 }
    : font(theme.fonts.display, theme.fonts.display.family);
  const body = font(theme.fonts.body, theme.fonts.body.family);
  const h = theme.headline;
  const light = theme.tone === "light";
  const scrimRgb = light ? (hexToRgb(colors.bg) ?? [255, 255, 255]).slice(0, 3).join(",") : "0,0,0";
  const outline = (c: string | undefined) => c ?? (light ? colors.bg : "#000");
  const text = (size: number, overrides: Partial<TextStyle> = {}): TextStyle => ({
    fontFamily: display.stack,
    fontWeight: display.weight,
    lightWeight: display.lightWeight,
    fontSize: size,
    color: colors.text,
    accent: colors.accent,
    highlight: colors.highlight,
    onHighlight: colors.onHighlight,
    align: h.align,
    uppercase: display.uppercase,
    letterSpacing: display.letterSpacing,
    lineHeight: display.uppercase ? 1.0 : 1.08,
    stroke: h.stroke,
    strokeColor: outline(h.strokeColor),
    shadow: h.shadow,
    charEm: display.charEm,
    ...overrides,
  });
  const capFont = theme.captionStyle.font === "body" ? body : display;
  const caption: CaptionLook = {
    fontFamily: capFont.stack,
    fontWeight: theme.captionStyle.font === "body" ? Math.max(700, capFont.weight) : capFont.weight,
    color: colors.text,
    accent: colors.accent,
    highlight: colors.highlight,
    onHighlight: colors.onHighlight,
    surface: colors.surface,
    uppercase: theme.captionStyle.uppercase,
    stroke: theme.captionStyle.stroke,
    scale: theme.captionStyle.scale,
    strokeColor: outline(theme.captionStyle.strokeColor),
    shadowRgb: scrimRgb,
  };
  return { theme, display, body, colors, scrimRgb, text, caption };
}
