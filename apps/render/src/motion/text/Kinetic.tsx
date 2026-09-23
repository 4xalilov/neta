import React from "react";
import { interpolate } from "remotion";
import { mix, presence, staggerFrames } from "../timing";
import { parseEmphasis, type Token } from "./parse";
import { clamp01, TextBox, useLocal } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "Kinetic",
  description: "Kinetik tipografiya: katta-kichik ritm, qalin/ingichka almashadi, qatorlar urilib kiradi.",
  recommendedFor: ["hook", "offer", "cta"],
  defaultDuration: 30,
};

/** Group words into short beats (≤ 2 short words or 1 long word per line). */
export function kineticBeats(tokens: Token[], maxChars = 11): Token[][] {
  const beats: Token[][] = [];
  let cur: Token[] = [];
  for (const t of tokens) {
    const len = cur.reduce((n, x) => n + x.word.length + 1, 0) + t.word.length;
    if (cur.length && (len > maxChars || cur.length >= 2 || t.emph || cur.some((x) => x.emph))) {
      beats.push(cur);
      cur = [];
    }
    cur.push(t);
  }
  if (cur.length) beats.push(cur);
  return beats;
}

/**
 * Words stacked in beats that alternate BIG/bold and small/light (emphasised
 * words are always big + accent). Big beats slam in (scale 1.7 → 1, heavy
 * spring), small beats slide in from alternating sides. The stack slowly
 * pushes in afterwards so the frame never feels static.
 */
export const Kinetic: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const beats = kineticBeats(parseEmphasis(text));
  const total = durationFrames ?? meta.defaultDuration;
  const delays = staggerFrames(beats.length, total * 0.6, 6);
  const big = (i: number) => beats[i]!.some((t) => t.emph) || i % 2 === 0;
  // Fit the stack into the box height (big lines ≈ 1.2 × fontSize tall, small ≈ 0.7 ×).
  const height = beats.reduce((h, _, i) => h + (big(i) ? 1.18 : 0.74) * style.fontSize, 0);
  const box = style.boxHeight ?? 700;
  const fit = Math.min(1, box / Math.max(1, height));
  const drift = interpolate(frame - startFrame, [0, 150], [1, 1.05], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <TextBox style={style} css={{ lineHeight: 1, transform: `scale(${drift})` }}>
      {beats.map((beat, i) => {
        const isBig = big(i);
        const p = presence(frame, { start: startFrame, duration: 14, delay: delays[i], exitFrame, spring: isBig ? "heavy" : "snappy", fps });
        const side = i % 4 === 1 ? -1 : 1;
        const emph = beat.some((t) => t.emph);
        return (
          <div
            key={i}
            style={{
              fontSize: style.fontSize * (isBig ? 1.18 : 0.66) * fit,
              fontWeight: isBig ? style.fontWeight : (style.lightWeight ?? 400),
              color: emph ? style.accent : isBig ? style.color : style.accent,
              letterSpacing: isBig ? `${style.letterSpacing ?? -0.02}em` : "0.08em",
              textTransform: isBig ? (style.uppercase ? "uppercase" : undefined) : "uppercase",
              opacity: clamp01(p * 2),
              transform: isBig
                ? `scale(${mix(p, 1.7, 1)})`
                : `translateX(${mix(clamp01(p), 180 * side, 0)}px)`,
              filter: isBig && p < 0.95 ? `blur(${mix(clamp01(p), 10, 0)}px)` : undefined,
              margin: `${isBig ? 0.02 : 0.1}em 0`,
              whiteSpace: "nowrap",
            }}
          >
            {beat.map((t) => t.word).join(" ")}
          </div>
        );
      })}
    </TextBox>
  );
};
