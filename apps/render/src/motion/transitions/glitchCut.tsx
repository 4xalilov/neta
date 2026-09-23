import React from "react";
import { AbsoluteFill } from "remotion";
import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { hash01 } from "../timing";

export type GlitchCutProps = { bands?: number; seed?: number };

/**
 * Digital glitch cut: around the cut point the image is split into horizontal
 * bands that jump sideways, with an RGB-tinted offset copy; the outgoing shot
 * is replaced by the incoming one at 50 %. Keep it short (6–10 frames).
 */
const GlitchCut: React.FC<TransitionPresentationComponentProps<GlitchCutProps>> = ({
  children,
  presentationProgress: p,
  presentationDirection,
  passedProps: { bands = 6, seed = 3 },
}) => {
  const exiting = presentationDirection === "exiting";
  const visible = exiting ? p < 0.5 : p >= 0.5;
  const k = Math.sin(Math.PI * p); // glitch strength, peaks at the cut
  const tick = Math.floor(p * 12);
  if (!visible) return <AbsoluteFill style={{ opacity: 0 }}>{children}</AbsoluteFill>;
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {Array.from({ length: bands }, (_, i) => {
        const top = (i / bands) * 100;
        const off = (hash01(seed + tick, i) - 0.5) * 180 * k;
        return (
          <AbsoluteFill
            key={i}
            style={{
              clipPath: `inset(${top}% 0 ${100 - top - 100 / bands}% 0)`,
              transform: `translateX(${off}px)`,
              filter: k > 0.4 && i % 2 === tick % 2 ? `hue-rotate(${90 * k}deg) saturate(${1 + k})` : undefined,
            }}
          >
            {children}
          </AbsoluteFill>
        );
      })}
      <AbsoluteFill style={{ background: "#00E5FF", mixBlendMode: "color", opacity: 0.25 * k }} />
    </AbsoluteFill>
  );
};

export const glitchCut = (props: GlitchCutProps = {}): TransitionPresentation<GlitchCutProps> => ({ component: GlitchCut, props });
