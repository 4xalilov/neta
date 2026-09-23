import { z } from "zod";
import { zColor } from "@remotion/zod-types";
import { TEXT_ANIMS } from "../text/names";
import { TRANSITIONS } from "../transitions/names";
import { FX_NAMES } from "../fx/names";
import { CAPTION_PRESETS } from "../captions/registry";

import { KEN_BURNS_MODES, type KenBurnsMode } from "./kenBurnsModes";

export { KEN_BURNS_MODES, type KenBurnsMode };

export const fontSpecSchema = z.object({
  family: z.string().min(1),
  weight: z.number().int().min(100).max(900),
  /** Light weight for Kinetic's small beats (variable fonts only; else = weight). */
  lightWeight: z.number().int().min(100).max(900).optional(),
  uppercase: z.boolean().default(false),
  /** em */
  letterSpacing: z.number().min(-0.1).max(0.5).default(-0.01),
  /** Average glyph width in em (line-split / auto-size estimate). */
  charEm: z.number().min(0.3).max(0.9).default(0.6),
});

/** A complete look: fonts, docs/08 colour roles, motion defaults, fx stack, background. */
export const styleThemeSchema = z.object({
  name: z.string().regex(/^[a-z]+$/),
  label: z.string(),
  description: z.string(),
  fonts: z.object({ display: fontSpecSchema, body: fontSpecSchema }),
  colors: z.object({
    bg: zColor(),
    surface: zColor(),
    text: zColor(),
    muted: zColor(),
    primary: zColor(),
    accent: zColor(),
    /** Marker / caption box. */
    highlight: zColor(),
    /** Text on top of `highlight`. */
    onHighlight: zColor(),
  }),
  captionPreset: z.enum(CAPTION_PRESETS),
  captionStyle: z.object({
    font: z.enum(["display", "body"]).default("display"),
    uppercase: z.boolean().default(false),
    /** Outline px; docs/08 default 6. */
    stroke: z.number().min(0).max(12).default(6),
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
    kind: z.enum(["brand", "mesh", "solid"]),
    colors: z.array(zColor()).min(1),
  }),
  headline: z.object({
    /** px on the 1080×1920 canvas (auto-shrunk to fit maxLines). */
    size: z.number().min(40).max(220),
    hookSize: z.number().min(40).max(260),
    align: z.enum(["left", "center", "right"]),
    maxLines: z.number().int().min(1).max(6),
    stroke: z.number().min(0).max(12).default(0),
    shadow: z.string().default("0 8px 30px rgba(0,0,0,0.55)"),
    /** Scrim behind headlines for contrast over bright images. */
    scrim: z.number().min(0).max(1).default(0.45),
  }),
  card: z.object({ glass: z.boolean(), radius: z.number().min(0).max(80) }),
  kenBurns: z.enum(KEN_BURNS_MODES),
  /** Motion tempo: 1 = normal, 1.5 = 50 % slower text entrances (luxury). */
  tempo: z.number().min(0.5).max(2),
  particlesColor: zColor().optional(),
});

export type StyleTheme = z.output<typeof styleThemeSchema>;
export type StyleThemeInput = z.input<typeof styleThemeSchema>;
