import React from "react";
import { AbsoluteFill } from "remotion";
import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { easings } from "../easings";

export type SliceProps = { slices?: number; direction?: "down" | "up" };

/** The incoming shot drops in as vertical slices, staggered left → right. */
const Slice: React.FC<TransitionPresentationComponentProps<SliceProps>> = ({
  children,
  presentationProgress: p,
  presentationDirection,
  passedProps: { slices = 5, direction = "down" },
}) => {
  if (presentationDirection === "exiting") {
    return <AbsoluteFill style={{ filter: `brightness(${1 - 0.4 * p})` }}>{children}</AbsoluteFill>;
  }
  if (p >= 1) return <AbsoluteFill>{children}</AbsoluteFill>;
  const sign = direction === "down" ? -1 : 1;
  const stagger = 0.35;
  return (
    <AbsoluteFill>
      {Array.from({ length: slices }, (_, i) => {
        const local = Math.min(1, Math.max(0, (p - (i / Math.max(1, slices - 1)) * stagger) / (1 - stagger)));
        const e = easings.expoOut(local);
        const left = (i / slices) * 100;
        return (
          <AbsoluteFill
            key={i}
            style={{
              clipPath: `inset(0 ${100 - left - 100 / slices - 0.05}% 0 ${left}%)`,
              transform: `translateY(${sign * (1 - e) * 100}%)`,
            }}
          >
            {children}
          </AbsoluteFill>
        );
      })}
    </AbsoluteFill>
  );
};

export const slice = (props: SliceProps = {}): TransitionPresentation<SliceProps> => ({ component: Slice, props });
