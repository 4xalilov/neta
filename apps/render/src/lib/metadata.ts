import type { CalculateMetadataFunction } from "remotion";
import { parseReelsProps, type ReelsProps } from "../props";
import { FPS, totalFrames } from "./timing";

/**
 * durationInFrames = round(sum(scenes[].durationS) * fps). Props are parsed
 * with the zod schema so compositions always receive defaults (brand tokens…).
 */
export const calculateReelsMetadata: CalculateMetadataFunction<ReelsProps> = ({ props }) => {
  const parsed = parseReelsProps(props);
  return {
    durationInFrames: totalFrames(parsed.scenes, FPS),
    fps: FPS,
    props: parsed,
  };
};
