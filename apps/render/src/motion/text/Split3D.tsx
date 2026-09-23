import React from "react";
import { mix, presence } from "../timing";
import { parseEmphasis } from "./parse";
import { clamp01, groupTiming, joinWords, TextBox, useLocal, Word } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "Split3D",
  description: "Soʻzlar perspektivada rotateX bilan \"yiqilib\" turadi (3D flip-in).",
  recommendedFor: ["title", "offer", "hook"],
  defaultDuration: 26,
};

/** Words flip in around their baseline (rotateX -95° → 0) with perspective. */
export const Split3D: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const tokens = parseEmphasis(text);
  const { delays } = groupTiming(tokens.length, durationFrames ?? meta.defaultDuration, 3);
  return (
    <TextBox style={style} css={{ perspective: 900 }}>
      {joinWords(
        tokens.map((t, i) => {
          const p = presence(frame, { start: startFrame, duration: 16, delay: delays[i], exitFrame, spring: "heavy", fps });
          return (
            <Word
              key={i}
              style={{
                color: t.emph ? style.accent : style.color,
                transform: `rotateX(${mix(p, -95, 0)}deg) translateZ(0)`,
                transformOrigin: "50% 100% -0.3em",
                opacity: clamp01(p * 2),
                backfaceVisibility: "hidden",
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
