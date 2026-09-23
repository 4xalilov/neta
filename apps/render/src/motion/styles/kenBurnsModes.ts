// Pure list (no zod / React) — shared by props.ts and the StyleTheme schema.
export const KEN_BURNS_MODES = ["in", "out", "left", "right", "none"] as const;
export type KenBurnsMode = (typeof KEN_BURNS_MODES)[number];
