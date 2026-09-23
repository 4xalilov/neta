import { describe, expect, it } from "vitest";
import { kenBurns, KB_SCALE_FROM, KB_SCALE_TO } from "../lib/kenBurns";

describe("kenBurns", () => {
  const D = 150;

  it("scales 1.0 → 1.12 over the scene and clamps outside it", () => {
    expect(kenBurns(0, D).scale).toBeCloseTo(KB_SCALE_FROM);
    expect(kenBurns(D, D).scale).toBeCloseTo(KB_SCALE_TO);
    expect(kenBurns(-20, D).scale).toBeCloseTo(1.0);
    expect(kenBurns(D + 50, D).scale).toBeCloseTo(1.12);
    expect(kenBurns(D / 2, D).scale).toBeCloseTo(1.06);
  });

  it("is monotonic and never exposes the image edge", () => {
    let prev = 0;
    for (let f = 0; f <= D; f++) {
      for (const idx of [0, 1]) {
        const t = kenBurns(f, D, idx);
        expect(t.scale).toBeGreaterThanOrEqual(1);
        expect(t.scale).toBeLessThanOrEqual(1.12 + 1e-9);
        const margin = ((t.scale - 1) / 2 / t.scale) * 100;
        expect(Math.abs(t.translateX)).toBeLessThanOrEqual(margin + 1e-9);
        expect(Math.abs(t.translateY)).toBeLessThanOrEqual(margin + 1e-9);
      }
      const s = kenBurns(f, D).scale;
      expect(s).toBeGreaterThanOrEqual(prev);
      prev = s;
    }
  });

  it("alternates pan direction between consecutive scenes", () => {
    const a = kenBurns(D, D, 0);
    const b = kenBurns(D, D, 1);
    expect(Math.sign(a.translateX)).toBe(-Math.sign(b.translateX));
    expect(a.translateX).not.toBe(0);
  });

  it("handles zero-length scenes", () => {
    expect(Number.isFinite(kenBurns(0, 0).scale)).toBe(true);
  });
});

describe("kenBurnsMode", async () => {
  const { kenBurnsMode } = await import("../lib/kenBurns");
  const D = 150;
  it.each(["in", "out", "left", "right", "none"] as const)("%s never exposes the image edge", (mode) => {
    for (let f = 0; f <= D; f += 5) {
      const t = kenBurnsMode(f, D, mode, 1);
      expect(t.scale).toBeGreaterThanOrEqual(1);
      const margin = ((t.scale - 1) / 2 / t.scale) * 100;
      expect(Math.abs(t.translateX)).toBeLessThanOrEqual(margin + 1e-9);
      expect(Math.abs(t.translateY)).toBeLessThanOrEqual(margin + 1e-9);
    }
  });

  it("in zooms in, out zooms out, left/right pan in opposite directions, none is static", () => {
    expect(kenBurnsMode(D, D, "in").scale).toBeGreaterThan(kenBurnsMode(0, D, "in").scale);
    expect(kenBurnsMode(D, D, "out").scale).toBeLessThan(kenBurnsMode(0, D, "out").scale);
    expect(Math.sign(kenBurnsMode(D, D, "left").translateX)).toBe(-Math.sign(kenBurnsMode(D, D, "right").translateX));
    expect(kenBurnsMode(70, D, "none")).toEqual({ scale: 1, translateX: 0, translateY: 0 });
    expect(kenBurnsMode(40, D, "in", 1)).toEqual(kenBurns(40, D, 1)); // default = legacy behaviour
  });
});
