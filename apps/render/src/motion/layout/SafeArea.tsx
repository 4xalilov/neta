import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { safeRect, SAFE } from "./safeArea";

/**
 * Lays children out inside the Instagram UI-safe rectangle (top 14 %,
 * bottom 22 %, sides 5 %). `debug` paints the unsafe zones in red.
 */
export const SafeArea: React.FC<{ debug?: boolean; children?: React.ReactNode; style?: React.CSSProperties }> = ({
  debug = false,
  children,
  style,
}) => {
  const { width, height } = useVideoConfig();
  const r = safeRect(width, height);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {debug ? <SafeAreaOverlay /> : null}
      <div style={{ position: "absolute", left: r.left, top: r.top, width: r.width, height: r.height, ...style }}>{children}</div>
    </AbsoluteFill>
  );
};

/** Red translucent unsafe zones + outline of the safe rect (for Studio review). */
export const SafeAreaOverlay: React.FC = () => {
  const { width, height } = useVideoConfig();
  const r = safeRect(width, height);
  const zone: React.CSSProperties = { position: "absolute", background: "rgba(239,68,68,0.28)" };
  const label: React.CSSProperties = { position: "absolute", color: "#fff", font: "700 26px sans-serif", padding: 8 };
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 1000 }}>
      <div style={{ ...zone, left: 0, top: 0, width, height: r.top }}>
        <span style={{ ...label, bottom: 0 }}>UI top {SAFE.top * 100}%</span>
      </div>
      <div style={{ ...zone, left: 0, top: r.bottom, width, height: height - r.bottom }}>
        <span style={label}>UI bottom {SAFE.bottom * 100}%</span>
      </div>
      <div style={{ ...zone, left: 0, top: r.top, width: r.left, height: r.height }} />
      <div style={{ ...zone, left: r.right, top: r.top, width: width - r.right, height: r.height }} />
      <div style={{ position: "absolute", left: r.left, top: r.top, width: r.width, height: r.height, outline: "3px dashed #EF4444" }} />
    </AbsoluteFill>
  );
};
