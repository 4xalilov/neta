import React from "react";
import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig } from "remotion";
import { kenBurnsCss, kenBurnsMode, type KenBurnsMode } from "../lib/kenBurns";

export const KenBurnsImage: React.FC<{ src: string; sceneIndex: number; mode?: KenBurnsMode }> = ({ src, sceneIndex, mode = "in" }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig(); // = this Sequence's length
  const t = kenBurnsMode(frame, durationInFrames, mode, sceneIndex);
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: kenBurnsCss(t),
          transformOrigin: "50% 50%",
        }}
      />
    </AbsoluteFill>
  );
};
