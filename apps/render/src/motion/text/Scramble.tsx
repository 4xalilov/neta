import React from "react";
import { hash01, presence } from "../timing";
import { parseEmphasis } from "./parse";
import { chars, joinWords, TextBox, useLocal, Word } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "Scramble",
  description: "Tasodifiy belgilar chapdan oʻngga haqiqiy harflarga aylanadi (decode effekti).",
  recommendedFor: ["hook", "problem", "proof"],
  defaultDuration: 30,
};

const GLYPHS = "ABCDEFGHJKLMNPQRSTUVXYZ0123456789#%&@$*+=?";

/** Random glyphs resolve left → right into the real text. Layout is reserved (no jumping). */
export const Scramble: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const tokens = parseEmphasis(text);
  const total = tokens.reduce((n, t) => n + chars(t.word).length, 0);
  const dur = durationFrames ?? meta.defaultDuration;
  const p = presence(frame, { start: startFrame, duration: dur, exitFrame, easing: (t) => t, fps });
  const tick = Math.floor(frame / 2);
  let k = 0;
  return (
    <TextBox style={style}>
      {joinWords(
        tokens.map((t, wi) => (
          <Word key={wi} style={{ color: t.emph ? style.accent : style.color }}>
            {chars(t.word).map((c, ci) => {
              const idx = k++;
              // Each char starts scrambling a bit before it resolves.
              const resolveAt = (idx + 1) / (total + 1);
              const startAt = Math.max(0, resolveAt - 0.35);
              const resolved = p >= resolveAt;
              const active = p > startAt && !resolved;
              const g = GLYPHS[Math.floor(hash01(tick, idx) * GLYPHS.length)]!;
              return (
                <span key={ci} style={{ position: "relative", display: "inline-block" }}>
                  <span style={{ opacity: resolved ? 1 : 0 }}>{c}</span>
                  {active ? (
                    <span style={{ position: "absolute", left: 0, right: 0, textAlign: "center", color: style.accent, opacity: 0.85 }}>{g}</span>
                  ) : null}
                </span>
              );
            })}
          </Word>
        )),
      )}
    </TextBox>
  );
};
