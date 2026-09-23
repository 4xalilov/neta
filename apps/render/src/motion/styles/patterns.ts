// Pure list of background pattern names (no React) — used by the StyleTheme schema.
// SVG tiles live in components/patterns.ts.
export const PATTERNS = [
  /** Uzbek ikat (abr): stacked zigzag diamonds — navruz. */
  "ikat",
  /** Adras silk: soft wavy vertical bands — bazaar. */
  "adras",
  /** Suzani embroidery: medallion rosettes — suzani-red. */
  "suzani",
  /** Girih: 8-point star lattice of Samarkand tilework — registan-blue. */
  "girih",
  /** Crescent + scattered stars — ramadan-night. */
  "stars",
  "dots",
  "grid",
  /** Ruled notebook lines. */
  "lines",
  /** Diagonal speed stripes. */
  "stripes",
  /** Comic halftone dots. */
  "halftone",
  "confetti",
  /** CRT scanlines. */
  "scanlines",
  /** Newsprint fibres. */
  "paper",
  /** Synthwave perspective grid + sun. */
  "retroGrid",
  "waves",
] as const;
export type PatternName = (typeof PATTERNS)[number];
