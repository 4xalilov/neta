import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Light anamorphic lens flare that drifts across the upper part of the frame:
 * a hot core, a horizontal streak and 3 ghosts mirrored through the centre.
 */
export const LensFlare: React.FC<{ color?: string; intensity?: number; from?: [number, number]; to?: [number, number] }> = ({
  color = "#FFE7B0",
  intensity = 0.6,
  from = [0.15, 0.18],
  to = [0.85, 0.24],
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();
  const p = interpolate(frame, [0, Math.max(1, durationInFrames)], [0, 1], { extrapolateRight: "clamp" });
  const cx = (from[0] + (to[0] - from[0]) * p) * width;
  const cy = (from[1] + (to[1] - from[1]) * p) * height;
  const mx = width / 2 - (cx - width / 2);
  const my = height / 2 - (cy - height / 2);
  const ghost = (k: number, r: number, a: number) => {
    const x = cx + (mx - cx) * k;
    const y = cy + (my - cy) * k;
    return (
      <div
        key={k}
        style={{
          position: "absolute",
          left: x - r,
          top: y - r,
          width: r * 2,
          height: r * 2,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${color}${Math.round(a * 255).toString(16).padStart(2, "0")} 0%, transparent 70%)`,
        }}
      />
    );
  };
  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "screen", opacity: intensity }}>
      <div
        style={{
          position: "absolute",
          left: cx - 260,
          top: cy - 260,
          width: 520,
          height: 520,
          borderRadius: "50%",
          background: `radial-gradient(circle, #FFFFFF 0%, ${color}AA 12%, transparent 60%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: cx - width * 0.7,
          top: cy - 5,
          width: width * 1.4,
          height: 10,
          background: `linear-gradient(90deg, transparent, ${color}99 45%, #FFFFFF 50%, ${color}99 55%, transparent)`,
          filter: "blur(3px)",
        }}
      />
      {ghost(0.55, 60, 0.25)}
      {ghost(0.8, 30, 0.35)}
      {ghost(1.15, 110, 0.15)}
    </AbsoluteFill>
  );
};
