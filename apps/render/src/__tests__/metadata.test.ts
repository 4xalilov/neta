import { describe, expect, it } from "vitest";
import { calculateReelsMetadata } from "../lib/metadata";
import { sceneFrames, sequenceFrames, totalFrames, transitionFrames, TRANSITION_FRAMES } from "../lib/timing";
import { defaultProps, type ReelsProps } from "../props";

const meta = async (props: unknown) =>
  calculateReelsMetadata({
    props: props as ReelsProps,
    defaultProps,
    abortSignal: new AbortController().signal,
    compositionId: "ReelsBasic",
    isRendering: true,
  } as Parameters<typeof calculateReelsMetadata>[0]);

describe("calculateMetadata", () => {
  it("durationInFrames = sum(durationS) * 30", async () => {
    const m = await meta({
      scenes: [
        { imageUrl: "a.png", durationS: 4, words: [] },
        { imageUrl: "b.png", durationS: 5.5, words: [] },
        { imageUrl: "c.png", durationS: 3.25, words: [] },
      ],
    });
    expect(m.durationInFrames).toBe(Math.round(12.75 * 30));
    expect(m.fps).toBe(30);
  });

  it("returns parsed props with brand defaults applied", async () => {
    const m = await meta({ scenes: [{ imageUrl: "a.png", durationS: 2 }] });
    expect(m.props?.brand.accent).toBe("#FACC15");
    expect(m.props?.scenes[0]!.words).toEqual([]);
  });

  it("matches the demo props (13 s → 390 frames)", async () => {
    expect((await meta(defaultProps)).durationInFrames).toBe(390);
  });

  it("rejects props without scenes", async () => {
    await expect(meta({ scenes: [] })).rejects.toThrow();
  });
});

describe("timing helpers", () => {
  it("rounds on the cumulative timeline so the total never drifts", () => {
    const scenes = [{ durationS: 1.01 }, { durationS: 1.01 }, { durationS: 1.01 }];
    const f = sceneFrames(scenes, 30);
    expect(f.reduce((a, b) => a + b, 0)).toBe(Math.round(3.03 * 30));
    expect(totalFrames(scenes)).toBe(91);
  });

  it("sequence lengths compensate the transition overlap", () => {
    const frames = [120, 150, 90];
    const T = transitionFrames(frames);
    expect(T).toBe(TRANSITION_FRAMES);
    const seq = sequenceFrames(frames, T);
    // TransitionSeries total = sum(seq) - T * (#transitions)
    expect(seq.reduce((a, b) => a + b, 0) - T * (frames.length - 1)).toBe(360);
  });

  it("shrinks the transition for very short scenes and drops it for one scene", () => {
    expect(transitionFrames([5, 100])).toBe(4);
    expect(transitionFrames([100])).toBe(0);
  });

  it("never returns 0 frames", () => {
    expect(totalFrames([])).toBe(1);
  });
});

describe("variable transitions (StyleTheme / scene.transition)", () => {
  it("clamps each cut to its neighbours and keeps scene starts on the audio timeline", async () => {
    const { transitionList, sequenceFramesVar, sceneStarts } = await import("../lib/timing");
    const frames = [120, 6, 150, 90];
    const trans = transitionList(frames, [99, 10, 20, 0]);
    expect(trans).toEqual([0, 5, 5, 0]);
    const seq = sequenceFramesVar(frames, trans);
    // TransitionSeries start of scene i = sum(seq[<i]) - sum(trans[1..i])
    let acc = 0;
    let overlap = 0;
    const starts = sceneStarts(frames);
    seq.forEach((len, i) => {
      overlap += trans[i]!;
      expect(acc - overlap).toBe(starts[i]);
      acc += len;
    });
    expect(acc - trans.reduce((a, b) => a + b, 0)).toBe(frames.reduce((a, b) => a + b, 0));
  });
});
