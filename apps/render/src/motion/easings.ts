// Easing curves + spring presets for the motion library (docs/11-motion-library.md).
// Everything here is pure math (no React) so it can be unit-tested in Node.
import { Easing, spring, type SpringConfig } from "remotion";

export type EasingFn = (t: number) => number;

const clamp01 = (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : t);

/**
 * After-Effects style curves. All map [0,1] → [0,1] with f(0)=0, f(1)=1.
 * "overshoot" / "back" / "anticipate" intentionally leave [0,1] in between
 * (that is the point) — use them for scale / position, not for opacity.
 */
export const easings = {
  linear: (t: number) => clamp01(t),
  /** Fast start, long soft landing — the default "pro" ease-out (AE Easy Ease Out ×). */
  expoOut: (t: number) => (t >= 1 ? 1 : t <= 0 ? 0 : 1 - Math.pow(2, -10 * t)),
  expoIn: (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : Math.pow(2, 10 * (t - 1))),
  expoInOut: (t: number) => {
    if (t <= 0) return 0;
    if (t >= 1) return 1;
    return t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2;
  },
  /** Cubic-bezier(0.16, 1, 0.3, 1) — Apple / Motion "smooth out". */
  smoothOut: Easing.bezier(0.16, 1, 0.3, 1) as EasingFn,
  /** Cubic-bezier(0.7, 0, 0.84, 0) — accelerate out of frame (exits). */
  smoothIn: Easing.bezier(0.7, 0, 0.84, 0) as EasingFn,
  /** Ease-out with a small overshoot past 1 (≈ +10 %), then settles. */
  backOut: (t: number) => {
    const x = clamp01(t);
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
  },
  /** Pulls back below 0 first (wind-up), then shoots to 1. */
  anticipate: (t: number) => {
    const x = clamp01(t);
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return c3 * x * x * x - c1 * x * x;
  },
  /** Stronger overshoot (≈ +20 %) with a damped wobble — "pop" feel. */
  overshoot: (t: number) => {
    const x = clamp01(t);
    if (x === 0 || x === 1) return x;
    return 1 - Math.exp(-6 * x) * Math.cos(x * Math.PI * 2.4) * (1 - x * 0.2);
  },
} satisfies Record<string, EasingFn>;

export type EasingName = keyof typeof easings;

/** Spring presets (Remotion `spring()` configs). */
export const springs = {
  /** Quick, almost no overshoot — UI chips, captions. */
  snappy: { damping: 20, stiffness: 260, mass: 0.6 },
  /** Slow & smooth, no bounce — luxury / editorial. */
  soft: { damping: 26, stiffness: 70, mass: 1 },
  /** Weighty landing, tiny overshoot — big headlines. */
  heavy: { damping: 16, stiffness: 120, mass: 1.6 },
  /** Playful, visible overshoot — CTA, emoji, BounceIn. */
  bouncy: { damping: 9, stiffness: 180, mass: 0.7 },
} satisfies Record<string, Partial<SpringConfig>>;

export type SpringName = keyof typeof springs;

/** spring() with a named preset, starting at `delay` frames. Returns 0 before the delay. */
export function springAt(
  frame: number,
  fps: number,
  preset: SpringName | Partial<SpringConfig> = "snappy",
  delay = 0,
  durationInFrames?: number,
): number {
  const config = typeof preset === "string" ? springs[preset] : preset;
  return spring({ frame: frame - delay, fps, config, durationInFrames });
}
