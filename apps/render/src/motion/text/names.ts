// Pure list of text preset names (no React) — used by zod schemas.
/** Valid `textAnim` values (props + StyleTheme). Keep in sync with TEXT_PRESETS. */
export const TEXT_ANIMS = [
  "WordPop",
  "CharCascade",
  "MaskWipe",
  "TypeWriter",
  "SlideMask",
  "Glitch",
  "Counter",
  "Highlighter",
  "Split3D",
  "Scramble",
  "Kinetic",
  "Outline2Fill",
  "BounceIn",
  "BlurFocus",
] as const;
export type TextAnim = (typeof TEXT_ANIMS)[number];

export const isTextAnim = (name: unknown): name is TextAnim =>
  typeof name === "string" && (TEXT_ANIMS as readonly string[]).includes(name);
