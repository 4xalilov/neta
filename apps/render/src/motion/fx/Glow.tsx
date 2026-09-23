import React from "react";

/** Neon glow around children (two stacked drop-shadows). Works on text and shapes. */
export const Glow: React.FC<{ color: string; radius?: number; strength?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  color,
  radius = 18,
  strength = 1,
  children,
  style,
}) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      filter: `drop-shadow(0 0 ${radius * 0.35}px ${color}) drop-shadow(0 0 ${radius}px ${color}${Math.round(Math.min(1, strength) * 170)
        .toString(16)
        .padStart(2, "0")})`,
      ...style,
    }}
  >
    {children}
  </div>
);
