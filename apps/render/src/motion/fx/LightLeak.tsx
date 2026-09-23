import React, { useState } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { LightLeak as GLLightLeak } from "@remotion/light-leaks";
import { noise2D } from "@remotion/noise";

/** WebGL available in this renderer? (Checked once, in the browser.) */
function hasWebGL(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl") || c.getContext("experimental-webgl"));
  } catch {
    return false;
  }
}

/**
 * Warm film light leak.
 * - `variant="css"` (default): drifting orange / magenta / gold radial blooms
 *   (screen blend) driven by @remotion/noise — works in any renderer.
 * - `variant="gl"`: the official @remotion/light-leaks WebGL shader; falls back
 *   to CSS automatically when the browser has no WebGL (it would otherwise
 *   cancel the render).
 * `intensity` 0–1, `hueShift` 0–360 (gl only), `seed` varies the pattern.
 */
export const LightLeak: React.FC<{ intensity?: number; seed?: number; hueShift?: number; variant?: "css" | "gl" }> = ({
  intensity = 0.5,
  seed = 0,
  hueShift = 0,
  variant = "css",
}) => {
  const [gl] = useState(() => variant === "gl" && hasWebGL());
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  if (gl) {
    return (
      <AbsoluteFill style={{ mixBlendMode: "screen", opacity: intensity, pointerEvents: "none" }}>
        <GLLightLeak seed={seed} hueShift={hueShift} />
      </AbsoluteFill>
    );
  }
  const t = frame / 30;
  const env = interpolate(frame, [0, 12, Math.max(13, durationInFrames - 12), Math.max(14, durationInFrames)], [0, 1, 1, 0.6], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const blob = (i: number, color: string, size: number) => {
    const x = 50 + 55 * noise2D(`leak${seed}-${i}x`, t * 0.12, i);
    const y = 30 + 50 * noise2D(`leak${seed}-${i}y`, i, t * 0.1);
    const a = 0.55 + 0.45 * noise2D(`leak${seed}-${i}a`, t * 0.3, i * 3);
    return `radial-gradient(circle ${size}px at ${x}% ${y}%, ${color}${Math.round(Math.max(0, a) * 200)
      .toString(16)
      .padStart(2, "0")} 0%, transparent 70%)`;
  };
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        mixBlendMode: "screen",
        opacity: intensity * env,
        background: [blob(0, "#FF7A1A", 900), blob(1, "#FF2E88", 700), blob(2, "#FFD36B", 600)].join(","),
        filter: "blur(30px)",
      }}
    />
  );
};
