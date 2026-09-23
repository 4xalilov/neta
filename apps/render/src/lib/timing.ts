export const FPS = 30;
export const WIDTH = 1080;
export const HEIGHT = 1920;
/** Cross-fade between scenes, in frames (docs/08: fade 12 kadr). */
export const TRANSITION_FRAMES = 12;
/** CTA card is shown during the last N seconds. */
export const CTA_SECONDS = 2.5;

/**
 * Frames per scene. Boundaries are rounded on the cumulative timeline, so the
 * sum always equals round(sum(durationS) * fps) and scene starts stay aligned
 * with the audio / word timestamps (which are relative to composition start).
 */
export function sceneFrames(scenes: ReadonlyArray<{ durationS: number }>, fps = FPS): number[] {
  const out: number[] = [];
  let acc = 0;
  for (const s of scenes) {
    const start = Math.round(acc * fps);
    acc += s.durationS;
    out.push(Math.round(acc * fps) - start);
  }
  return out;
}

/** Total composition length in frames (min 1 so Remotion accepts it). */
export function totalFrames(scenes: ReadonlyArray<{ durationS: number }>, fps = FPS): number {
  return Math.max(1, sceneFrames(scenes, fps).reduce((a, b) => a + b, 0));
}

/**
 * Transition length actually used: at most TRANSITION_FRAMES, and never longer
 * than the shortest scene (TransitionSeries requires transition <= sequence).
 */
export function transitionFrames(frames: number[], wanted = TRANSITION_FRAMES): number {
  if (frames.length < 2) return 0;
  return Math.max(0, Math.min(wanted, ...frames.map((f) => f - 1)));
}

/**
 * Sequence lengths for a TransitionSeries. Every scene except the last is
 * extended by the transition length, which exactly cancels the overlap that the
 * transitions remove — total length stays sum(sceneFrames) and scene i starts
 * fading in at its nominal start time.
 */
export function sequenceFrames(frames: number[], transition: number): number[] {
  return frames.map((f, i) => (i < frames.length - 1 ? f + transition : f));
}
