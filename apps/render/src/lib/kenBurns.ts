import { interpolate } from "remotion";

export const KB_SCALE_FROM = 1.0;
export const KB_SCALE_TO = 1.12;

export interface KenBurnsTransform {
  scale: number;
  /** Percent of the element width, applied after scale. */
  translateX: number;
  /** Percent of the element height, applied after scale. */
  translateY: number;
}

/**
 * Ken Burns transform for `frame` of a scene lasting `durationInFrames`.
 * Scale 1.0 → 1.12 (docs/08). The pan direction alternates per scene index
 * (even scenes drift right/down, odd scenes left/up) and is always kept inside
 * the margin the zoom creates, so image edges never become visible.
 */
export function kenBurns(frame: number, durationInFrames: number, sceneIndex = 0): KenBurnsTransform {
  const d = Math.max(1, durationInFrames);
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  const scale = interpolate(frame, [0, d], [KB_SCALE_FROM, KB_SCALE_TO], clamp);
  // Visible margin per side in the element's own (pre-scale) percent units.
  const margin = ((scale - 1) / 2 / scale) * 100;
  const progress = interpolate(frame, [0, d], [-1, 1], clamp);
  const dir = sceneIndex % 2 === 0 ? 1 : -1;
  return {
    scale,
    translateX: dir * progress * margin * 0.9,
    translateY: dir * progress * margin * 0.4,
  };
}

export const kenBurnsCss = (t: KenBurnsTransform) =>
  `scale(${t.scale}) translate(${t.translateX}%, ${t.translateY}%)`;

export type KenBurnsMode = "in" | "out" | "left" | "right" | "none";

/**
 * Ken Burns by mode (scene prop `kenBurns`):
 * - `in`   : the classic push-in above (1.0 → 1.12, alternating diagonal drift)
 * - `out`  : pull-out 1.12 → 1.0, drift reversed
 * - `left` / `right`: constant 1.12 zoom, horizontal pan across the margin
 * - `none` : static (scale 1)
 * Every mode keeps the pan inside the zoom margin (no visible image edge).
 */
export function kenBurnsMode(frame: number, durationInFrames: number, mode: KenBurnsMode = "in", sceneIndex = 0): KenBurnsTransform {
  const d = Math.max(1, durationInFrames);
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  switch (mode) {
    case "none":
      return { scale: 1, translateX: 0, translateY: 0 };
    case "out": {
      const t = kenBurns(d - Math.min(Math.max(frame, 0), d), d, sceneIndex);
      return t;
    }
    case "left":
    case "right": {
      const scale = KB_SCALE_TO;
      const margin = ((scale - 1) / 2 / scale) * 100;
      const p = interpolate(frame, [0, d], [-1, 1], clamp);
      const dir = mode === "left" ? -1 : 1;
      return { scale, translateX: dir * p * margin * 0.9, translateY: 0 };
    }
    default:
      return kenBurns(frame, d, sceneIndex);
  }
}
