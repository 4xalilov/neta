import { z } from "zod";
import { TEXT_ANIMS } from "../text/names";
import { TRANSITIONS } from "../transitions/names";
import { FX_NAMES } from "../fx/names";
import { CAPTION_PRESETS } from "../captions/registry";

import { KEN_BURNS_MODES, type KenBurnsMode } from "./kenBurnsModes";
import { PATTERNS, type PatternName } from "./patterns";

export { KEN_BURNS_MODES, type KenBurnsMode, PATTERNS, type PatternName };

/**
 * Theme colours are hex only (#rgb, #rrggbb, #rrggbbaa) so every consumer —
 * CSS, the WCAG contrast gate, the Python candidate pipeline — can parse them.
 */
export const hexColor = () =>
  z
    .string()
    .regex(/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/, "hex colour: #rgb, #rrggbb or #rrggbbaa")
    .describe("Hex colour #rgb | #rrggbb | #rrggbbaa");

export const fontSpecSchema = z.object({
  family: z.string().min(1),
  weight: z.number().int().min(100).max(1000),
  /** Light weight for Kinetic's small beats (variable fonts only; else = weight). */
  lightWeight: z.number().int().min(100).max(1000).optional(),
  uppercase: z.boolean().default(false),
  /** em */
  letterSpacing: z.number().min(-0.1).max(0.5).default(-0.01),
  /** Average glyph width in em incl. ~20 % safety (line-split / auto-size estimate). */
  charEm: z.number().min(0.3).max(0.9).default(0.6),
});

/** Catalog families (docs/11 "Uslublar katalogi"). */
export const THEME_FAMILIES = [
  "bold",
  "minimal",
  "editorial",
  "neon",
  "luxury",
  "warm",
  "playful",
  "uzbek",
  "social",
  "finance",
  "fitness",
  "beauty",
] as const;
export type ThemeFamily = (typeof THEME_FAMILIES)[number];

export const AIDA_STAGES = ["attention", "interest", "desire", "action"] as const;
export type AidaStage = (typeof AIDA_STAGES)[number];

/** Knowledge-base metadata: what the Writer / theme picker matches on. */
export const themeMetaSchema = z.object({
  family: z.enum(THEME_FAMILIES),
  /** English mood tags ("energetic", "calm", …). */
  mood: z.array(z.string().min(2).max(40)).min(1).max(8),
  /** English niche slugs ("restaurant", "beauty-salon", …). */
  niches: z.array(z.string().min(2).max(40)).min(1).max(12),
  /** AIDA stages the look fits best. */
  aida: z.array(z.enum(AIDA_STAGES)).min(1).max(4),
  description_uz: z.string().min(10).max(400),
  /** Catalog version the theme was added in (YYYY-MM). */
  since: z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/),
});
export type ThemeMeta = z.output<typeof themeMetaSchema>;

const themeShape = {
  /** Lowercase slug, words joined with "-" (e.g. "dark-gold"). */
  name: z
    .string()
    .max(40)
    .regex(/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/),
  label: z.string().min(1).max(40),
  description: z.string(),
  /**
   * dark = light text over dark scrims (default); light = dark text, scrims
   * and outlines take the theme `bg` colour instead of black.
   */
  tone: z.enum(["dark", "light"]).default("dark"),
  fonts: z.object({ display: fontSpecSchema, body: fontSpecSchema }),
  colors: z.object({
    bg: hexColor(),
    surface: hexColor(),
    text: hexColor(),
    muted: hexColor(),
    primary: hexColor(),
    accent: hexColor(),
    /** Marker / caption box. */
    highlight: hexColor(),
    /** Text on top of `highlight`. */
    onHighlight: hexColor(),
  }),
  captionPreset: z.enum(CAPTION_PRESETS),
  captionStyle: z.object({
    font: z.enum(["display", "body"]).default("display"),
    uppercase: z.boolean().default(false),
    /** Outline px; docs/08 default 6. */
    stroke: z.number().min(0).max(12).default(6),
    /** Outline colour; default black (dark tone) / `bg` (light tone). */
    strokeColor: hexColor().optional(),
    scale: z.number().min(0.6).max(1.6).default(1),
  }),
  /** Hook + scene titles. */
  defaultTextAnim: z.enum(TEXT_ANIMS),
  /** Second preset (proof / numbers) — StyleCatalog shows both. */
  secondaryTextAnim: z.enum(TEXT_ANIMS),
  ctaTextAnim: z.enum(TEXT_ANIMS),
  defaultTransition: z.enum(TRANSITIONS),
  transitionFrames: z.number().int().min(0).max(30),
  fx: z.array(z.enum(FX_NAMES)),
  fxIntensity: z
    .object({
      grain: z.number().min(0).max(1),
      vignette: z.number().min(0).max(1),
      shake: z.number().min(0).max(60),
      chromatic: z.number().min(0).max(30),
      lightLeak: z.number().min(0).max(1),
      glow: z.number().min(0).max(80),
    })
    .partial()
    .default({}),
  background: z.object({
    /** brand = docs/08 drift glow; mesh = noise blobs; solid; gradient = linear over `colors`; pattern = gradient + SVG tile. */
    kind: z.enum(["brand", "mesh", "solid", "gradient", "pattern"]),
    colors: z.array(hexColor()).min(1).max(6),
    /** Tile for kind "pattern" (default "dots"). */
    pattern: z.enum(PATTERNS).optional(),
    /** Tile ink colour (default `accent`). */
    patternColor: hexColor().optional(),
    patternOpacity: z.number().min(0).max(1).default(0.16),
    /** Gradient angle in degrees (gradient / pattern). */
    angle: z.number().min(0).max(360).default(160),
  }),
  headline: z.object({
    /** px on the 1080×1920 canvas (auto-shrunk to fit maxLines). */
    size: z.number().min(40).max(220),
    hookSize: z.number().min(40).max(260),
    align: z.enum(["left", "center", "right"]),
    maxLines: z.number().int().min(1).max(6),
    stroke: z.number().min(0).max(12).default(0),
    /** Outline colour; default black (dark tone) / `bg` (light tone). */
    strokeColor: hexColor().optional(),
    shadow: z.string().max(200).default("0 8px 30px rgba(0,0,0,0.55)"),
    /** Scrim behind headlines for contrast over bright images. */
    scrim: z.number().min(0).max(1).default(0.45),
  }),
  card: z.object({ glass: z.boolean(), radius: z.number().min(0).max(80) }),
  kenBurns: z.enum(KEN_BURNS_MODES),
  /** Motion tempo: 1 = normal, 1.5 = 50 % slower text entrances (luxury). */
  tempo: z.number().min(0.5).max(2),
  particlesColor: hexColor().optional(),
};

/**
 * A complete look: fonts, docs/08 colour roles, motion defaults, fx stack,
 * background + knowledge-base `meta`. Themes are JSON data
 * (src/motion/styles/themes/*.json) validated with this schema; the JSON Schema
 * export (`npm run themes:schema`) is what the Python candidate pipeline uses.
 */
export const styleThemeSchema = z.object({ ...themeShape, meta: themeMetaSchema });

/**
 * What a render accepts as `props.theme` (DB-approved theme sent by the API):
 * the same schema, but `meta` is optional — it does not change pixels.
 */
export const renderThemeSchema = z.object({ ...themeShape, meta: themeMetaSchema.optional() });

export type StyleTheme = z.output<typeof styleThemeSchema>;
export type StyleThemeInput = z.input<typeof styleThemeSchema>;
export type RenderTheme = z.output<typeof renderThemeSchema>;
