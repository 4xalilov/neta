import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { noise2D } from "@remotion/noise";

/**
 * Animated gradient-mesh background: 3–4 large soft blobs drifting on noise
 * paths over a base colour. Use behind text-only scenes or letterboxed images.
 */
export const GradientMesh: React.FC<{ base: string; colors: string[]; speed?: number; seed?: string }> = ({
  base,
  colors,
  speed = 1,
  seed = "mesh",
}) => {
  const frame = useCurrentFrame();
  const t = frame * 0.004 * speed;
  const layers = colors.slice(0, 4).map((c, i) => {
    const x = 50 + 42 * noise2D(`${seed}${i}x`, t, i * 10);
    const y = 50 + 42 * noise2D(`${seed}${i}y`, i * 10, t);
    const r = 55 + 12 * noise2D(`${seed}${i}r`, t * 2, i);
    // Soft falloff comes from the gradient itself (a full-frame CSS blur() costs ~2× render time).
    return `radial-gradient(circle at ${x}% ${y}%, ${c} 0%, ${c.length === 9 ? c.slice(0, 7) + "00" : "transparent"} ${r}%)`;
  });
  return (
    <AbsoluteFill style={{ background: base }}>
      <AbsoluteFill style={{ background: layers.join(",") }} />
    </AbsoluteFill>
  );
};
