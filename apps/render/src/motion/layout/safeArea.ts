// Instagram Reels UI-safe zones (1080×1920): the top bar (account / audio)
// covers ≈ 14 %, the caption + buttons block ≈ 22 % at the bottom, and the
// like/comment/share rail the right edge. Keep every text inside safeRect().

export const SAFE = { top: 0.14, bottom: 0.22, side: 0.05 } as const;

export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
  right: number;
  bottom: number;
}

/** Safe rectangle in px for a frame of `width × height`. */
export function safeRect(width = 1080, height = 1920, s: { top: number; bottom: number; side: number } = SAFE): Rect {
  const left = Math.round(width * s.side);
  const top = Math.round(height * s.top);
  const right = Math.round(width * (1 - s.side));
  const bottom = Math.round(height * (1 - s.bottom));
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}

/** Is `r` fully inside the safe rect? */
export function insideSafe(r: Pick<Rect, "left" | "top" | "width" | "height">, width = 1080, height = 1920): boolean {
  const s = safeRect(width, height);
  return r.left >= s.left && r.top >= s.top && r.left + r.width <= s.right && r.top + r.height <= s.bottom;
}

/**
 * Named regions inside the safe rect used by the Reel layout (px, 1080×1920):
 * - headline: hook / scene titles (upper part of the safe area)
 * - cta: CTA card (lower-middle, above the captions)
 * - captions: bottom band of the safe area (captions sit on its bottom edge = 22 %)
 */
export function regions(width = 1080, height = 1920) {
  const s = safeRect(width, height);
  const headline: Rect = { left: s.left, top: s.top + 40, width: s.width, height: Math.round(s.height * 0.42), right: s.right, bottom: 0 };
  headline.bottom = headline.top + headline.height;
  const captions: Rect = { left: s.left, top: s.bottom - 300, width: s.width, height: 300, right: s.right, bottom: s.bottom };
  const cta: Rect = { left: s.left, top: s.bottom - 330 - 440, width: s.width, height: 440, right: s.right, bottom: s.bottom - 330 };
  return { safe: s, headline, captions, cta };
}
