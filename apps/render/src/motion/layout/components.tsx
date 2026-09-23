import React from "react";
import { Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { easings } from "../easings";
import { mix, presence, revealProgress } from "../timing";

/** Frosted-glass card (backdrop blur + translucent surface + hairline border). */
export const Card: React.FC<{
  surface?: string;
  border?: string;
  radius?: number;
  padding?: number | string;
  glass?: boolean;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({ surface = "#131A2A", border = "rgba(255,255,255,0.14)", radius = 36, padding = "40px 48px", glass = true, style, children }) => (
  <div
    style={{
      background: glass ? `${surface}B3` : surface,
      backdropFilter: glass ? "blur(24px) saturate(1.4)" : undefined,
      border: `2px solid ${border}`,
      borderRadius: radius,
      padding,
      boxShadow: "0 24px 64px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08)",
      ...style,
    }}
  >
    {children}
  </div>
);

/** Pill badge that springs in at `startFrame` (e.g. "−30%", "YANGI", theme name). */
export const Chip: React.FC<{
  text: string;
  color?: string;
  background?: string;
  outline?: boolean;
  fontFamily: string;
  fontSize?: number;
  startFrame?: number;
  style?: React.CSSProperties;
}> = ({ text, color = "#0B0F19", background = "#FACC15", outline = false, fontFamily, fontSize = 34, startFrame = 0, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = presence(frame, { start: startFrame, duration: 12, spring: "bouncy", fps });
  return (
    <div
      style={{
        display: "inline-block",
        padding: "0.32em 0.9em",
        borderRadius: 999,
        fontFamily,
        fontWeight: 800,
        fontSize,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        color: outline ? background : color,
        background: outline ? "transparent" : background,
        border: `3px solid ${background}`,
        transform: `scale(${Math.max(0, p)})`,
        opacity: Math.min(1, Math.max(0, p * 2)),
        ...style,
      }}
    >
      {text}
    </div>
  );
};
/** Alias — some designers call it a badge. */
export const Badge = Chip;

/** Hairline divider that grows from the centre. */
export const Divider: React.FC<{ color?: string; width?: number; thickness?: number; startFrame?: number; style?: React.CSSProperties }> = ({
  color = "#FACC15",
  width = 240,
  thickness = 6,
  startFrame = 0,
  style,
}) => {
  const frame = useCurrentFrame();
  const p = revealProgress(frame, startFrame, 18, easings.expoOut);
  return <div style={{ width, height: thickness, borderRadius: thickness, background: color, transform: `scaleX(${p})`, margin: "0 auto", ...style }} />;
};

/**
 * Lower third: accent bar + name/role card sliding in from the left, exits
 * the same way at `exitFrame`. Place it above the caption band.
 */
export const LowerThird: React.FC<{
  title: string;
  subtitle?: string;
  accent: string;
  color?: string;
  surface?: string;
  fontFamily: string;
  bodyFamily?: string;
  startFrame?: number;
  exitFrame?: number | null;
  style?: React.CSSProperties;
}> = ({ title, subtitle, accent, color = "#E6EAF2", surface = "#131A2A", fontFamily, bodyFamily, startFrame = 0, exitFrame = null, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const bar = presence(frame, { start: startFrame, duration: 12, exitFrame, easing: easings.expoOut, fps });
  const card = presence(frame, { start: startFrame + 4, duration: 16, exitFrame, easing: easings.expoOut, fps });
  return (
    <div style={{ display: "flex", alignItems: "stretch", gap: 0, ...style }}>
      <div style={{ width: 14, background: accent, borderRadius: 7, transform: `scaleY(${bar})`, transformOrigin: "50% 100%" }} />
      <div style={{ overflow: "hidden" }}>
        <div
          style={{
            transform: `translateX(${mix(card, -104, 0)}%)`,
            background: `${surface}E6`,
            padding: "22px 34px",
            borderRadius: "0 22px 22px 0",
          }}
        >
          <div style={{ fontFamily, fontWeight: 800, fontSize: 52, color, lineHeight: 1.1 }}>{title}</div>
          {subtitle ? (
            <div style={{ fontFamily: bodyFamily ?? fontFamily, fontWeight: 500, fontSize: 34, color: accent, marginTop: 6, letterSpacing: "0.02em" }}>{subtitle}</div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

/** Rounded, shadowed image with an accent border; scales in gently at `startFrame`. */
export const ImageFrame: React.FC<{
  src: string;
  accent?: string;
  radius?: number;
  borderWidth?: number;
  startFrame?: number;
  style?: React.CSSProperties;
}> = ({ src, accent = "#FACC15", radius = 40, borderWidth = 6, startFrame = 0, style }) => {
  const frame = useCurrentFrame();
  const p = revealProgress(frame, startFrame, 24, easings.smoothOut);
  const zoom = interpolate(frame - startFrame, [0, 150], [1.08, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div
      style={{
        borderRadius: radius,
        border: `${borderWidth}px solid ${accent}`,
        overflow: "hidden",
        boxShadow: `0 30px 80px rgba(0,0,0,0.55), 0 0 0 ${borderWidth * 2}px ${accent}22`,
        transform: `translateY(${mix(p, 60, 0)}px) scale(${mix(p, 0.92, 1)})`,
        opacity: p,
        ...style,
      }}
    >
      <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${zoom})`, display: "block" }} />
    </div>
  );
};
