import { describe, expect, it } from "vitest";
import { BRAND_DEFAULTS } from "../props";
import { getTheme, resolveLook, styleThemeSchema, THEME_NAMES, THEMES } from "../motion/styles";
import { TEXT_PRESETS } from "../motion/text";
import { CAPTION_META, CAPTION_PRESETS, isCaptionPreset, pageGroups } from "../motion/captions";
import { FX_META, FX_NAMES, normalizeFx } from "../motion/fx/names";
import { pickTransition, TRANSITION_META, TRANSITIONS } from "../motion/transitions";
import { insideSafe, regions, safeRect, SAFE } from "../motion/layout/safeArea";
import { evenWords } from "../lib/captions";

describe("theme registry", () => {
  it("keeps the 7 original themes and each theme validates against the StyleTheme schema", () => {
    expect(THEME_NAMES).toEqual(expect.arrayContaining(["bold", "corporate", "editorial", "hype", "luxury", "minimal", "neon"]));
    for (const name of THEME_NAMES) {
      const t = THEMES[name]!;
      expect(styleThemeSchema.safeParse(t).success, name).toBe(true);
      expect(t.name).toBe(name);
      expect(TEXT_PRESETS[t.defaultTextAnim]).toBeDefined();
      expect(TEXT_PRESETS[t.secondaryTextAnim]).toBeDefined();
      expect(t.defaultTextAnim).not.toBe(t.secondaryTextAnim);
    }
  });

  it("matches the art direction brief", () => {
    expect(THEMES.bold).toMatchObject({ defaultTransition: "zoomPunch", colors: { highlight: "#FACC15" } });
    expect(THEMES.bold!.fonts.display).toMatchObject({ family: "Plus Jakarta Sans", weight: 800 });
    expect(THEMES.bold!.fx).toContain("grain");
    expect(THEMES.minimal).toMatchObject({ defaultTextAnim: "MaskWipe", defaultTransition: "fade" });
    expect(THEMES.minimal!.fonts.display.family).toBe("Manrope");
    expect(THEMES.neon).toMatchObject({ defaultTextAnim: "Glitch" });
    expect(THEMES.neon!.fx).toEqual(expect.arrayContaining(["glow", "chromatic"]));
    expect(THEMES.editorial!.fonts.display.family).toBe("Playfair Display");
    expect(THEMES.corporate).toMatchObject({ defaultTextAnim: "SlideMask", colors: { primary: "#6366F1" } });
    expect(THEMES.hype).toMatchObject({ defaultTextAnim: "Kinetic", defaultTransition: "whipPan" });
    expect(THEMES.hype!.fx).toContain("shake");
    expect(THEMES.luxury).toMatchObject({ defaultTextAnim: "BlurFocus", colors: { accent: "#D4AF37" } });
    expect(THEMES.luxury!.fx).toContain("vignette");
    expect(THEMES.luxury!.tempo).toBeGreaterThan(1);
  });

  it("getTheme is case-insensitive and falls back to bold", () => {
    expect(getTheme("NEON").name).toBe("neon");
    expect(getTheme("nope").name).toBe("bold");
    expect(getTheme(undefined).name).toBe("bold");
  });

  it("the schema rejects broken themes", () => {
    const bad = { ...THEMES.bold!, defaultTextAnim: "Nope" };
    expect(styleThemeSchema.safeParse(bad).success).toBe(false);
    expect(styleThemeSchema.safeParse({ ...THEMES.bold!, colors: { ...THEMES.bold!.colors, accent: "yellow-ish" } }).success).toBe(false);
  });
});

describe("resolveLook (theme × brand)", () => {
  it("uses theme colours/fonts when the brand is untouched", () => {
    const look = resolveLook(THEMES.neon!, { ...BRAND_DEFAULTS });
    expect(look.colors.accent).toBe(THEMES.neon!.colors.accent);
    expect(look.display.family).toBe("Plus Jakarta Sans");
    expect(look.text(100).fontSize).toBe(100);
  });

  it("customised brand fields win", () => {
    const look = resolveLook(THEMES.luxury!, { ...BRAND_DEFAULTS, accent: "#FF5500", font: "Manrope" });
    expect(look.colors.accent).toBe("#FF5500");
    expect(look.colors.highlight).toBe("#FF5500");
    expect(look.display.family).toBe("Manrope");
    expect(look.colors.bg).toBe(THEMES.luxury!.colors.bg);
  });
});

describe("transition registry", () => {
  it("includes the custom presentations and reused built-ins", () => {
    expect(TRANSITIONS).toEqual(expect.arrayContaining(["zoomPunch", "whipPan", "glitchCut", "maskCircle", "slice", "fade", "slide", "wipe", "flip"]));
  });

  it.each([...TRANSITIONS])("pickTransition(%s) returns a usable presentation + timing", (name) => {
    const t = pickTransition(name, { width: 1080, height: 1920 });
    expect(t.name).toBe(name);
    expect(typeof t.presentation.component).toBe("function");
    expect(t.timing.getDurationInFrames({ fps: 30 })).toBe(t.durationInFrames);
    expect(t.durationInFrames).toBe(Math.max(name === "none" ? 1 : 2, TRANSITION_META[name].frames || 1));
    expect(t.timing.getProgress({ frame: 0, fps: 30 })).toBeCloseTo(0);
  });

  it("unknown names fall back, durations can be overridden", () => {
    expect(pickTransition("warp-drive").name).toBe("fade");
    expect(pickTransition("warp-drive", { fallback: "slice" }).name).toBe("slice");
    expect(pickTransition("zoomPunch", { durationInFrames: 6 }).durationInFrames).toBe(6);
  });
});

describe("caption presets", () => {
  it("registry has the 5 presets with sane paging budgets", () => {
    expect([...CAPTION_PRESETS]).toEqual(["karaoke", "boxHighlight", "pillGlass", "bigWord", "lineByLine"]);
    for (const p of CAPTION_PRESETS) {
      expect(CAPTION_META[p].maxChars).toBeGreaterThan(10);
      expect(CAPTION_META[p].maxLines).toBeGreaterThanOrEqual(1);
      expect(CAPTION_META[p].description.length).toBeGreaterThan(10);
    }
    expect(isCaptionPreset("karaoke")).toBe(true);
    expect(isCaptionPreset("fancy")).toBe(false);
  });

  it("pages each scene with its own preset and never spans scenes", () => {
    const s1 = evenWords("Bugun biz sizga oʻzbekcha Reels qanday tayyorlanishini koʻrsatamiz", 0, 4);
    const s2 = evenWords("Obuna boʻling va doʻstlaringizga ulashing", 4.2, 7);
    const pages = pageGroups([{ words: s1, preset: "lineByLine" }, { words: s2 }], "karaoke");
    const first = pages.filter((p) => p.start < 4.1);
    const second = pages.filter((p) => p.start >= 4.1);
    expect(first.every((p) => p.preset === "lineByLine" && p.lines.length === 1)).toBe(true);
    expect(second.every((p) => p.preset === "karaoke")).toBe(true);
    for (let i = 1; i < pages.length; i++) expect(pages[i - 1]!.end).toBeLessThanOrEqual(pages[i]!.start + 1e-9);
    // unknown preset → fallback
    expect(pageGroups([{ words: s2, preset: "nope" }], "pillGlass")[0]!.preset).toBe("pillGlass");
  });
});

describe("fx registry", () => {
  it("lists the fx with metadata and normalises LLM input", () => {
    for (const n of FX_NAMES) expect(FX_META[n].description.length).toBeGreaterThan(5);
    expect(normalizeFx(["shake", "SHAKE", "shake", "lightLeak", "sparkles"])).toEqual(["shake", "lightLeak"]);
    expect(normalizeFx(null)).toEqual([]);
  });
});

describe("safe area", () => {
  it("is top 14 %, bottom 22 %, sides 5 % of 1080×1920", () => {
    expect(SAFE).toEqual({ top: 0.14, bottom: 0.22, side: 0.05 });
    expect(safeRect(1080, 1920)).toEqual({ left: 54, top: 269, right: 1026, bottom: 1498, width: 972, height: 1229 });
  });

  it("headline / CTA / caption regions sit inside the safe area and don't collide", () => {
    const r = regions(1080, 1920);
    for (const k of ["headline", "cta", "captions"] as const) expect(insideSafe(r[k]), k).toBe(true);
    expect(r.cta.bottom).toBeLessThanOrEqual(r.captions.top);
    expect(r.headline.top).toBeLessThan(r.cta.top);
    expect(insideSafe({ left: 0, top: 0, width: 100, height: 100 })).toBe(false);
  });
});
