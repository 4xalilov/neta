// Pure caption helpers (no React) — unit-tested in __tests__/captions.test.ts.

export interface Word {
  /** The word as displayed (punctuation attached). Same source as TTS text (script.tts_text). */
  w: string;
  /** Seconds from composition start. */
  start: number;
  /** Seconds from composition start. */
  end: number;
}

export interface CaptionPage {
  /** Words per line; at most `maxLines` lines. */
  lines: Word[][];
  /** Flat word list in order. */
  words: Word[];
  /** Seconds: first word start. */
  start: number;
  /** Seconds: page stays on screen until this time (next page start or last word end + hold). */
  end: number;
}

export interface PageOptions {
  /** Pause (s) between two words that forces a new page even if it would fit. */
  breakOnGapS?: number;
  /** How long (s) the last page lingers after its last word ends. */
  holdS?: number;
}

const lineLength = (line: Word[]) =>
  line.reduce((n, w, i) => n + w.w.length + (i > 0 ? 1 : 0), 0);

/**
 * Greedy word wrap into lines of at most `perLine` chars. A single word longer
 * than `perLine` gets its own line (words are never split).
 */
export function wrapWords(words: Word[], perLine: number): Word[][] {
  const lines: Word[][] = [];
  let cur: Word[] = [];
  for (const word of words) {
    if (cur.length > 0 && lineLength([...cur, word]) > perLine) {
      lines.push(cur);
      cur = [];
    }
    cur.push(word);
  }
  if (cur.length) lines.push(cur);
  return lines;
}

/**
 * Group timed words into caption pages (docs/08: 2 lines, ≤ 42 chars).
 *
 * - `maxChars` is the budget for the whole page (text joined with single spaces);
 *   lines get ceil(maxChars / maxLines) chars each (21 for 42/2 — what fits on a
 *   1080px frame at the Reels font size).
 * - Pages break only at word boundaries; a page never wraps to more than
 *   `maxLines` lines. An over-long single word still forms its own page.
 * - A pause longer than `breakOnGapS` between words starts a new page.
 */
export function pageWords(
  words: Word[],
  maxChars = 42,
  maxLines = 2,
  opts: PageOptions = {},
): CaptionPage[] {
  const breakOnGapS = opts.breakOnGapS ?? 0.8;
  const holdS = opts.holdS ?? 0.6;
  const perLine = Math.max(1, Math.ceil(maxChars / Math.max(1, maxLines)));

  const clean = words
    .filter((w) => w.w.trim().length > 0)
    .map((w) => ({ ...w, w: w.w.trim() }))
    .sort((a, b) => a.start - b.start);

  const groups: Word[][] = [];
  let cur: Word[] = [];
  for (const word of clean) {
    if (cur.length > 0) {
      const next = [...cur, word];
      const prev = cur[cur.length - 1]!;
      const tooLong = lineLength(next) > maxChars;
      const tooManyLines = wrapWords(next, perLine).length > maxLines;
      const pause = word.start - prev.end > breakOnGapS;
      if (tooLong || tooManyLines || pause) {
        groups.push(cur);
        cur = [];
      }
    }
    cur.push(word);
  }
  if (cur.length) groups.push(cur);

  return groups.map((g, i) => {
    const start = g[0]!.start;
    const lastEnd = Math.max(...g.map((w) => w.end));
    const nextStart = groups[i + 1]?.[0]?.start;
    const end = nextStart !== undefined ? Math.max(lastEnd, nextStart) : lastEnd + holdS;
    return { lines: wrapWords(g, perLine), words: g, start, end };
  });
}

/** Page visible at time t (seconds), or null. */
export function pageAt(pages: CaptionPage[], t: number): CaptionPage | null {
  return pages.find((p) => t >= p.start && t < p.end) ?? null;
}

/**
 * Index (within page.words) of the word to highlight at time t: the last word
 * that has started. Stays on the last spoken word during short pauses.
 */
export function activeWordIndex(page: CaptionPage, t: number): number {
  let idx = -1;
  page.words.forEach((w, i) => {
    if (t >= w.start) idx = i;
  });
  return idx;
}

/** Evenly distribute a sentence over [start, end] — used for demo props and tests. */
export function evenWords(text: string, start: number, end: number): Word[] {
  const parts = text.split(/\s+/).filter(Boolean);
  const step = (end - start) / Math.max(1, parts.length);
  return parts.map((w, i) => ({
    w,
    start: +(start + i * step).toFixed(3),
    end: +(start + (i + 1) * step - 0.02).toFixed(3),
  }));
}

/**
 * Page several word groups (one per scene) independently, so no caption page
 * spans a scene cut, and clip each page's end to the next page's start.
 */
export function pageScenes(
  groups: Word[][],
  maxChars = 42,
  maxLines = 2,
  opts: PageOptions = {},
): CaptionPage[] {
  const pages = groups.flatMap((g) => pageWords(g, maxChars, maxLines, opts));
  pages.sort((a, b) => a.start - b.start);
  return pages.map((p, i) => {
    const next = pages[i + 1];
    return next && next.start < p.end ? { ...p, end: Math.max(p.start, next.start) } : p;
  });
}
