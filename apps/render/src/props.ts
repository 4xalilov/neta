import { z } from "zod";
import { zColor } from "@remotion/zod-types";
import { evenWords } from "./lib/captions";

/**
 * Brand tokens — docs/08-design-system.md "Remotion Reels tokenlari".
 * Mandatory defaults; the API may override them per workspace (brand_profile).
 */
export const BRAND_DEFAULTS = {
  font: "Plus Jakarta Sans",
  color: "#E6EAF2", // text
  accent: "#FACC15", // subtitle (active word, yellow)
  bg: "#0B0F19",
  surface: "#131A2A",
  logoUrl: null as string | null,
} as const;

/** Secondary tokens used by background / CTA (docs/08 colour table). */
export const TOKENS = {
  surface2: "#1B2438",
  border: "#26304A",
  muted: "#8B95AD",
  primary: "#6366F1",
  cyan: "#22D3EE",
  stroke: "#000000",
} as const;

export const wordSchema = z.object({
  w: z.string(),
  start: z.number().min(0),
  end: z.number().min(0),
});

export const sceneSchema = z.object({
  imageUrl: z.string().min(1),
  /** Depth map (Depth Anything; white = near). Used only by ReelsParallax. */
  depthUrl: z.string().min(1).nullish(),
  durationS: z.number().positive(),
  /** Word timings in seconds relative to the COMPOSITION start (not the scene). */
  words: z.array(wordSchema).default([]),
  /** Static caption shown for the whole scene when it has no word timings. */
  subtitle: z.string().nullish(),
});

export const brandSchema = z.object({
  font: z.string().default(BRAND_DEFAULTS.font),
  color: zColor().default(BRAND_DEFAULTS.color),
  accent: zColor().default(BRAND_DEFAULTS.accent),
  bg: zColor().default(BRAND_DEFAULTS.bg),
  surface: zColor().default(BRAND_DEFAULTS.surface),
  logoUrl: z.string().nullish(),
});

export const reelsPropsSchema = z.object({
  audioUrl: z.string().nullish(),
  cta: z.string().nullish(),
  scenes: z.array(sceneSchema).min(1),
  brand: brandSchema.default({ ...BRAND_DEFAULTS }),
});

/** Props as sent by the API (optional fields may be omitted). */
export type ReelsPropsInput = z.input<typeof reelsPropsSchema>;
/** Props after defaults are applied — what the compositions receive. */
export type ReelsProps = z.output<typeof reelsPropsSchema>;
export type Scene = ReelsProps["scenes"][number];
export type Brand = ReelsProps["brand"];

export function parseReelsProps(input: unknown): ReelsProps {
  return reelsPropsSchema.parse(input);
}

// ---------------------------------------------------------------------------
// Demo props: offline placeholders (data-URI SVG), no network needed.

const svgUri = (svg: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;

export function placeholderImage(from: string, to: string, label: string): string {
  return svgUri(
    `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">` +
      `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">` +
      `<stop offset="0" stop-color="${from}"/><stop offset="1" stop-color="${to}"/></linearGradient></defs>` +
      `<rect width="1080" height="1920" fill="url(#g)"/>` +
      `<circle cx="540" cy="820" r="300" fill="#ffffff" fill-opacity="0.18"/>` +
      `<rect x="140" y="1180" width="800" height="36" rx="18" fill="#ffffff" fill-opacity="0.12"/>` +
      `<text x="540" y="860" font-family="sans-serif" font-size="120" font-weight="800" ` +
      `fill="#ffffff" fill-opacity="0.85" text-anchor="middle">${label}</text></svg>`,
  );
}

/** Depth placeholder: bright (near) disc in the middle, dark (far) edges. */
export function placeholderDepth(): string {
  return svgUri(
    `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">` +
      `<defs><radialGradient id="d" cx="0.5" cy="0.43" r="0.35">` +
      `<stop offset="0" stop-color="#fff"/><stop offset="0.7" stop-color="#fff"/>` +
      `<stop offset="1" stop-color="#000"/></radialGradient></defs>` +
      `<rect width="1080" height="1920" fill="#000"/><rect width="1080" height="1920" fill="url(#d)"/></svg>`,
  );
}

export const defaultProps: ReelsProps = {
  audioUrl: null,
  cta: "Obuna boʻling — har kuni yangi Reels!",
  scenes: [
    {
      imageUrl: placeholderImage("#6366F1", "#0B0F19", "Sahna 1"),
      depthUrl: null,
      durationS: 4,
      words: evenWords("Salom! Bu Neta — oʻzbekcha Reels demosi.", 0.2, 3.8),
      subtitle: null,
    },
    {
      imageUrl: placeholderImage("#22D3EE", "#131A2A", "Sahna 2"),
      depthUrl: placeholderDepth(),
      durationS: 4,
      words: evenWords("Har bir soʻz oʻz vaqtida sariq rangda yonadi.", 4.1, 7.8),
      subtitle: null,
    },
    {
      imageUrl: placeholderImage("#10B981", "#0B0F19", "Sahna 3"),
      depthUrl: null,
      durationS: 5,
      words: evenWords("Rasm, ovoz va subtitr — hammasi avtomatik.", 8.1, 10.4),
      subtitle: null,
    },
  ],
  brand: { ...BRAND_DEFAULTS },
};

/**
 * Cut props down to the first `seconds` of the timeline (DEMO_SECONDS in
 * renderLocal.ts). Scenes past the cut are dropped, the last kept scene is
 * shortened, and words starting after the cut are removed.
 */
export function truncateProps(props: ReelsProps, seconds: number): ReelsProps {
  if (!(seconds > 0)) return props;
  const scenes: Scene[] = [];
  let t = 0;
  for (const s of props.scenes) {
    if (t >= seconds) break;
    const durationS = Math.min(s.durationS, seconds - t);
    scenes.push({ ...s, durationS, words: s.words.filter((w) => w.start < seconds) });
    t += durationS;
  }
  return { ...props, scenes };
}
