import React from "react";
import { easings } from "../easings";
import { mix, presence } from "../timing";
import { parseEmphasis } from "./parse";
import { clamp01, joinWords, TextBox, useLocal, Word } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "BlurFocus",
  description: "Sekin fokus: blur 20→0, harf oraligʻi keng→normal. Luxury / premium.",
  recommendedFor: ["title", "quote", "offer"],
  defaultDuration: 40,
};

/** Slow rack-focus: blur 20 → 0 px while letter-spacing tightens and the block settles. */
export const BlurFocus: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const p = presence(frame, { start: startFrame, duration: durationFrames ?? meta.defaultDuration, exitFrame, easing: easings.smoothOut, fps });
  const ls = style.letterSpacing ?? 0;
  return (
    <TextBox
      style={style}
      css={{
        opacity: clamp01(p * 1.3),
        filter: p < 0.999 ? `blur(${mix(p, 20, 0)}px)` : undefined,
        letterSpacing: `${mix(p, ls + 0.15, ls)}em`,
        transform: `scale(${mix(p, 1.08, 1)})`,
      }}
    >
      {joinWords(parseEmphasis(text).map((t, i) => <Word key={i} style={{ color: t.emph ? style.accent : style.color }}>{t.word}</Word>))}
    </TextBox>
  );
};
