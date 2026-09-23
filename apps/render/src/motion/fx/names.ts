// Pure fx name list + metadata (no React) — used by zod schemas.
/**
 * Overlay fx are drawn on top of the scene layer; wrapper fx (shake,
 * chromatic) transform the scene layer itself; `glow` applies to headlines.
 */
export const FX_NAMES = [
  "grain",
  "vignette",
  "lightLeak",
  "particles",
  "lensFlare",
  "progressBar",
  "shake",
  "chromatic",
  "glow",
] as const;
export type FxName = (typeof FX_NAMES)[number];

export const FX_META: Record<FxName, { kind: "overlay" | "wrapper" | "text"; description: string }> = {
  grain: { kind: "overlay", description: "Plyonka donadorligi (FilmGrain, @remotion/noise)" },
  vignette: { kind: "overlay", description: "Burchaklarni qoraytirish, diqqat markazga" },
  lightLeak: { kind: "overlay", description: "Iliq yorugʻlik sizishi (sahna boshida)" },
  particles: { kind: "overlay", description: "Suzuvchi zarrachalar / oltin chang" },
  lensFlare: { kind: "overlay", description: "Yengil linza chaqnashi" },
  progressBar: { kind: "overlay", description: "Tepada ingichka progress chizigʻi" },
  shake: { kind: "wrapper", description: "Kamera silkinishi (sahna boshida zarba)" },
  chromatic: { kind: "wrapper", description: "RGB ajralish (kesimda kuchli, keyin 1–2 px)" },
  glow: { kind: "text", description: "Sarlavha atrofida neon nur" },
};

export const isFxName = (n: unknown): n is FxName => typeof n === "string" && (FX_NAMES as readonly string[]).includes(n);

/** Keep known names, drop duplicates / unknowns (LLM-friendly). */
export const normalizeFx = (names: ReadonlyArray<string> | null | undefined): FxName[] =>
  Array.from(new Set((names ?? []).filter(isFxName)));
