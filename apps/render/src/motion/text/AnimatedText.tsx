import React from "react";
import { uzbekSafe } from "../../lib/fonts";
import { getTextPreset, type TextAnim } from "./registry";
import type { TextPresetProps } from "./types";

/**
 * Dispatch to a text preset by name. Also makes the text safe for the font:
 * families without U+02BB/U+02BC get the visually identical ‘ ’ (see
 * lib/fonts.ts FONT_UZ_GLYPHS).
 */
export const AnimatedText: React.FC<TextPresetProps & { anim: TextAnim | string | null | undefined; fallback?: TextAnim }> = ({
  anim,
  fallback,
  text,
  ...rest
}) => {
  const { Component } = getTextPreset(anim, fallback);
  return <Component text={uzbekSafe(text, rest.style.fontFamily)} {...rest} />;
};
