import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { TOKENS } from "../props";

const NOISE = `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">` +
    `<filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/>` +
    `<feColorMatrix type="saturate" values="0"/></filter>` +
    `<rect width="256" height="256" filter="url(#n)"/></svg>`,
)}")`;

/**
 * Dark brand backdrop (docs/08: qora/ko'k gradient): bg → surface vertical
 * gradient, a slowly drifting primary/cyan glow and a faint animated grain.
 * Visible behind images during fades and around letterboxed content.
 */
export const Background: React.FC<{ bg: string; surface: string }> = ({ bg, surface }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const drift = interpolate(frame, [0, Math.max(1, durationInFrames)], [0, 1]);
  const gx = 30 + 40 * Math.sin(drift * Math.PI * 2);
  const gy = 25 + 20 * Math.cos(drift * Math.PI * 2);
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${bg} 0%, ${surface} 100%)` }}>
      <AbsoluteFill
        style={{
          background:
            `radial-gradient(circle at ${gx}% ${gy}%, ${TOKENS.primary}33 0%, transparent 45%),` +
            `radial-gradient(circle at ${100 - gx}% ${100 - gy}%, ${TOKENS.cyan}22 0%, transparent 40%)`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: NOISE,
          backgroundPosition: `${(frame * 37) % 256}px ${(frame * 53) % 256}px`,
          opacity: 0.05,
          mixBlendMode: "overlay",
        }}
      />
    </AbsoluteFill>
  );
};
