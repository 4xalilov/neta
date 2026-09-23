import React from "react";
import { easings } from "../easings";
import { mix, presence, staggerFrames } from "../timing";
import { splitLines } from "./parse";
import { TextBox, useLocal } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "SlideMask",
  description: "Qatorlar niqob ortidan pastdan sirgʻalib chiqadi — editorial / korporativ.",
  recommendedFor: ["title", "proof", "offer"],
  defaultDuration: 24,
};

/** Editorial line reveal: each line slides up from behind its own mask, staggered. */
export const SlideMask: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const perLine = Math.max(6, Math.floor((style.boxWidth ?? 972) / (style.fontSize * (style.charEm ?? 0.6))));
  const lines = splitLines(text, perLine);
  const total = durationFrames ?? meta.defaultDuration;
  const delays = staggerFrames(lines.length, total * 0.4, 5);
  const elDur = Math.max(10, total - (delays[delays.length - 1] ?? 0));
  return (
    <TextBox style={style}>
      {lines.map((line, li) => {
        const p = presence(frame, { start: startFrame, duration: elDur, delay: delays[li], exitFrame, easing: easings.expoOut, fps });
        return (
          <div key={li} style={{ overflow: "hidden", paddingBottom: "0.12em", marginBottom: "-0.12em" }}>
            <div style={{ transform: `translateY(${mix(p, 112, 0)}%) skewY(${mix(p, 4, 0)}deg)`, transformOrigin: "0% 100%" }}>
              {line.map((t, i) => (
                <React.Fragment key={i}>
                  {i > 0 ? " " : null}
                  <span style={{ color: t.emph ? style.accent : style.color }}>{t.word}</span>
                </React.Fragment>
              ))}
            </div>
          </div>
        );
      })}
    </TextBox>
  );
};
