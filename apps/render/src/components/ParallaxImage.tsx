import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Simple 2.5D parallax from one image + its depth map (roadmap 2.4).
 *
 * Two copies of the image are stacked:
 *   - back layer: the full image, gentle zoom, drifts slightly AGAINST the pan;
 *   - front layer: the same image masked by the depth map (CSS `mask-mode:
 *     luminance`, white = near), zooms more and drifts WITH the pan.
 * Near pixels therefore move faster than far pixels, which reads as camera
 * motion. There is no inpainting: at strong depth edges a faint double contour
 * can appear, so the offsets are kept small. The mask moves with the front
 * layer because it is applied to the same element.
 */
export const ParallaxImage: React.FC<{ src: string; depthSrc: string; sceneIndex: number }> = ({
  src,
  depthSrc,
  sceneIndex,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  const p = interpolate(frame, [0, Math.max(1, durationInFrames)], [-1, 1], clamp);
  const dir = sceneIndex % 2 === 0 ? 1 : -1;

  const backScale = interpolate(p, [-1, 1], [1.08, 1.12]);
  const frontScale = interpolate(p, [-1, 1], [1.1, 1.18]);
  // % of element size; back margin ≈ 3.5–5 %, front offsets stay within ~2.4 %.
  const backX = -dir * p * 1.2;
  const frontX = dir * p * 2.4;
  const frontY = -p * 1.0;

  const fill: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    objectFit: "cover",
    transformOrigin: "50% 50%",
  };

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img src={src} style={{ ...fill, transform: `scale(${backScale}) translate(${backX}%, 0%)` }} />
      <div
        style={{
          ...fill,
          transform: `scale(${frontScale}) translate(${frontX}%, ${frontY}%)`,
          maskImage: `url("${depthSrc}")`,
          maskMode: "luminance",
          maskSize: "cover",
          maskPosition: "center",
          maskRepeat: "no-repeat",
        }}
      >
        <Img src={src} style={{ ...fill, transform: "none" }} />
      </div>
      {/* Preload the depth map so delayRender() waits for it before the first frame. */}
      <Img src={depthSrc} style={{ position: "absolute", width: 1, height: 1, opacity: 0 }} />
    </AbsoluteFill>
  );
};
