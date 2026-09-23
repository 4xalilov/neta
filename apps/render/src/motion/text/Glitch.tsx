import React from "react";
import { easings } from "../easings";
import { hash01, presence, revealProgress } from "../timing";
import { plainText } from "./parse";
import { clamp01, TextBox, useLocal } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "Glitch",
  description: "6 kadr RGB-split + titroq, soʻng tinchlanadi. Neon / tech hook uchun.",
  recommendedFor: ["hook", "problem"],
  defaultDuration: 12,
};

const GLITCH_FRAMES = 6;

/** RGB split + jitter for 6 frames, then settles (exit replays the glitch in reverse). */
export const Glitch: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const dur = durationFrames ?? meta.defaultDuration;
  const settle = dur - GLITCH_FRAMES;
  const visible = presence(frame, { start: startFrame, duration: 2, exitFrame: exitFrame != null ? exitFrame + GLITCH_FRAMES : null, exitDuration: 2, fps });
  // Glitch intensity: 1 during the first GLITCH_FRAMES, then decays over `settle` frames.
  let k = 1 - revealProgress(frame, startFrame + GLITCH_FRAMES, Math.max(1, settle), easings.expoOut);
  if (exitFrame != null && frame >= exitFrame) k = Math.max(k, revealProgress(frame, exitFrame, GLITCH_FRAMES, (t) => t));
  if (frame < startFrame) k = 0;
  const seed = Math.floor(frame / 2); // jitter changes every 2 frames
  const j = (i: number) => (hash01(seed, i) - 0.5) * 2; // -1..1
  const dx = 26 * k * j(1);
  const dy = 6 * k * j(2);
  const split = 10 + 18 * k;
  const words = plainText(text);
  const layer = (color: string, x: number, y: number, blend?: React.CSSProperties["mixBlendMode"], extra?: React.CSSProperties) => (
    <TextBox style={{ ...style, color, stroke: 0, shadow: undefined }} css={{ transform: `translate(${x}px, ${y}px)`, mixBlendMode: blend, ...extra }}>
      {words}
    </TextBox>
  );
  // Horizontal slice displacement on the main layer while glitching.
  const sliceTop = hash01(seed, 7) * 70;
  const sliceH = 8 + hash01(seed, 8) * 18;
  return (
    <div style={{ position: "absolute", inset: 0, opacity: visible }}>
      {k > 0.02 ? layer("#FF1F5A", dx + split * clamp01(k * 3) * 0.6, dy, "screen", { opacity: 0.9 * k }) : null}
      {k > 0.02 ? layer("#00E5FF", dx - split * clamp01(k * 3) * 0.6, -dy, "screen", { opacity: 0.9 * k }) : null}
      <TextBox style={style} css={{ transform: `translate(${dx * 0.4}px, 0) skewX(${-8 * k * j(3)}deg)` }}>
        {words}
      </TextBox>
      {k > 0.25 ? (
        <TextBox
          style={{ ...style, color: style.accent }}
          css={{ transform: `translate(${40 * k * j(9)}px, 0)`, clipPath: `inset(${sliceTop}% 0 ${Math.max(0, 100 - sliceTop - sliceH)}% 0)` }}
        >
          {words}
        </TextBox>
      ) : null}
    </div>
  );
};
