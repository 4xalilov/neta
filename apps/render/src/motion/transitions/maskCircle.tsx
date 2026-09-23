import React from "react";
import { AbsoluteFill } from "remotion";
import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { easings } from "../easings";

export type MaskCircleProps = { ringColor?: string; x?: number; y?: number };

/** Circular mask reveal from a point (default centre) with an accent ring on the edge. */
const MaskCircle: React.FC<TransitionPresentationComponentProps<MaskCircleProps>> = ({
  children,
  presentationProgress: p,
  presentationDirection,
  passedProps: { ringColor = "#FACC15", x = 50, y = 50 },
}) => {
  if (presentationDirection === "exiting") return <AbsoluteFill>{children}</AbsoluteFill>;
  const e = easings.expoInOut(p);
  const r = e * 120; // % of the reference radius — 120 covers the corners of 9:16
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ clipPath: `circle(${r}% at ${x}% ${y}%)` }}>{children}</AbsoluteFill>
      {p > 0 && p < 1 ? (
        <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, overflow: "visible" }}>
          <ellipse
            cx={x}
            cy={y}
            rx={(r * Math.hypot(1080, 1920)) / Math.SQRT2 / 1080}
            ry={(r * Math.hypot(1080, 1920)) / Math.SQRT2 / 1920}
            fill="none"
            stroke={ringColor}
            vectorEffect="non-scaling-stroke"
            style={{ strokeWidth: 14 * (1 - e) + 2 }}
            opacity={1 - e * 0.6}
          />
        </svg>
      ) : null}
    </AbsoluteFill>
  );
};

export const maskCircle = (props: MaskCircleProps = {}): TransitionPresentation<MaskCircleProps> => ({ component: MaskCircle, props });
