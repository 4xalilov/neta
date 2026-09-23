import { describe, expect, it } from "vitest";
import { spring } from "remotion";
import { easings, springAt, springs } from "../motion/easings";
import { hash01, presence, revealProgress, staggerFrames } from "../motion/timing";
import {
  fitFontSize,
  formatCounter,
  getTextPreset,
  parseCounter,
  parseEmphasis,
  plainText,
  splitLines,
  TEXT_ANIMS,
  TEXT_PRESETS,
} from "../motion/text";
import { kineticBeats } from "../motion/text/Kinetic";

const samples = (n = 200) => Array.from({ length: n + 1 }, (_, i) => i / n);

describe("easings", () => {
  const monotonic = ["linear", "expoOut", "expoIn", "expoInOut", "smoothOut", "smoothIn"] as const;
  it.each(monotonic)("%s is monotonic, bounded to [0,1], f(0)=0, f(1)=1", (name) => {
    const f = easings[name];
    expect(f(0)).toBeCloseTo(0, 6);
    expect(f(1)).toBeCloseTo(1, 6);
    let prev = -Infinity;
    for (const t of samples()) {
      const v = f(t);
      expect(v).toBeGreaterThanOrEqual(-1e-9);
      expect(v).toBeLessThanOrEqual(1 + 1e-9);
      expect(v).toBeGreaterThanOrEqual(prev - 1e-9);
      prev = v;
    }
  });

  it.each(["backOut", "anticipate", "overshoot"] as const)("%s hits the endpoints and stays within [-0.2, 1.3]", (name) => {
    const f = easings[name];
    expect(f(0)).toBeCloseTo(0, 6);
    expect(f(1)).toBeCloseTo(1, 6);
    for (const t of samples()) {
      expect(f(t)).toBeGreaterThanOrEqual(-0.2);
      expect(f(t)).toBeLessThanOrEqual(1.3);
    }
  });

  it("overshoot / backOut really overshoot, anticipate really winds up", () => {
    expect(Math.max(...samples().map(easings.backOut))).toBeGreaterThan(1.05);
    expect(Math.max(...samples().map(easings.overshoot))).toBeGreaterThan(1.05);
    expect(Math.min(...samples().map(easings.anticipate))).toBeLessThan(-0.05);
  });

  it("clamps input outside [0,1]", () => {
    expect(easings.expoOut(-1)).toBe(0);
    expect(easings.expoOut(2)).toBe(1);
    expect(easings.backOut(5)).toBeCloseTo(1);
  });
});

describe("spring presets", () => {
  const fps = 30;
  it.each(Object.keys(springs) as (keyof typeof springs)[])("%s starts at 0, is bounded and settles at 1", (name) => {
    const vals = Array.from({ length: 120 }, (_, f) => spring({ frame: f, fps, config: springs[name] }));
    expect(vals[0]).toBeCloseTo(0, 3);
    for (const v of vals) {
      expect(v).toBeGreaterThanOrEqual(-1e-6);
      expect(v).toBeLessThanOrEqual(1.45);
    }
    expect(vals[119]!).toBeCloseTo(1, 2);
  });

  it("soft never overshoots, bouncy clearly does, snappy barely does", () => {
    const peak = (n: keyof typeof springs) => Math.max(...Array.from({ length: 120 }, (_, f) => spring({ frame: f, fps, config: springs[n] })));
    expect(peak("soft")).toBeLessThanOrEqual(1.0001);
    expect(peak("bouncy")).toBeGreaterThan(1.15);
    expect(peak("snappy")).toBeLessThan(1.06);
    // soft is monotonic
    let prev = 0;
    for (let f = 0; f < 120; f++) {
      const v = spring({ frame: f, fps, config: springs.soft });
      expect(v).toBeGreaterThanOrEqual(prev - 1e-9);
      prev = v;
    }
  });

  it("springAt waits for its delay", () => {
    expect(springAt(5, 30, "snappy", 10)).toBe(0);
    expect(springAt(40, 30, "snappy", 10)).toBeGreaterThan(0.9);
  });
});

describe("timing helpers", () => {
  it("staggerFrames: starts at 0, non-decreasing, fits the window, respects maxPer", () => {
    for (const [count, window, maxPer] of [[1, 10, 3], [5, 12, 4], [20, 12, 4], [8, 100, 3]] as const) {
      const d = staggerFrames(count, window, maxPer);
      expect(d).toHaveLength(count);
      expect(d[0]).toBe(0);
      for (let i = 1; i < d.length; i++) {
        expect(d[i]!).toBeGreaterThanOrEqual(d[i - 1]!);
        expect(d[i]! - d[i - 1]!).toBeLessThanOrEqual(maxPer + 1e-9);
      }
      expect(d[d.length - 1]!).toBeLessThanOrEqual(window + 1e-9);
    }
    expect(staggerFrames(0, 10)).toEqual([]);
  });

  it("revealProgress is clamped and monotonic", () => {
    expect(revealProgress(0, 10, 20)).toBe(0);
    expect(revealProgress(30, 10, 20)).toBe(1);
    expect(revealProgress(100, 10, 20)).toBe(1);
    expect(revealProgress(9, 10, 0)).toBe(0);
    expect(revealProgress(10, 10, 0)).toBe(1);
    let prev = 0;
    for (let f = 0; f < 40; f++) {
      const v = revealProgress(f, 10, 20);
      expect(v).toBeGreaterThanOrEqual(prev);
      prev = v;
    }
  });

  it("presence mirrors the entrance on exit", () => {
    const o = { start: 0, duration: 10, exitFrame: 50, exitDuration: 10 };
    expect(presence(0, o)).toBe(0);
    expect(presence(20, o)).toBe(1);
    expect(presence(49, o)).toBe(1);
    expect(presence(55, o)).toBeGreaterThan(0);
    expect(presence(55, o)).toBeLessThan(1);
    expect(presence(60, o)).toBe(0);
    expect(presence(20, { start: 0, duration: 10 })).toBe(1); // no exit
    // spring mode may overshoot but starts at 0 and ends at rest
    expect(presence(0, { start: 5, duration: 10, spring: "bouncy", fps: 30 })).toBe(0);
    expect(presence(90, { start: 5, duration: 10, spring: "bouncy", fps: 30 })).toBeCloseTo(1, 2);
  });

  it("hash01 is deterministic and in [0,1)", () => {
    expect(hash01(3, 7)).toBe(hash01(3, 7));
    for (let i = 0; i < 100; i++) {
      const v = hash01("s", i);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });
});

describe("text parsing", () => {
  it("parseEmphasis handles *single*, *multi word* spans and punctuation", () => {
    expect(parseEmphasis("Bugun *50%* chegirma")).toEqual([
      { word: "Bugun", emph: false },
      { word: "50%", emph: true },
      { word: "chegirma", emph: false },
    ]);
    expect(parseEmphasis("*juda arzon* narx").map((t) => t.emph)).toEqual([true, true, false]);
    expect(parseEmphasis("faqat *bugun*!").map((t) => [t.word, t.emph])).toEqual([
      ["faqat", false],
      ["bugun!", true],
    ]);
    expect(plainText("Narx *30%* arzon")).toBe("Narx 30% arzon");
  });

  it("autoEmph picks a number first, else the longest word", () => {
    expect(parseEmphasis("Narx 30% arzon", true).find((t) => t.emph)!.word).toBe("30%");
    expect(parseEmphasis("Oʻzbekcha sifat", true).find((t) => t.emph)!.word).toBe("Oʻzbekcha");
  });

  it("splitLines breaks at word boundaries and on \\n", () => {
    const lines = splitLines("Biznesingiz uchun aqlli yechim", 12);
    expect(lines.map((l) => l.map((t) => t.word).join(" "))).toEqual(["Biznesingiz", "uchun aqlli", "yechim"]);
    expect(splitLines("bir\nikki", 50)).toHaveLength(2);
  });

  it("fitFontSize shrinks long text and never goes below min", () => {
    const short = fitFontSize("Salom", 972, 3, 120, 0.62);
    const long = fitFontSize("Bu juda uzun sarlavha boʻlib u uch qatorga zoʻrgʻa sigʻadi, shuning uchun kichrayadi", 972, 3, 120, 0.62);
    expect(short).toBe(120);
    expect(long).toBeLessThan(short);
    expect(fitFontSize("a".repeat(500), 972, 1, 120, 0.62, 40)).toBe(40);
  });

  it("parseCounter / formatCounter keep the source formatting", () => {
    const p = parseCounter("15%")!;
    expect(p).toMatchObject({ prefix: "", value: 15, suffix: "%", decimals: 0 });
    expect(formatCounter(7, p)).toBe("7%");
    const som = parseCounter("1 500 000 soʻm")!;
    expect(som.value).toBe(1500000);
    expect(formatCounter(1500000, som)).toBe("1 500 000 soʻm");
    expect(formatCounter(12345, som)).toBe("12 345 soʻm");
    const dec = parseCounter("x2,5 tezroq")!;
    expect(dec).toMatchObject({ prefix: "x", value: 2.5, decimals: 1, decimalSep: "," });
    expect(formatCounter(1.25, dec)).toBe("x1,3 tezroq");
    expect(parseCounter("raqamsiz matn")).toBeNull();
  });

  it("kineticBeats makes short beats and isolates emphasised words", () => {
    const beats = kineticBeats(parseEmphasis("Bugun *faqat* bugun katta chegirma"));
    expect(beats.map((b) => b.map((t) => t.word).join(" "))).toEqual(["Bugun", "faqat", "bugun katta", "chegirma"]);
  });
});

describe("text preset registry", () => {
  it("has ≥ 12 presets, each with a component and complete meta", () => {
    expect(TEXT_ANIMS.length).toBeGreaterThanOrEqual(12);
    expect(Object.keys(TEXT_PRESETS).sort()).toEqual([...TEXT_ANIMS].sort());
    for (const name of TEXT_ANIMS) {
      const { Component, meta } = TEXT_PRESETS[name];
      expect(typeof Component).toBe("function");
      expect(meta.name).toBe(name);
      expect(meta.description.length).toBeGreaterThan(10);
      expect(meta.recommendedFor.length).toBeGreaterThan(0);
      expect(meta.defaultDuration).toBeGreaterThan(0);
    }
  });

  it("covers the Writer intents (hook / proof / cta)", () => {
    for (const intent of ["hook", "proof", "cta"] as const) {
      expect(TEXT_ANIMS.filter((n) => TEXT_PRESETS[n].meta.recommendedFor.includes(intent)).length).toBeGreaterThanOrEqual(2);
    }
  });

  it("getTextPreset falls back for unknown names", () => {
    expect(getTextPreset("Glitch").meta.name).toBe("Glitch");
    expect(getTextPreset("NoSuchAnim", "MaskWipe").meta.name).toBe("MaskWipe");
    expect(getTextPreset(null).meta.name).toBe("WordPop");
  });
});
