// Pure timing helpers shared by every text preset / caption / fx.
// No React here — unit-tested in __tests__/motion.test.ts.
import { spring, type SpringConfig } from "remotion";
import { easings, springs, type EasingFn, type SpringName } from "./easings";

const clamp01 = (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : t);

/**
 * Start delays (frames) for `count` staggered elements. The whole stagger fits
 * into `window` frames, but no two neighbours are more than `maxPer` frames
 * apart (so short titles don't crawl). Always non-decreasing, first = 0.
 */
export function staggerFrames(count: number, window: number, maxPer = 4): number[] {
  if (count <= 0) return [];
  if (count === 1) return [0];
  const per = Math.max(0, Math.min(maxPer, window / (count - 1)));
  return Array.from({ length: count }, (_, i) => i * per);
}

/**
 * Eased progress in [0,1] of an animation that starts at `start` and lasts
 * `duration` frames. Clamped outside; duration ≤ 0 → a hard cut at `start`.
 */
export function revealProgress(frame: number, start: number, duration: number, easing: EasingFn = easings.expoOut): number {
  if (duration <= 0) return frame >= start ? 1 : 0;
  return easing(clamp01((frame - start) / duration));
}

export interface PresenceOptions {
  /** First frame of the entrance. */
  start: number;
  /** Entrance length in frames. */
  duration: number;
  /** Frame at which the exit (mirrored entrance) begins; undefined = never exits. */
  exitFrame?: number | null;
  /** Exit length (defaults to `duration`, capped at 15 frames). */
  exitDuration?: number;
  /** Delay of this element inside the group (stagger), applied to entrance and exit. */
  delay?: number;
  /** Easing for eased mode (ignored when `spring` is set). */
  easing?: EasingFn;
  /** Use a spring (may overshoot > 1) instead of an easing for the entrance. */
  spring?: SpringName | Partial<SpringConfig>;
  fps?: number;
}

/**
 * Progress of an element that enters and (optionally) exits:
 * 0 → hidden, 1 → at rest. The exit mirrors the entrance (progress runs back
 * 1 → 0), so every preset gets an exit animation for free.
 */
export function presence(frame: number, o: PresenceOptions): number {
  const delay = o.delay ?? 0;
  const start = o.start + delay;
  let pIn: number;
  if (o.spring) {
    const config = typeof o.spring === "string" ? springs[o.spring] : o.spring;
    pIn = frame < start ? 0 : spring({ frame: frame - start, fps: o.fps ?? 30, config });
  } else {
    pIn = revealProgress(frame, start, o.duration, o.easing ?? easings.expoOut);
  }
  if (o.exitFrame === undefined || o.exitFrame === null) return pIn;
  const exitDur = o.exitDuration ?? Math.min(15, Math.max(1, o.duration));
  const pOut = revealProgress(frame, o.exitFrame + delay * 0.5, exitDur, easings.smoothIn);
  return Math.min(pIn, 1 - pOut);
}

/** Map a progress value (possibly overshooting) linearly onto [from, to]. */
export const mix = (p: number, from: number, to: number) => from + (to - from) * p;

/** Deterministic 0..1 hash for (seed, i) — cheap alternative to remotion random() in loops. */
export function hash01(seed: number | string, i = 0): number {
  const str = `${seed}:${i}`;
  let h = 2166136261;
  for (let k = 0; k < str.length; k++) {
    h ^= str.charCodeAt(k);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 100000) / 100000;
}
