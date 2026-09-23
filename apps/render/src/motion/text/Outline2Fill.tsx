import React from "react";
import { easings } from "../easings";
import { mix, presence, revealProgress } from "../timing";
import { parseEmphasis } from "./parse";
import { clamp01, joinWords, TextBox, useLocal, Word } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "Outline2Fill",
  description: "Avval kontur (stroke) matn paydo boʻladi, soʻng pastdan yuqoriga rang bilan toʻladi.",
  recommendedFor: ["title", "offer", "cta"],
  defaultDuration: 30,
};

/** Stroke-only text appears, then a solid fill wipes up from the baseline. */
export const Outline2Fill: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const total = durationFrames ?? meta.defaultDuration;
  const outline = presence(frame, { start: startFrame, duration: Math.round(total * 0.4), exitFrame, easing: easings.expoOut, fps });
  let fill = revealProgress(frame, startFrame + Math.round(total * 0.35), Math.round(total * 0.65), easings.expoInOut);
  if (exitFrame != null) fill = Math.min(fill, 1 - revealProgress(frame, exitFrame - 8, 10, easings.smoothIn));
  const tokens = parseEmphasis(text);
  const words = (filled: boolean) =>
    joinWords(
      tokens.map((t, i) => (
        <Word key={i} style={{ color: filled ? (t.emph ? style.accent : style.color) : "transparent" }}>
          {t.word}
        </Word>
      )),
    );
  const strokeW = Math.max(2, Math.round(style.fontSize / 34));
  return (
    <TextBox style={style} css={{ display: "grid", opacity: clamp01(outline * 1.4), transform: `scale(${mix(outline, 0.94, 1)})` }}>
      <div style={{ gridArea: "1 / 1", WebkitTextStroke: `${strokeW}px ${style.color}`, textShadow: "none", paintOrder: "normal" }}>{words(false)}</div>
      <div style={{ gridArea: "1 / 1", clipPath: `inset(${(1 - fill) * 100}% -5% -5% -5%)` }}>{words(true)}</div>
    </TextBox>
  );
};
