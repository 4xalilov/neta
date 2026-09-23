// Transition registry: built-in @remotion/transitions (non-WebGL ones) + our
// custom presentations. pickTransition(name) → { presentation, timing }.
import { linearTiming, type TransitionPresentation, type TransitionTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { flip } from "@remotion/transitions/flip";
import { iris } from "@remotion/transitions/iris";
import { clockWipe } from "@remotion/transitions/clock-wipe";
import { none } from "@remotion/transitions/none";
import { easings, type EasingFn } from "../easings";
import { zoomPunch } from "./zoomPunch";
import { whipPan } from "./whipPan";
import { glitchCut } from "./glitchCut";
import { maskCircle } from "./maskCircle";
import { slice } from "./slice";
import { TRANSITIONS, isTransitionName, type TransitionName } from "./names";

export { zoomPunch, whipPan, glitchCut, maskCircle, slice };

export { TRANSITIONS, isTransitionName, type TransitionName };

export interface TransitionMeta {
  description: string;
  /** Recommended length in frames @30 fps. */
  frames: number;
  easing: EasingFn;
  builtIn: boolean;
}

export const TRANSITION_META: Record<TransitionName, TransitionMeta> = {
  fade: { description: "Yumshoq cross-fade (standart)", frames: 12, easing: easings.linear, builtIn: true },
  slide: { description: "Yangi kadr yondan surib kiradi", frames: 14, easing: easings.expoInOut, builtIn: true },
  wipe: { description: "Chiziqli parda (wipe)", frames: 14, easing: easings.expoInOut, builtIn: true },
  flip: { description: "3D varaq aylanishi", frames: 16, easing: easings.expoInOut, builtIn: true },
  iris: { description: "Doira ochilishi (klassik iris)", frames: 14, easing: easings.expoInOut, builtIn: true },
  clockWipe: { description: "Soat mili boʻyicha parda", frames: 16, easing: easings.expoInOut, builtIn: true },
  zoomPunch: { description: "Zarb bilan zoom-kesim + oq chaqnash", frames: 10, easing: easings.linear, builtIn: false },
  whipPan: { description: "Tez gorizontal burilish, yoʻnalishli motion-blur", frames: 12, easing: easings.linear, builtIn: false },
  glitchCut: { description: "Raqamli glitch kesim (tasmalar + RGB)", frames: 8, easing: easings.linear, builtIn: false },
  maskCircle: { description: "Aksent halqali doira-niqob ochilishi", frames: 16, easing: easings.linear, builtIn: false },
  slice: { description: "Vertikal boʻlaklar ketma-ket tushadi", frames: 16, easing: easings.linear, builtIn: false },
  none: { description: "Toʻgʻridan-toʻgʻri kesim", frames: 0, easing: easings.linear, builtIn: true },
};

export interface PickedTransition {
  name: TransitionName;
  presentation: TransitionPresentation<Record<string, unknown>>;
  timing: TransitionTiming;
  durationInFrames: number;
}

/**
 * Build a transition by name. Unknown names fall back to `fallback` (fade).
 * `durationInFrames` overrides the recommended length (the Reel clamps it to
 * the scene lengths). `accent` colours maskCircle's ring / zoomPunch's flash.
 */
export function pickTransition(
  name: string | null | undefined,
  opts: { width?: number; height?: number; durationInFrames?: number; accent?: string; index?: number; fallback?: TransitionName } = {},
): PickedTransition {
  const n: TransitionName = isTransitionName(name) ? name : (opts.fallback ?? "fade");
  const meta = TRANSITION_META[n];
  const durationInFrames = Math.max(n === "none" ? 1 : 2, Math.round(opts.durationInFrames ?? meta.frames) || 1);
  const width = opts.width ?? 1080;
  const height = opts.height ?? 1920;
  const alt = (opts.index ?? 0) % 2 === 0;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const presentations: Record<TransitionName, () => TransitionPresentation<any>> = {
    fade: () => fade(),
    slide: () => slide({ direction: alt ? "from-right" : "from-left" }),
    wipe: () => wipe({ direction: alt ? "from-left" : "from-right" }),
    flip: () => flip({ direction: alt ? "from-right" : "from-left" }),
    iris: () => iris({ width, height }),
    clockWipe: () => clockWipe({ width, height }),
    zoomPunch: () => zoomPunch(),
    whipPan: () => whipPan({ direction: alt ? "left" : "right" }),
    glitchCut: () => glitchCut({ seed: opts.index ?? 3 }),
    maskCircle: () => maskCircle({ ringColor: opts.accent }),
    slice: () => slice({ direction: alt ? "down" : "up" }),
    none: () => none(),
  };
  return {
    name: n,
    presentation: presentations[n]() as TransitionPresentation<Record<string, unknown>>,
    timing: linearTiming({ durationInFrames, easing: meta.easing }),
    durationInFrames,
  };
}
