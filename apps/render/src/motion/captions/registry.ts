// Caption preset registry (pure data — used by the zod schemas and tests).

export const CAPTION_PRESETS = ["karaoke", "boxHighlight", "pillGlass", "bigWord", "lineByLine"] as const;
export type CaptionPreset = (typeof CAPTION_PRESETS)[number];

export interface CaptionPresetMeta {
  description: string;
  /** Page budget (chars) and lines — passed to pageWords(). */
  maxChars: number;
  maxLines: number;
  /** Font size in px on the 1080×1920 canvas. */
  fontSize: number;
}

export const CAPTION_META: Record<CaptionPreset, CaptionPresetMeta> = {
  karaoke: { description: "TikTok uslubi: 2 qator, faol soʻz aksent rangda + pop (joriy standart)", maxChars: 42, maxLines: 2, fontSize: 78 },
  boxHighlight: { description: "Hormozi uslubi: faol soʻz aksent rangli yumaloq quti ichida", maxChars: 30, maxLines: 2, fontSize: 82 },
  pillGlass: { description: "Muzli shisha (frosted) tabletka fonida, aytilmagan soʻzlar xira", maxChars: 36, maxLines: 2, fontSize: 64 },
  bigWord: { description: "Bir vaqtda bitta soʻz, juda katta, scale-in", maxChars: 42, maxLines: 2, fontSize: 150 },
  lineByLine: { description: "Bitta qator, niqob ortidan pastdan chiqadi — editorial", maxChars: 24, maxLines: 1, fontSize: 72 },
};

export const isCaptionPreset = (n: unknown): n is CaptionPreset =>
  typeof n === "string" && (CAPTION_PRESETS as readonly string[]).includes(n);
