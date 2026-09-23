import React, { useMemo } from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { activeWordIndex, pageAt, pageScenes, type Word } from "../lib/captions";

export interface StaticCaption {
  text: string;
  start: number;
  end: number;
}

export interface SubtitlesProps {
  /**
   * Word timings in seconds relative to composition start, one array per scene
   * (pages never span a scene cut).
   */
  wordGroups: Word[][];
  /** Scene-level `subtitle` fallbacks shown when no word page is active. */
  staticCaptions?: StaticCaption[];
  color: string;
  accent: string;
  fontFamily: string;
  maxChars?: number;
  maxLines?: number;
}

const STROKE = 6; // docs/08: qora kontur 6px
const FONT_SIZE = 78;

const textStyle = (fontFamily: string): React.CSSProperties => ({
  fontFamily,
  fontWeight: 800,
  fontSize: FONT_SIZE,
  lineHeight: 1.18,
  WebkitTextStroke: `${STROKE}px #000`,
  paintOrder: "stroke fill",
  textShadow: "0 6px 18px rgba(0,0,0,0.55), 0 0 2px #000",
  letterSpacing: "-0.01em",
});

/**
 * Kinetic word-level captions (TikTok style): pages of ≤ 2 lines / ≤ 42 chars,
 * all words of the page visible, active word in `accent` (others `color`) with
 * a spring() pop when it starts; the page itself springs in.
 * Anchored 22% from the bottom (clear of Instagram UI).
 */
export const Subtitles: React.FC<SubtitlesProps> = ({
  wordGroups,
  staticCaptions = [],
  color,
  accent,
  fontFamily,
  maxChars = 42,
  maxLines = 2,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const pages = useMemo(() => pageScenes(wordGroups, maxChars, maxLines), [wordGroups, maxChars, maxLines]);
  const page = pageAt(pages, t);

  let content: React.ReactNode = null;
  let pageScale = 1;
  if (page) {
    const active = activeWordIndex(page, t);
    // Whole page pops in when it appears …
    const pageIn = spring({ frame: frame - Math.round(page.start * fps), fps, config: { damping: 14, stiffness: 200 } });
    pageScale = 0.9 + 0.1 * pageIn;
    let k = 0;
    content = page.lines.map((line, li) => (
      <div key={li}>
        {line.map((word, wi) => {
          const idx = k++;
          const isActive = idx === active;
          // … and each word pops (spring overshoot) when it becomes the spoken one.
          const pop = spring({
            frame: frame - Math.round(word.start * fps),
            fps,
            config: { damping: 9, stiffness: 260, mass: 0.6 },
          });
          return (
            <span
              key={wi}
              style={{
                display: "inline-block",
                margin: "0 0.14em",
                color: isActive ? accent : color,
                transform: `scale(${isActive ? 0.85 + 0.21 * pop : 1})`,
                transformOrigin: "50% 70%",
              }}
            >
              {word.w}
            </span>
          );
        })}
      </div>
    ));
  } else {
    const s = staticCaptions.find((c) => t >= c.start && t < c.end);
    if (s) content = <div style={{ color }}>{s.text}</div>;
  }

  if (!content) return null;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: 60,
          right: 60,
          bottom: "22%",
          textAlign: "center",
          transform: `scale(${pageScale})`,
          transformOrigin: "50% 100%",
          ...textStyle(fontFamily),
        }}
      >
        {content}
      </div>
    </AbsoluteFill>
  );
};
