import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { noise2D } from "@remotion/noise";

/** Camera-shake offset at `frame` (px / deg). Pure — exported for tests. */
export function shakeAt(frame: number, intensity: number, seed = "shake", frequency = 0.35) {
  const t = frame * frequency;
  return {
    x: noise2D(`${seed}x`, t, 0) * intensity,
    y: noise2D(`${seed}y`, 0, t) * intensity * 0.8,
    r: noise2D(`${seed}r`, t, t) * intensity * 0.04,
  };
}

/**
 * Handheld / impact camera shake around the children (noise-driven, smooth).
 * `intensity` in px (6 = subtle handheld, 24 = impact). `decayFrames` > 0 makes
 * it an impact that dies out; the frame is over-scaled so edges never show.
 */
export const Shake: React.FC<{ intensity?: number; decayFrames?: number; seed?: string; children: React.ReactNode }> = ({
  intensity = 8,
  decayFrames = 0,
  seed = "shake",
  children,
}) => {
  const frame = useCurrentFrame();
  const k = decayFrames > 0 ? Math.max(0, 1 - frame / decayFrames) ** 2 : 1;
  const s = shakeAt(frame, intensity * k, seed);
  const overscan = 1 + (2 * intensity) / 1080;
  return (
    <AbsoluteFill style={{ transform: `translate(${s.x}px, ${s.y}px) rotate(${s.r}deg) scale(${overscan})` }}>{children}</AbsoluteFill>
  );
};
