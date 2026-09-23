// Pure text helpers for presets (no React): emphasis markup, line splitting,
// font auto-sizing, counter parsing. Unit-tested in __tests__/motion.test.ts.

export interface Token {
  word: string;
  /** Marked with *asterisks* by the Writer → accent / highlight. */
  emph: boolean;
}

/**
 * Split a headline into words. Words wrapped in `*…*` are emphasised
 * ("Bugun *50%* chegirma" → "50%" is emph). Multi-word spans work too
 * ("*juda arzon* narx"). When nothing is marked, `autoEmph` picks the longest
 * word (numbers win), so presets like Highlighter always have a target.
 */
export function parseEmphasis(text: string, autoEmph = false): Token[] {
  const tokens: Token[] = [];
  let inEmph = false;
  for (const raw of text.split(/\s+/).filter(Boolean)) {
    let w = raw;
    let emph = inEmph;
    if (w.startsWith("*")) {
      emph = true;
      inEmph = true;
      w = w.slice(1);
    }
    if (w.endsWith("*")) {
      w = w.slice(0, -1);
      inEmph = false;
    } else if (/\*[^\w]*$/u.test(w)) {
      // "*50%*," — punctuation after the closing star
      w = w.replace(/\*([^\w]*)$/u, "$1");
      inEmph = false;
    }
    w = w.replace(/\*/g, "");
    if (w) tokens.push({ word: w, emph });
  }
  if (autoEmph && tokens.length > 0 && !tokens.some((t) => t.emph)) {
    const score = (t: Token) => (/\d/.test(t.word) ? 100 : 0) + t.word.replace(/[^\p{L}\p{N}]/gu, "").length;
    let best = 0;
    tokens.forEach((t, i) => {
      if (score(t) > score(tokens[best]!)) best = i;
    });
    tokens[best] = { ...tokens[best]!, emph: true };
  }
  return tokens;
}

/** Remove the `*` emphasis markup. */
export const plainText = (text: string) => parseEmphasis(text).map((t) => t.word).join(" ");

/**
 * Greedy line split at word boundaries (explicit "\n" always breaks).
 * Returns token lines so emphasis survives.
 */
export function splitLines(text: string, maxChars: number, autoEmph = false): Token[][] {
  const out: Token[][] = [];
  for (const para of text.split(/\n+/)) {
    const tokens = parseEmphasis(para, autoEmph);
    let cur: Token[] = [];
    let len = 0;
    for (const t of tokens) {
      const add = (cur.length ? 1 : 0) + t.word.length;
      if (cur.length && len + add > maxChars) {
        out.push(cur);
        cur = [];
        len = 0;
      }
      len += (cur.length ? 1 : 0) + t.word.length;
      cur.push(t);
    }
    if (cur.length) out.push(cur);
  }
  return out;
}

/**
 * Pick a font size (px) so `text` fits `maxLines` lines of `boxWidth` px,
 * using an average glyph width of `charEm` × fontSize (≈0.62 for Plus Jakarta
 * 800, 0.45 for Anton, 0.56 for Playfair). Deterministic — no DOM measuring,
 * so it gives the same result in every render tab.
 */
export function fitFontSize(
  text: string,
  boxWidth: number,
  maxLines: number,
  base: number,
  charEm = 0.6,
  min = 40,
): number {
  const words = plainText(text).split(" ").filter(Boolean);
  if (words.length === 0) return base;
  const longest = Math.max(...words.map((w) => w.length));
  for (let size = base; size > min; size -= 2) {
    const perLine = Math.floor(boxWidth / (size * charEm));
    if (longest > perLine) continue;
    if (splitLines(words.join(" "), perLine).length <= maxLines) return size;
  }
  return min;
}

export interface CounterParts {
  prefix: string;
  value: number;
  suffix: string;
  decimals: number;
  /** Thousands separator used in the source ("" when none). */
  group: string;
  decimalSep: string;
}

/**
 * Find the first number in a string ("15%", "1 500 000 soʻm", "$2.5K",
 * "x3") and split it into prefix / value / suffix, remembering the formatting.
 * Returns null when the text has no number.
 */
export function parseCounter(text: string): CounterParts | null {
  const m = /(\d{1,3}(?:([   .,'’])\d{3})+|\d+)([.,]\d+)?/u.exec(text);
  if (!m) return null;
  const intPart = m[1]!;
  const group = m[2] ?? "";
  const frac = m[3] ?? "";
  const digits = intPart.replace(/[^\d]/g, "");
  const value = Number(digits + (frac ? "." + frac.slice(1) : ""));
  return {
    prefix: text.slice(0, m.index),
    value,
    suffix: text.slice(m.index + m[0].length),
    decimals: frac ? frac.length - 1 : 0,
    group,
    decimalSep: frac ? frac[0]! : ".",
  };
}

/** Format `value` like the source number (same grouping / decimals). */
export function formatCounter(value: number, p: CounterParts): string {
  const fixed = Math.abs(value).toFixed(p.decimals);
  const [int, frac] = fixed.split(".");
  const grouped = p.group ? int!.replace(/\B(?=(\d{3})+(?!\d))/g, p.group) : int!;
  return `${p.prefix}${value < 0 ? "-" : ""}${grouped}${frac ? p.decimalSep + frac : ""}${p.suffix}`;
}
