import React from "react";
import { presence } from "../timing";
import { parseEmphasis } from "./parse";
import { chars, joinWords, TextBox, useLocal, Word } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "TypeWriter",
  description: "Harfma-harf yoziladi, miltillovchi kursor bilan (layout sakramaydi).",
  recommendedFor: ["problem", "quote", "hook"],
  defaultDuration: 36,
};

/** Characters typed one by one (layout reserved up front) with a blinking cursor. */
export const TypeWriter: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const tokens = parseEmphasis(text);
  const total = tokens.reduce((n, t) => n + chars(t.word).length, 0);
  const dur = durationFrames ?? Math.min(60, Math.max(meta.defaultDuration, total * 1.3));
  const p = presence(frame, { start: startFrame, duration: dur, exitFrame, easing: (t) => t, fps });
  const shown = Math.round(p * total);
  const typing = p > 0 && p < 1;
  const blinkOn = Math.floor((frame - startFrame) / (fps * 0.45)) % 2 === 0;
  const cursorVisible = frame >= startFrame && (typing || blinkOn) && p > 0;
  let k = 0;
  let cursorPlaced = false;
  const cursor = (
    <span key="cursor" style={{ position: "relative", display: "inline-block", width: 0 }}>
      <span
        style={{
          position: "absolute",
          left: "0.04em",
          top: "0.08em",
          width: "0.09em",
          height: "0.95em",
          background: style.accent,
          opacity: cursorVisible ? 1 : 0,
        }}
      />
    </span>
  );
  return (
    <TextBox style={style}>
      {joinWords(
        tokens.map((t, wi) => (
          <Word key={wi} style={{ color: t.emph ? style.accent : style.color }}>
            {chars(t.word).flatMap((c, ci) => {
              const idx = k++;
              const nodes: React.ReactNode[] = [
                <span key={ci} style={{ opacity: idx < shown ? 1 : 0 }}>
                  {c}
                </span>,
              ];
              if (!cursorPlaced && idx === shown - 1) {
                cursorPlaced = true;
                nodes.push(cursor);
              }
              if (!cursorPlaced && shown === 0 && idx === 0) {
                cursorPlaced = true;
                nodes.unshift(cursor);
              }
              return nodes;
            })}
          </Word>
        )),
      )}
    </TextBox>
  );
};
