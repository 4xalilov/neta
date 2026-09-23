import { describe, expect, it } from "vitest";
import { BRAND_DEFAULTS, defaultProps, parseReelsProps, reelsPropsSchema, truncateProps } from "../props";

describe("props schema", () => {
  it("applies docs/08 brand defaults", () => {
    const p = parseReelsProps({ scenes: [{ imageUrl: "x.png", durationS: 3 }] });
    expect(p.brand).toEqual({
      font: "Plus Jakarta Sans",
      color: "#E6EAF2",
      accent: "#FACC15",
      bg: "#0B0F19",
      surface: "#131A2A",
      logoUrl: null,
    });
    expect(p.scenes[0]!.words).toEqual([]);
  });

  it("fills missing brand fields individually", () => {
    const p = parseReelsProps({
      scenes: [{ imageUrl: "x.png", durationS: 3 }],
      brand: { accent: "#22D3EE", logoUrl: "https://cdn/logo.png" },
    });
    expect(p.brand.accent).toBe("#22D3EE");
    expect(p.brand.color).toBe(BRAND_DEFAULTS.color);
    expect(p.brand.logoUrl).toBe("https://cdn/logo.png");
  });

  it("accepts null for optional fields (Python None)", () => {
    const p = parseReelsProps({
      audioUrl: null,
      cta: null,
      scenes: [{ imageUrl: "x.png", depthUrl: null, durationS: 3, subtitle: null, words: [] }],
    });
    expect(p.audioUrl).toBeNull();
  });

  it("rejects invalid input", () => {
    expect(reelsPropsSchema.safeParse({ scenes: [] }).success).toBe(false);
    expect(reelsPropsSchema.safeParse({ scenes: [{ imageUrl: "x", durationS: 0 }] }).success).toBe(false);
    expect(reelsPropsSchema.safeParse({ scenes: [{ imageUrl: "x", durationS: 1, words: [{ w: "a", start: -1, end: 1 }] }] }).success).toBe(false);
    expect(
      reelsPropsSchema.safeParse({ scenes: [{ imageUrl: "x", durationS: 1 }], brand: { accent: "not-a-colour" } }).success,
    ).toBe(false);
  });

  it("demo props are valid and offline (data URIs only)", () => {
    const p = parseReelsProps(defaultProps);
    expect(p.scenes).toHaveLength(3);
    for (const s of p.scenes) {
      expect(s.imageUrl.startsWith("data:image/svg+xml")).toBe(true);
      expect(s.words.length).toBeGreaterThan(0);
    }
    expect(p.scenes.some((s) => s.depthUrl)).toBe(true);
  });

  it("truncateProps cuts the timeline to N seconds", () => {
    const t = truncateProps(defaultProps, 5);
    expect(t.scenes.map((s) => s.durationS)).toEqual([4, 1]);
    expect(t.scenes.flatMap((s) => s.words).every((w) => w.start < 5)).toBe(true);
    expect(truncateProps(defaultProps, 0)).toBe(defaultProps);
  });
});
