import React from "react";
import { AbsoluteFill } from "remotion";

/** Darkened corners (radial). `intensity` 0–1 = corner alpha. */
export const Vignette: React.FC<{ intensity?: number; color?: string }> = ({ intensity = 0.55, color = "0,0,0" }) => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      background: `radial-gradient(ellipse 75% 60% at 50% 46%, rgba(${color},0) 55%, rgba(${color},${intensity * 0.6}) 82%, rgba(${color},${intensity}) 100%)`,
    }}
  />
);
