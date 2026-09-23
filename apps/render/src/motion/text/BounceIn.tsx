import React from "react";
import { Trail } from "@remotion/motion-blur";
import { mix, presence } from "../timing";
import { parseEmphasis } from "./parse";
import { clamp01, groupTiming, joinWords, TextBox, useLocal, Word } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "BounceIn",
  description: "Spring overshoot bilan sakrab kiradi (bouncy), motion-blur izi bilan. CTA uchun.",
  recommendedFor: ["cta", "offer", "hook"],
  defaultDuration: 24,
};

const Inner: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const tokens = parseEmphasis(text);
  const { delays } = groupTiming(tokens.length, durationFrames ?? meta.defaultDuration, 3);
  return (
    <TextBox style={style}>
      {joinWords(
        tokens.map((t, i) => {
          const p = presence(frame, { start: startFrame, duration: 20, delay: delays[i], exitFrame, spring: "bouncy", fps });
          return (
            <Word
              key={i}
              style={{
                color: t.emph ? style.accent : style.color,
                transform: `translateY(${mix(p, 90, 0)}px) scale(${Math.max(0, p)})`,
                opacity: clamp01(p * 3),
                transformOrigin: "50% 100%",
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

/** Spring overshoot pop-in per word, with a short motion-blur trail. */
export const BounceIn: React.FC<TextPresetProps> = (props) => (
  <Trail layers={3} lagInFrames={0.6} trailOpacity={0.3}>
    <Inner {...props} />
  </Trail>
);
