import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { Brand } from "../props";
import { TOKENS } from "../props";

/**
 * Call-to-action card. Mount it inside a <Sequence> covering the last
 * CTA_SECONDS; it slides up with a spring from below the frame.
 */
export const CTA: React.FC<{ text: string; brand: Brand; fontFamily: string }> = ({
  text,
  brand,
  fontFamily,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 14, stiffness: 120, mass: 0.8 } });
  const y = interpolate(p, [0, 1], [420, 0]);
  return (
    <div
      style={{
        position: "absolute",
        left: 72,
        right: 72,
        // Sits above the subtitle band (bottom 22%) and below the image centre.
        bottom: "36%",
        transform: `translateY(${y}px)`,
        opacity: interpolate(p, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
        background: `${brand.surface}E6`,
        border: `2px solid ${TOKENS.border}`,
        borderRadius: 36,
        padding: "40px 48px",
        boxShadow: "0 24px 64px rgba(0,0,0,0.5)",
        textAlign: "center",
        fontFamily,
        fontWeight: 800,
        fontSize: 60,
        lineHeight: 1.15,
        color: brand.color,
      }}
    >
      <div style={{ width: 96, height: 8, borderRadius: 4, background: brand.accent, margin: "0 auto 24px" }} />
      {text}
    </div>
  );
};
