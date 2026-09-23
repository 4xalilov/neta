import React from "react";
import { easings } from "../easings";
import { mix, presence, staggerFrames } from "../timing";
import { parseEmphasis } from "./parse";
import { chars, clamp01, joinWords, TextBox, useLocal, Word } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "CharCascade",
  description: "Har bir harf niqob ortidan pastdan koʻtariladi (y-offset + opacity), kaskad.",
  recommendedFor: ["title", "quote", "hook"],
  defaultDuration: 28,
};

/** Per-character y-offset + opacity cascade, each word clipped by a mask. */
export const CharCascade: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const tokens = parseEmphasis(text);
  const total = durationFrames ?? meta.defaultDuration;
  const count = tokens.reduce((n, t) => n + chars(t.word).length, 0);
  const delays = staggerFrames(count, total * 0.55, 1.2);
  const elDur = Math.max(10, total - (delays[delays.length - 1] ?? 0));
  let k = 0;
  return (
    <TextBox style={style}>
      {joinWords(
        tokens.map((t, wi) => (
          <Word
            key={wi}
            style={{
              overflow: "hidden",
              verticalAlign: "bottom",
              paddingBottom: "0.14em",
              marginBottom: "-0.14em",
              color: t.emph ? style.accent : style.color,
            }}
          >
            {chars(t.word).map((c, ci) => {
              const p = presence(frame, { start: startFrame, duration: elDur, delay: delays[k++], exitFrame, easing: easings.expoOut, fps });
              return (
                <span
                  key={ci}
                  style={{
                    display: "inline-block",
                    transform: `translateY(${mix(p, 105, 0)}%) rotate(${mix(p, 8, 0)}deg)`,
                    opacity: clamp01(p * 1.4),
                  }}
                >
                  {c}
                </span>
              );
            })}
          </Word>
        )),
      )}
    </TextBox>
  );
};
