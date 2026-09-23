// Text-reveal preset registry — pure data + components (docs/11-motion-library.md "Matn animatsiyalari").
import type { TextPreset } from "./types";
import { TEXT_ANIMS, isTextAnim, type TextAnim } from "./names";
import { WordPop, meta as wordPop } from "./WordPop";
import { CharCascade, meta as charCascade } from "./CharCascade";
import { MaskWipe, meta as maskWipe } from "./MaskWipe";
import { TypeWriter, meta as typeWriter } from "./TypeWriter";
import { SlideMask, meta as slideMask } from "./SlideMask";
import { Glitch, meta as glitch } from "./Glitch";
import { Counter, meta as counter } from "./Counter";
import { Highlighter, meta as highlighter } from "./Highlighter";
import { Split3D, meta as split3D } from "./Split3D";
import { Scramble, meta as scramble } from "./Scramble";
import { Kinetic, meta as kinetic } from "./Kinetic";
import { Outline2Fill, meta as outline2Fill } from "./Outline2Fill";
import { BounceIn, meta as bounceIn } from "./BounceIn";
import { BlurFocus, meta as blurFocus } from "./BlurFocus";

export { TEXT_ANIMS, isTextAnim, type TextAnim };

export const TEXT_PRESETS: Record<TextAnim, TextPreset> = {
  WordPop: { Component: WordPop, meta: wordPop },
  CharCascade: { Component: CharCascade, meta: charCascade },
  MaskWipe: { Component: MaskWipe, meta: maskWipe },
  TypeWriter: { Component: TypeWriter, meta: typeWriter },
  SlideMask: { Component: SlideMask, meta: slideMask },
  Glitch: { Component: Glitch, meta: glitch },
  Counter: { Component: Counter, meta: counter },
  Highlighter: { Component: Highlighter, meta: highlighter },
  Split3D: { Component: Split3D, meta: split3D },
  Scramble: { Component: Scramble, meta: scramble },
  Kinetic: { Component: Kinetic, meta: kinetic },
  Outline2Fill: { Component: Outline2Fill, meta: outline2Fill },
  BounceIn: { Component: BounceIn, meta: bounceIn },
  BlurFocus: { Component: BlurFocus, meta: blurFocus },
};

/** Preset by name; unknown names fall back to `fallback` (theme default). */
export function getTextPreset(name: string | null | undefined, fallback: TextAnim = "WordPop"): TextPreset {
  return TEXT_PRESETS[isTextAnim(name) ? name : fallback];
}
