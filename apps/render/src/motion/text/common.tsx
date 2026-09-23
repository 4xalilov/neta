import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { staggerFrames } from "../timing";
import type { TextStyle } from "./types";

/** Base CSS for a text block rendered with `style`. */
export function baseTextStyle(s: TextStyle): React.CSSProperties {
  return {
    fontFamily: s.fontFamily,
    fontWeight: s.fontWeight,
    fontSize: s.fontSize,
    color: s.color,
    lineHeight: s.lineHeight ?? 1.08,
    letterSpacing: `${s.letterSpacing ?? -0.01}em`,
    textTransform: s.uppercase ? "uppercase" : undefined,
    textAlign: s.align ?? "center",
    WebkitTextStroke: s.stroke ? `${s.stroke}px ${s.strokeColor ?? "#000"}` : undefined,
    paintOrder: s.stroke ? "stroke fill" : undefined,
    textShadow: s.shadow,
    fontKerning: "normal",
    whiteSpace: "normal",
    overflowWrap: "normal",
    wordBreak: "keep-all",
    margin: 0,
  };
}

/**
 * Full-size box that positions the text block (presets fill their parent; the
 * parent — TitleBlock / SafeArea region — decides where on screen it sits).
 */
export const TextBox: React.FC<{ style: TextStyle; children: React.ReactNode; css?: React.CSSProperties }> = ({
  style,
  children,
  css,
}) => {
  const align = style.align ?? "center";
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center",
        pointerEvents: "none",
      }}
    >
      <div style={{ ...baseTextStyle(style), maxWidth: "100%", ...css }}>{children}</div>
    </AbsoluteFill>
  );
};

/** Frame + fps of the enclosing Sequence. */
export function useLocal() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return { frame, fps };
}

/**
 * Entrance timing for `count` staggered elements inside a total window of
 * `total` frames: stagger uses ≤ 45 % of the window (≤ maxPer per step), the
 * rest is each element's own animation (≥ 8 frames).
 */
export function groupTiming(count: number, total: number, maxPer = 3) {
  const delays = staggerFrames(count, total * 0.45, maxPer);
  const last = delays[delays.length - 1] ?? 0;
  return { delays, elDur: Math.max(8, total - last) };
}

/** Inline-block word wrapper; words are separated by real spaces so lines wrap. */
export const Word: React.FC<{ style?: React.CSSProperties; children: React.ReactNode }> = ({ style, children }) => (
  <span style={{ display: "inline-block", whiteSpace: "pre", ...style }}>{children}</span>
);

/** Join rendered words with breakable spaces. */
export function joinWords(nodes: React.ReactNode[]): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  nodes.forEach((n, i) => {
    if (i > 0) out.push(" ");
    out.push(n);
  });
  return out;
}

/** Split into grapheme-ish chars (keeps ʻ with its letter visually; surrogate-safe). */
export const chars = (w: string) => Array.from(w);

export const clamp01 = (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : t);
