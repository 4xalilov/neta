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

describe("props schema — motion library fields", () => {
  it("old props (no style fields) still parse, with style = bold and scene extras null/undefined", () => {
    const p = parseReelsProps({ scenes: [{ imageUrl: "x.png", durationS: 3 }] });
    expect(p.style).toBe("bold");
    expect(p.hookText).toBeUndefined();
    expect(p.captionPreset).toBeUndefined();
    const s = p.scenes[0]!;
    expect([s.title, s.textAnim, s.transition, s.fx, s.kenBurns, s.captionPreset]).toEqual([
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
    ]);
  });

  it("parses every new field", () => {
    const p = parseReelsProps({
      style: "neon",
      hookText: "Bugun *50%* chegirma",
      captionPreset: "boxHighlight",
      scenes: [
        {
          imageUrl: "x.png",
          durationS: 3,
          title: "*1 500 000* soʻm",
          textAnim: "Counter",
          transition: "whipPan",
          fx: ["shake", "lightLeak"],
          kenBurns: "left",
          captionPreset: "bigWord",
        },
      ],
    });
    expect(p).toMatchObject({ style: "neon", hookText: "Bugun *50%* chegirma", captionPreset: "boxHighlight" });
    expect(p.scenes[0]).toMatchObject({
      title: "*1 500 000* soʻm",
      textAnim: "Counter",
      transition: "whipPan",
      fx: ["shake", "lightLeak"],
      kenBurns: "left",
      captionPreset: "bigWord",
    });
  });

  it("is lenient with LLM mistakes: unknown enum values become null instead of failing the job", () => {
    const p = parseReelsProps({
      captionPreset: "hormozi",
      scenes: [{ imageUrl: "x.png", durationS: 3, textAnim: "Explode", transition: "warp", kenBurns: "zoom", captionPreset: 5 }],
    });
    expect(p.captionPreset).toBeNull();
    expect(p.scenes[0]).toMatchObject({ textAnim: null, transition: null, kenBurns: null, captionPreset: null });
    // …and accepts Python None everywhere.
    const n = parseReelsProps({
      style: "bold",
      hookText: null,
      captionPreset: null,
      scenes: [{ imageUrl: "x.png", durationS: 3, title: null, textAnim: null, transition: null, fx: null, kenBurns: null, captionPreset: null }],
    });
    expect(n.scenes[0]!.fx).toBeNull();
  });

  it("demo props showcase hook + titles", () => {
    const p = parseReelsProps(defaultProps);
    expect(p.style).toBe("bold");
    expect(p.hookText).toBeTruthy();
    expect(p.scenes.some((s) => s.title && s.textAnim)).toBe(true);
  });
});
