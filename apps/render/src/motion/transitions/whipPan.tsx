import React, { useId } from "react";
import { AbsoluteFill } from "remotion";
import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { easings } from "../easings";

export type WhipPanProps = { direction?: "left" | "right"; blur?: number };

/**
 * Whip pan: both shots slide horizontally with an expo in-out curve and a
 * directional (horizontal-only) motion blur that peaks mid-move — an SVG
 * feGaussianBlur with stdDeviation "x 0", which CSS blur() cannot do.
 */
const WhipPan: React.FC<TransitionPresentationComponentProps<WhipPanProps>> = ({
  children,
  presentationProgress: p,
  presentationDirection,
  passedProps: { direction = "left", blur = 60 },
}) => {
  const id = useId().replace(/:/g, "");
  const e = easings.expoInOut(p);
  const sign = direction === "left" ? -1 : 1;
  const x = presentationDirection === "exiting" ? sign * e * 100 : -sign * (1 - e) * 100;
  const b = Math.sin(Math.PI * p) * blur;
  return (
    <AbsoluteFill style={{ transform: `translateX(${x}%)` }}>
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <filter id={`whip-${id}`} x="-20%" y="0" width="140%" height="100%">
          <feGaussianBlur stdDeviation={`${b.toFixed(2)} 0`} />
        </filter>
      </svg>
      <AbsoluteFill style={{ filter: b > 0.5 ? `url(#whip-${id})` : undefined }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export const whipPan = (props: WhipPanProps = {}): TransitionPresentation<WhipPanProps> => ({ component: WhipPan, props });
