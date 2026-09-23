import type React from "react";

/** Visual style a text preset renders with (resolved from the StyleTheme). */
export interface TextStyle {
  /** CSS font-family stack (from ensureFont()). */
  fontFamily: string;
  fontWeight: number;
  /** Lighter weight used by Kinetic's "small" beats. */
  lightWeight?: number;
  /** Font size in px (1080×1920 canvas). */
  fontSize: number;
  color: string;
  /** Accent colour: emphasised words, cursor, wipe bar, glitch channel. */
  accent: string;
  /** Marker / box colour behind key words (Highlighter). Defaults to accent. */
  highlight?: string;
  /** Text colour on top of the highlight (contrast). */
  onHighlight?: string;
  align?: "left" | "center" | "right";
  uppercase?: boolean;
  /** em */
  letterSpacing?: number;
  lineHeight?: number;
  /** Outline width in px (0 = none). */
  stroke?: number;
  strokeColor?: string;
  /** CSS text-shadow. */
  shadow?: string;
  /** Width (px) of the box the text lives in — for presets that split lines themselves. */
  boxWidth?: number;
  /** Height (px) of the box (Kinetic scales its stack to fit). */
  boxHeight?: number;
  /** Average glyph width in em for this font (line-split estimate). */
  charEm?: number;
}

export interface TextPresetProps {
  text: string;
  /** Frame (relative to the enclosing Sequence) at which the entrance starts. */
  startFrame: number;
  /** Entrance length in frames (preset default when omitted). */
  durationFrames?: number;
  /** Frame at which the mirrored exit starts; omit to stay on screen. */
  exitFrame?: number | null;
  style: TextStyle;
}

export type TextIntent = "hook" | "problem" | "proof" | "offer" | "cta" | "title" | "quote";

export interface TextPresetMeta {
  name: string;
  description: string;
  /** AIDA stages / intents this preset suits best. */
  recommendedFor: TextIntent[];
  /** Default entrance length in frames at 30 fps. */
  defaultDuration: number;
}

export interface TextPreset {
  Component: React.FC<TextPresetProps>;
  meta: TextPresetMeta;
}
