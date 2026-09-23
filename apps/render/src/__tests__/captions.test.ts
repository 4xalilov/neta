import { describe, expect, it } from "vitest";
import { activeWordIndex, evenWords, pageAt, pageScenes, pageWords, wrapWords, type Word } from "../lib/captions";

const text = (ws: Word[]) => ws.map((w) => w.w).join(" ");

describe("pageWords", () => {
  const words = evenWords(
    "Bugun biz sizga oʻzbekcha Reels qanday qilib avtomatik tayyorlanishini koʻrsatamiz, obuna boʻling",
    0,
    12,
  );

  it("keeps every page within maxChars and maxLines, breaking only at word boundaries", () => {
    const pages = pageWords(words, 42, 2);
    expect(pages.length).toBeGreaterThan(1);
    for (const p of pages) {
      expect(text(p.words).length).toBeLessThanOrEqual(42);
      expect(p.lines.length).toBeLessThanOrEqual(2);
      for (const line of p.lines) expect(text(line).length).toBeLessThanOrEqual(21);
      expect(p.lines.flat()).toEqual(p.words);
    }
    // No word lost or duplicated, order preserved.
    expect(pages.flatMap((p) => p.words).map((w) => w.w)).toEqual(words.map((w) => w.w));
  });

  it("respects a single-line limit", () => {
    const pages = pageWords(words, 20, 1);
    for (const p of pages) {
      expect(p.lines).toHaveLength(1);
      expect(text(p.words).length).toBeLessThanOrEqual(20);
    }
  });

  it("puts an over-long word on its own page instead of splitting it", () => {
    const long = "a".repeat(50);
    const pages = pageWords(
      [
        { w: "salom", start: 0, end: 0.4 },
        { w: long, start: 0.5, end: 1 },
        { w: "dunyo", start: 1.1, end: 1.5 },
      ],
      42,
      2,
    );
    expect(pages.map((p) => text(p.words))).toEqual(["salom", long, "dunyo"]);
  });

  it("starts a new page after a long pause and chains page timing", () => {
    const pages = pageWords(
      [
        { w: "bir", start: 0, end: 0.3 },
        { w: "ikki", start: 0.35, end: 0.7 },
        { w: "uch", start: 2.0, end: 2.4 },
      ],
      42,
      2,
      { breakOnGapS: 0.8, holdS: 0.5 },
    );
    expect(pages.map((p) => text(p.words))).toEqual(["bir ikki", "uch"]);
    expect(pages[0]!.start).toBe(0);
    expect(pages[0]!.end).toBe(2.0); // stays until the next page starts
    expect(pages[1]!.end).toBeCloseTo(2.9);
  });

  it("ignores blank words and sorts by start", () => {
    const pages = pageWords([
      { w: "ikki", start: 1, end: 1.5 },
      { w: "  ", start: 0.5, end: 0.6 },
      { w: " bir ", start: 0, end: 0.4 },
    ]);
    expect(pages).toHaveLength(1);
    expect(text(pages[0]!.words)).toBe("bir ikki");
  });

  it("returns no pages for no words", () => {
    expect(pageWords([])).toEqual([]);
  });
});

describe("wrapWords", () => {
  it("wraps greedily at the per-line budget", () => {
    const ws = evenWords("aaaa bbbb cccc dddd", 0, 4);
    expect(wrapWords(ws, 9).map(text)).toEqual(["aaaa bbbb", "cccc dddd"]);
  });
});

describe("pageScenes / pageAt / activeWordIndex", () => {
  const scene1 = evenWords("Salom! Bu Neta demosi.", 0.2, 3.8);
  const scene2 = evenWords("Har bir soʻz yonadi.", 4.0, 7.0);

  it("never lets a page span two scenes", () => {
    const pages = pageScenes([scene1, scene2]);
    expect(pages.map((p) => text(p.words))).toEqual(["Salom! Bu Neta demosi.", "Har bir soʻz yonadi."]);
    expect(pages[0]!.end).toBeLessThanOrEqual(pages[1]!.start);
  });

  it("finds the visible page and the active word", () => {
    const pages = pageScenes([scene1, scene2]);
    expect(pageAt(pages, 0.1)).toBeNull();
    const p = pageAt(pages, 1.2)!;
    expect(text(p.words)).toBe("Salom! Bu Neta demosi.");
    expect(p.words[activeWordIndex(p, 1.2)]!.w).toBe("Bu");
    // During the short gap after a word it stays highlighted.
    expect(activeWordIndex(p, scene1[0]!.end + 0.01)).toBe(0);
    expect(activeWordIndex(p, 0.1)).toBe(-1);
    expect(text(pageAt(pages, 5)!.words)).toBe("Har bir soʻz yonadi.");
  });
});
