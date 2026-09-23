// Brand font loading (browser side, runs inside the Remotion bundle).
//
// 1. Local files from public/fonts (shipped in the repo/image) — no network at
//    render time. Loaded via FontFace + staticFile() behind delayRender().
// 2. If the family has no local files, fall back to @remotion/google-fonts
//    (fetches from fonts.gstatic.com at render time — fine in prod, not in CI).
// 3. Unknown families are used as-is (must be installed in the container),
//    with Inter / system sans-serif as fallback in the CSS stack.
import { continueRender, delayRender, staticFile } from "remotion";
import { loadFont as loadJakarta } from "@remotion/google-fonts/PlusJakartaSans";
import { loadFont as loadManrope } from "@remotion/google-fonts/Manrope";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadPlayfair } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";

// Unicode ranges from Google Fonts / Fontsource. NOTE: U+02BB/U+02BC (Uzbek ʻ ʼ)
// are routed to the `latin` file — but not every family actually HAS those
// glyphs there (see FONT_UZ_GLYPHS below, verified by __tests__/fonts.test.ts).
const RANGES = {
  latin:
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD",
  "latin-ext":
    "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF",
  cyrillic: "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116",
  // Uzbek Cyrillic Қ Ғ Ҳ live here.
  "cyrillic-ext": "U+0460-052F, U+1C80-1C8A, U+20B4, U+2DE0-2DFF, U+A640-A69F, U+FE2E-FE2F",
} as const;
type Subset = keyof typeof RANGES;

export interface LocalFace {
  file: string;
  /** CSS font-weight descriptor: "400" (static) or "200 800" (variable range). */
  weight: string;
  unicodeRange: string;
}

const L: Subset[] = ["latin", "latin-ext"];
const LC: Subset[] = ["latin", "latin-ext", "cyrillic"];
const LCX: Subset[] = ["latin", "latin-ext", "cyrillic", "cyrillic-ext"];

/** `fonts/<base>-<subset>.woff2` for each subset. */
const faces = (base: string, weight: string, subsets: Subset[]): LocalFace[] =>
  subsets.map((s) => ({ file: `fonts/${base}-${s}.woff2`, weight, unicodeRange: RANGES[s] }));

/**
 * Files in public/fonts (see public/fonts/README.md). All SIL OFL 1.1, from
 * Google Fonts / Fontsource. Variable fonts list their full wght range.
 */
export const LOCAL_FONTS: Record<string, LocalFace[]> = {
  // The "-800" files are actually the variable font (wght 200–800).
  "Plus Jakarta Sans": faces("PlusJakartaSans-800", "200 800", L),
  Manrope: faces("Manrope-var", "200 800", LC),
  "Playfair Display": faces("PlayfairDisplay-var", "400 900", LC),
  Anton: faces("Anton-400", "400", L),
  Bangers: faces("Bangers-400", "400", L),
  "Bebas Neue": faces("BebasNeue-400", "400", L),
  Caveat: faces("Caveat-var", "400 700", LCX),
  Comfortaa: faces("Comfortaa-var", "300 700", LCX),
  "Cormorant Garamond": faces("CormorantGaramond-var", "300 700", LCX),
  "DM Serif Display": faces("DMSerifDisplay-400", "400", L),
  "Exo 2": faces("Exo2-var", "100 900", LCX),
  Fraunces: faces("Fraunces-var", "100 900", L),
  Fredoka: faces("Fredoka-var", "300 700", L),
  Inter: faces("Inter-var", "100 900", LCX),
  "JetBrains Mono": faces("JetBrainsMono-var", "100 800", LCX),
  Lora: faces("Lora-var", "400 700", LCX),
  Montserrat: faces("Montserrat-var", "100 900", LCX),
  Nunito: faces("Nunito-var", "200 1000", LCX),
  Oswald: faces("Oswald-var", "200 700", LCX),
  Pacifico: faces("Pacifico-400", "400", LCX),
  "PT Serif": [...faces("PTSerif-400", "400", LCX), ...faces("PTSerif-700", "700", LCX)],
  Rubik: faces("Rubik-var", "300 900", LCX),
  "Russo One": faces("RussoOne-400", "400", LC),
  "Space Grotesk": faces("SpaceGrotesk-var", "300 700", L),
  Syne: faces("Syne-var", "400 800", L),
  "Tenor Sans": faces("TenorSans-400", "400", LC),
  Unbounded: faces("Unbounded-var", "200 900", LCX),
  "Yeseva One": faces("YesevaOne-400", "400", LCX),
};

/** Weights a local family can draw without faux-bold: [min, max] over its faces. */
export function fontWeightRange(family: string): [number, number] | null {
  const f = LOCAL_FONTS[family];
  if (!f) return null;
  const ws = f.flatMap((x) => x.weight.split(" ").map(Number));
  return [Math.min(...ws), Math.max(...ws)];
}

/** Static families that ship only some weights (e.g. PT Serif 400 + 700). */
export function fontHasWeight(family: string, weight: number): boolean {
  const f = LOCAL_FONTS[family];
  if (!f) return false;
  return f.some((x) => {
    const [a, b] = x.weight.split(" ").map(Number) as [number, number | undefined];
    return b === undefined ? a === weight : weight >= a && weight <= b;
  });
}

export interface UzGlyphs {
  /** U+02BB ʻ (oʻ, gʻ) drawn natively. */
  okina: boolean;
  /** U+02BC ʼ (tutuq belgisi) drawn natively. */
  tutuq: boolean;
}

/**
 * Which Uzbek modifier letters each family's `latin` file really contains
 * (U+02BB ʻ for oʻ/gʻ, U+02BC ʼ for the tutuq belgisi). Verified against the
 * woff2 cmaps by __tests__/fonts.test.ts. A missing glyph is painted with the
 * visually identical U+2018 ‘ / U+2019 ’ (uzbekSafe) instead of a fallback-font
 * glyph with different weight/metrics. Many families have ʼ but not ʻ, so the
 * swap is per glyph. The source text (script.tts_text) is never changed —
 * only what is painted.
 */
export const FONT_UZ_GLYPHS: Record<string, UzGlyphs> = {
  "Plus Jakarta Sans": { okina: false, tutuq: false },
  Manrope: { okina: false, tutuq: false },
  "Playfair Display": { okina: true, tutuq: true },
  Anton: { okina: true, tutuq: true },
  Bangers: { okina: false, tutuq: false },
  "Bebas Neue": { okina: false, tutuq: true },
  Caveat: { okina: false, tutuq: true },
  Comfortaa: { okina: true, tutuq: true },
  "Cormorant Garamond": { okina: true, tutuq: true },
  "DM Serif Display": { okina: false, tutuq: false },
  "Exo 2": { okina: true, tutuq: true },
  Fraunces: { okina: false, tutuq: true },
  Fredoka: { okina: false, tutuq: false },
  Inter: { okina: true, tutuq: true },
  "JetBrains Mono": { okina: false, tutuq: true },
  Lora: { okina: true, tutuq: true },
  Montserrat: { okina: true, tutuq: true },
  Nunito: { okina: true, tutuq: true },
  Oswald: { okina: true, tutuq: true },
  Pacifico: { okina: false, tutuq: true },
  "PT Serif": { okina: false, tutuq: true },
  Rubik: { okina: false, tutuq: true },
  "Russo One": { okina: false, tutuq: false },
  "Space Grotesk": { okina: true, tutuq: true },
  Syne: { okina: false, tutuq: false },
  "Tenor Sans": { okina: false, tutuq: true },
  Unbounded: { okina: true, tutuq: true },
  "Yeseva One": { okina: false, tutuq: true },
};

/** First family name of a CSS font-family stack (`"A", B, sans-serif` → `A`). */
export const primaryFamily = (stack: string) => stack.split(",")[0]!.trim().replace(/^["']|["']$/g, "");

/**
 * Replace ʻ/ʼ with ‘/’ where the (primary) font lacks them. Accepts a family
 * name or a CSS stack. Unknown families are left untouched.
 */
export function uzbekSafe(text: string, family: string): string {
  const g = FONT_UZ_GLYPHS[primaryFamily(family)];
  if (!g) return text;
  let out = text;
  if (!g.okina) out = out.replace(/\u02BB/g, "\u2018");
  if (!g.tutuq) out = out.replace(/\u02BC/g, "\u2019");
  return out;
}

const GOOGLE: Record<string, () => void> = {
  "Plus Jakarta Sans": () =>
    loadJakarta("normal", { weights: ["800"], subsets: ["latin", "latin-ext"] }),
  Manrope: () =>
    loadManrope("normal", { weights: ["700", "800"], subsets: ["latin", "latin-ext", "cyrillic"] }),
  Inter: () => loadInter("normal", { weights: ["800"], subsets: ["latin", "latin-ext"] }),
  "Playfair Display": () =>
    loadPlayfair("normal", { weights: ["600", "700", "800"], subsets: ["latin", "latin-ext", "cyrillic"] }),
  Anton: () => loadAnton("normal", { weights: ["400"], subsets: ["latin", "latin-ext"] }),
};

/** Families that can still load from Google Fonts (network) without local files. */
export const GOOGLE_FONT_FAMILIES: readonly string[] = Object.keys(GOOGLE);

const requested = new Set<string>();

function loadLocal(family: string, faces: LocalFace[]): void {
  const handle = delayRender(`Loading local font ${family}`, { timeoutInMilliseconds: 30000 });
  Promise.all(
    faces.map(async (f) => {
      const face = new FontFace(family, `url(${staticFile(f.file)}) format("woff2")`, {
        weight: f.weight,
        unicodeRange: f.unicodeRange,
      });
      await face.load();
      document.fonts.add(face);
    }),
  )
    .catch((err) => {
      // Missing local files: fall back to Google Fonts (network) if we know the family.
      console.warn(`[fonts] local ${family} failed (${String(err)}), trying Google Fonts`);
      GOOGLE[family]?.();
    })
    .finally(() => continueRender(handle));
}

/**
 * Make sure `family` is loaded (idempotent) and return a CSS font-family stack.
 * Call during render (component body) — delayRender() blocks the frame until ready.
 */
export function ensureFont(family: string): string {
  if (typeof document !== "undefined" && !requested.has(family)) {
    requested.add(family);
    const local = LOCAL_FONTS[family];
    if (local) loadLocal(family, local);
    else GOOGLE[family]?.();
  }
  return `"${family}", "Plus Jakarta Sans", Inter, "Noto Sans", sans-serif`;
}
