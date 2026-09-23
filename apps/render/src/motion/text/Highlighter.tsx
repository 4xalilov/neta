import React from "react";
import { easings } from "../easings";
import { mix, presence, revealProgress } from "../timing";
import { parseEmphasis } from "./parse";
import { clamp01, groupTiming, joinWords, TextBox, useLocal, Word } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "Highlighter",
  description: "Matn chiqadi, keyin kalit soʻz (*…* yoki eng uzun/raqamli) ortida marker chiziladi.",
  recommendedFor: ["proof", "offer", "problem"],
  defaultDuration: 30,
};

/** Words rise in, then a marker stroke is drawn behind the key word(s) (`*word*`). */
export const Highlighter: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const total = durationFrames ?? meta.defaultDuration;
  const tokens = parseEmphasis(text, true);
  const inWin = Math.round(total * 0.5);
  const { delays, elDur } = groupTiming(tokens.length, inWin, 2);
  const markStart = startFrame + inWin - 2;
  const markDur = total - inWin + 2;
  const hl = style.highlight ?? style.accent;
  const on = style.onHighlight ?? "#0B0F19";
  return (
    <TextBox style={style}>
      {joinWords(
        tokens.map((t, i) => {
          const p = presence(frame, { start: startFrame, duration: elDur, delay: delays[i], exitFrame, easing: easings.expoOut, fps });
          let m = t.emph ? revealProgress(frame, markStart, markDur, easings.expoInOut) : 0;
          if (t.emph && exitFrame != null) m = Math.min(m, 1 - revealProgress(frame, exitFrame - 6, 8, easings.smoothIn));
          return (
            <Word
              key={i}
              style={{
                position: "relative",
                margin: t.emph ? "0 0.14em" : undefined,
                opacity: clamp01(p * 1.5),
                transform: `translateY(${mix(p, 40, 0)}px)`,
                color: style.color,
                zIndex: 1,
              }}
            >
              {t.emph ? (
                <span
                  style={{
                    position: "absolute",
                    left: "-0.14em",
                    right: "-0.14em",
                    top: "0.06em",
                    bottom: "-0.02em",
                    background: hl,
                    borderRadius: "0.14em 0.3em 0.18em 0.32em",
                    transform: "rotate(-1.6deg)",
                    clipPath: `inset(-10% ${(1 - m) * 100}% -10% 0)`,
                    zIndex: -1,
                  }}
                />
              ) : null}
              {t.word}
              {t.emph && m > 0 ? (
                // "Ink under the marker": the same word in the on-highlight colour,
                // clipped exactly like the marker so the colour flips where it passes.
                <span
                  aria-hidden
                  style={{
                    position: "absolute",
                    inset: 0,
                    color: on,
                    textShadow: "none",
                    WebkitTextStroke: "0px transparent",
                    clipPath: `inset(-20% calc(${(1 - m) * 100}% - 0.14em) -20% -0.2em)`,
                  }}
                >
                  {t.word}
                </span>
              ) : null}
            </Word>
          );
        }),
      )}
    </TextBox>
  );
};
