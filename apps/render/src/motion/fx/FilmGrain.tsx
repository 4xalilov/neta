import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { noise2D } from "@remotion/noise";

const TILE = 240;
const SEEDS = 8;
const tileUri = (seed: number) =>
  `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${TILE}" height="${TILE}">` +
      `<filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="${seed}" stitchTiles="stitch"/>` +
      `<feColorMatrix type="saturate" values="0"/></filter>` +
      `<rect width="${TILE}" height="${TILE}" filter="url(#n)"/></svg>`,
  )}")`;
const TILES = Array.from({ length: SEEDS }, (_, i) => tileUri(i + 1));

/**
 * Animated film grain. A small feTurbulence tile (8 seeds, cycled per frame)
 * is jittered with @remotion/noise so the grain never repeats visibly; opacity
 * flickers slightly like real film. Cheap: no per-pixel JS.
 */
export const FilmGrain: React.FC<{ intensity?: number; seed?: string }> = ({ intensity = 0.08, seed = "grain" }) => {
  const frame = useCurrentFrame();
  const ox = Math.round((noise2D(seed, frame * 0.9, 0) + 1) * TILE);
  const oy = Math.round((noise2D(seed, 0, frame * 0.9) + 1) * TILE);
  const flicker = 1 + 0.25 * noise2D(`${seed}-f`, frame * 0.35, 1);
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        backgroundImage: TILES[frame % SEEDS],
        backgroundPosition: `${ox}px ${oy}px`,
        opacity: Math.max(0, intensity * flicker),
        mixBlendMode: "overlay",
      }}
    />
  );
};
