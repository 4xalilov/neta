import React from "react";
import { easings } from "../easings";
import { presence, revealProgress, staggerFrames } from "../timing";
import { splitLines } from "./parse";
import { TextBox, useLocal } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "MaskWipe",
  description: "Aksent chiziq chapdan oʻngga yurib, orqasidan matnni ochadi (clip-path), qatorma-qator.",
  recommendedFor: ["title", "cta", "offer"],
  defaultDuration: 22,
};

/**
 * clip-path reveal left → right led by an accent bar, one line after another
 * (each line is its own fit-content box, so the bar travels exactly to the end
 * of the text). The bar collapses when its line is done; exit wipes back.
 */
export const MaskWipe: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const total = durationFrames ?? meta.defaultDuration;
  const perLine = Math.max(6, Math.floor((style.boxWidth ?? 972) / (style.fontSize * (style.charEm ?? 0.6))));
  const lines = splitLines(text, perLine);
  const delays = staggerFrames(lines.length, total * 0.35, 5);
  const dur = Math.max(10, total - (delays[delays.length - 1] ?? 0));
  const exiting = exitFrame != null && frame >= exitFrame;
  const align = style.align ?? "center";
  return (
    <TextBox style={style} css={{ display: "flex", flexDirection: "column", alignItems: align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center" }}>
      {lines.map((line, li) => {
        const d = delays[li] ?? 0;
        const p = presence(frame, { start: startFrame, duration: dur, delay: d, exitFrame, easing: easings.expoInOut, fps });
        const barHide = exiting ? 1 - revealProgress(frame, exitFrame! + d * 0.5, 4) : revealProgress(frame, startFrame + d + dur, 8, easings.expoOut);
        return (
          <div key={li} style={{ position: "relative", width: "fit-content", whiteSpace: "nowrap" }}>
            <div style={{ clipPath: `inset(-0.2em ${(1 - p) * 100}% -0.2em -0.1em)` }}>
              {line.map((t, i) => (
                <React.Fragment key={i}>
                  {i > 0 ? " " : null}
                  <span style={{ color: t.emph ? style.accent : style.color }}>{t.word}</span>
                </React.Fragment>
              ))}
            </div>
            <div
              style={{
                position: "absolute",
                top: "0.02em",
                bottom: "0.02em",
                left: `calc(${p * 100}% - 0.05em)`,
                width: "0.1em",
                background: style.accent,
                borderRadius: "0.04em",
                transform: `scaleY(${Math.max(0, 1 - barHide)})`,
                opacity: p <= 0.001 || barHide >= 0.999 ? 0 : 1,
                boxShadow: `0 0 24px ${style.accent}88`,
              }}
            />
          </div>
        );
      })}
    </TextBox>
  );
};
