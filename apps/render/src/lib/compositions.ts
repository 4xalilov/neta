export const COMPOSITION_IDS = ["ReelsBasic", "ReelsParallax"] as const;
export type CompositionId = (typeof COMPOSITION_IDS)[number];
