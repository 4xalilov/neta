import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { noise2D } from "@remotion/noise";
import { hash01 } from "../timing";

/** Position of particle `i` at `frame` in % of the frame (deterministic). */
export function particleAt(i: number, frame: number, seed = "p", speed = 1) {
  const baseX = hash01(seed, i) * 100;
  const baseY = hash01(seed, i + 1000) * 100;
  const rise = ((frame * 0.06 * speed * (0.5 + hash01(seed, i + 2000))) % 120) - 10;
  return {
    x: baseX + 4 * noise2D(`${seed}${i}`, frame * 0.01, 0),
    y: ((baseY - rise + 120) % 120) - 10,
    twinkle: 0.5 + 0.5 * noise2D(`${seed}t${i}`, frame * 0.05, 1),
  };
}

/** Floating dust / bokeh dots (gold dust for luxury, cyan sparks for neon). */
export const Particles: React.FC<{ count?: number; color?: string; size?: number; seed?: string; opacity?: number }> = ({
  count = 40,
  color = "#FFFFFF",
  size = 6,
  seed = "p",
  opacity = 0.7,
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "screen", opacity }}>
      {Array.from({ length: count }, (_, i) => {
        const p = particleAt(i, frame, seed);
        const s = size * (0.4 + hash01(seed, i + 3000) * 1.2);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: (p.x / 100) * width,
              top: (p.y / 100) * height,
              width: s,
              height: s,
              borderRadius: "50%",
              background: color,
              opacity: p.twinkle,
              boxShadow: `0 0 ${s * 2}px ${color}`,
              filter: s > size ? `blur(${(s - size) * 0.5}px)` : undefined,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
