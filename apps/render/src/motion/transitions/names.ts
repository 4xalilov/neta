// Pure list of transition names (no React) — used by zod schemas.
export const TRANSITIONS = [
  "fade",
  "slide",
  "wipe",
  "flip",
  "iris",
  "clockWipe",
  "zoomPunch",
  "whipPan",
  "glitchCut",
  "maskCircle",
  "slice",
  "none",
] as const;
export type TransitionName = (typeof TRANSITIONS)[number];
export const isTransitionName = (n: unknown): n is TransitionName =>
  typeof n === "string" && (TRANSITIONS as readonly string[]).includes(n);
