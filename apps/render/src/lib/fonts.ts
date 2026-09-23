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

// Unicode ranges from Google Fonts. NOTE: U+02BB/U+02BC (Uzbek ʻ ʼ) live in `latin`.
const LATIN =
  "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD";
const LATIN_EXT =
  "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF";
const CYRILLIC = "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116";

interface LocalFace {
  file: string;
  weight: string;
  unicodeRange: string;
}

/** Files expected in public/fonts (see public/fonts/README.md). */
export const LOCAL_FONTS: Record<string, LocalFace[]> = {
  "Plus Jakarta Sans": [
    { file: "fonts/PlusJakartaSans-800-latin.woff2", weight: "800", unicodeRange: LATIN },
    { file: "fonts/PlusJakartaSans-800-latin-ext.woff2", weight: "800", unicodeRange: LATIN_EXT },
  ],
  Manrope: [
    { file: "fonts/Manrope-var-latin.woff2", weight: "200 800", unicodeRange: LATIN },
    { file: "fonts/Manrope-var-latin-ext.woff2", weight: "200 800", unicodeRange: LATIN_EXT },
    { file: "fonts/Manrope-var-cyrillic.woff2", weight: "200 800", unicodeRange: CYRILLIC },
  ],
};

const GOOGLE: Record<string, () => void> = {
  "Plus Jakarta Sans": () =>
    loadJakarta("normal", { weights: ["800"], subsets: ["latin", "latin-ext"] }),
  Manrope: () =>
    loadManrope("normal", { weights: ["700", "800"], subsets: ["latin", "latin-ext", "cyrillic"] }),
  Inter: () => loadInter("normal", { weights: ["800"], subsets: ["latin", "latin-ext"] }),
};

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
