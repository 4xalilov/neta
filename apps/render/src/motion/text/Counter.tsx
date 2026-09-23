import React from "react";
import { easings } from "../easings";
import { mix, presence, revealProgress } from "../timing";
import { formatCounter, parseCounter, plainText } from "./parse";
import { clamp01, TextBox, useLocal } from "./common";
import type { TextPresetMeta, TextPresetProps } from "./types";

export const meta: TextPresetMeta = {
  name: "Counter",
  description: "Raqam 0 dan qiymatgacha sanaladi, formatni saqlaydi (\"15%\", \"1 500 000 soʻm\").",
  recommendedFor: ["proof", "offer"],
  defaultDuration: 40,
};

/**
 * Number tween with the source formatting kept (grouping, decimals, prefix /
 * suffix). The number and its attached unit ("%", "x") use the accent colour.
 * Text without a number falls back to a simple rise-in.
 */
export const Counter: React.FC<TextPresetProps> = ({ text, startFrame, durationFrames, exitFrame, style }) => {
  const { frame, fps } = useLocal();
  const dur = durationFrames ?? meta.defaultDuration;
  const clean = plainText(text);
  const parts = parseCounter(clean);
  const appear = presence(frame, { start: startFrame, duration: 12, exitFrame, easing: easings.backOut, fps });
  const count = revealProgress(frame, startFrame, dur, easings.expoOut);
  if (!parts) {
    return (
      <TextBox style={style} css={{ opacity: clamp01(appear), transform: `translateY(${mix(clamp01(appear), 40, 0)}px)` }}>
        {clean}
      </TextBox>
    );
  }
  const value = parts.value * count;
  const shown = formatCounter(parts.decimals === 0 ? Math.round(value) : value, parts);
  // Attach the unit right after the number ("15%" / "x3") to the accent span.
  const numText = shown.slice(parts.prefix.length, shown.length - parts.suffix.length);
  const unit = /^\S*/u.exec(parts.suffix)?.[0] ?? "";
  const rest = parts.suffix.slice(unit.length);
  return (
    <TextBox style={style} css={{ opacity: clamp01(appear * 1.5), transform: `scale(${mix(appear, 0.82, 1)})`, fontVariantNumeric: "tabular-nums" }}>
      {parts.prefix}
      <span style={{ color: style.accent, whiteSpace: "nowrap" }}>
        {numText}
        {unit}
      </span>
      {rest}
    </TextBox>
  );
};
