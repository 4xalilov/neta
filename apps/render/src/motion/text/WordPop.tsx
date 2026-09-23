import React from "react";
import { Trail } from "@remotion/motion-blur";
import { easings } from "../easings";
import { mix, presence } from "../timing";
import { parseEmphasis } from "./parse";
import { clamp01, groupTiming, joinWords, TextBox, useLocal, Word } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "WordPop",
  description: "Soʻzma-soʻz scale + blur-in, stagger bilan; motion-blur izi (Trail).",
  recommendedFor: ["hook", "title", "offer"],
  defaultDuration: 20,
};

const Inner: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const tokens = parseEmphasis(text);
  const { delays, elDur } = groupTiming(tokens.length, durationFrames ?? meta.defaultDuration, 3);
  return (
    <TextBox style={style}>
      {joinWords(
        tokens.map((t, i) => {
          const p = presence(frame, { start: startFrame, duration: elDur, delay: delays[i], exitFrame, easing: easings.backOut, fps });
          const q = clamp01(p);
          return (
            <Word
              key={i}
              style={{
                color: t.emph ? style.accent : style.color,
                opacity: clamp01(q * 1.6),
                transform: `translateY(${mix(q, 34, 0)}px) scale(${mix(p, 0.55, 1)})`,
                filter: q < 0.999 ? `blur(${mix(q, 14, 0)}px)` : undefined,
                transformOrigin: "50% 80%",
              }}
            >
              {t.word}
            </Word>
          );
        }),
      )}
    </TextBox>
  );
};

/** Word-by-word scale + blur-in with stagger, motion-blurred via @remotion/motion-blur <Trail>. */
export const WordPop: React.FC<TextPresetProps> = (props) => (
  <Trail layers={3} lagInFrames={0.7} trailOpacity={0.35}>
    <Inner {...props} />
  </Trail>
);
