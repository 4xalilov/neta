import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

/** Thin Reels progress bar along the top edge (fills over the whole composition). */
export const ProgressBar: React.FC<{ color: string; track?: string; height?: number; top?: number }> = ({
  color,
  track = "rgba(255,255,255,0.18)",
  height = 8,
  top = 0,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const p = Math.min(1, (frame + 1) / Math.max(1, durationInFrames));
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", top, left: 0, right: 0, height, background: track }}>
        <div style={{ height: "100%", width: `${p * 100}%`, background: color, boxShadow: `0 0 12px ${color}` }} />
      </div>
    </AbsoluteFill>
  );
};
