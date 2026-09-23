import React from "react";
import type { Word } from "../lib/captions";
import { Captions, type StaticCaption } from "../motion/captions";

export type { StaticCaption };

export interface SubtitlesProps {
  /** Word timings (seconds from composition start), one array per scene. */
  wordGroups: Word[][];
  staticCaptions?: StaticCaption[];
  color: string;
  accent: string;
  fontFamily: string;
}

/**
 * Backwards-compatible wrapper: the original TikTok-style karaoke captions
 * (docs/08). New code uses motion/captions <Captions> with a preset.
 */
export const Subtitles: React.FC<SubtitlesProps> = ({ wordGroups, staticCaptions, color, accent, fontFamily }) => (
  <Captions
    groups={wordGroups.map((words) => ({ words }))}
    staticCaptions={staticCaptions}
    preset="karaoke"
    look={{ fontFamily, color, accent, stroke: 6 }}
  />
);
