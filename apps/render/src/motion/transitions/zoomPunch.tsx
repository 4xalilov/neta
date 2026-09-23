import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { easings } from "../easings";

export type ZoomPunchProps = { flashColor?: string; maxScale?: number };

/**
 * Punch-in cut: the outgoing shot rushes towards the camera (scale ↑, blur),
 * a short white flash hides the cut, the new shot lands from zoomed-in
 * (scale 1.35 → 1) with an expo ease-out. Classic "impact" cut.
 */
const ZoomPunch: React.FC<TransitionPresentationComponentProps<ZoomPunchProps>> = ({
  children,
  presentationProgress: p,
  presentationDirection,
  passedProps: { flashColor = "#FFFFFF", maxScale = 1.35 },
}) => {
  if (presentationDirection === "exiting") {
    const q = easings.expoIn(Math.min(1, p / 0.5));
    return (
      <AbsoluteFill style={{ transform: `scale(${1 + (maxScale - 1) * q})`, filter: `blur(${q * 10}px) brightness(${1 + q * 0.6})`, opacity: p < 0.5 ? 1 : 0 }}>
        {children}
      </AbsoluteFill>
    );
  }
  const q = easings.expoOut(Math.max(0, (p - 0.5) / 0.5));
  const flash = interpolate(p, [0.4, 0.5, 0.8], [0, 0.6, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: `scale(${maxScale - (maxScale - 1) * q})`, filter: q < 1 ? `blur(${(1 - q) * 8}px)` : undefined, opacity: p >= 0.5 ? 1 : 0 }}>
        {children}
      </AbsoluteFill>
      <AbsoluteFill style={{ background: flashColor, opacity: flash, pointerEvents: "none" }} />
    </AbsoluteFill>
  );
};

export const zoomPunch = (props: ZoomPunchProps = {}): TransitionPresentation<ZoomPunchProps> => ({ component: ZoomPunch, props });
