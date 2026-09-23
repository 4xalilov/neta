import React from "react";
import type { ReelsProps } from "../props";
import { Reel } from "../components/Reel";

/**
 * Roadmap 2.4 (stub) — like ReelsBasic, but scenes with `depthUrl` use the
 * depth-masked two-layer parallax (components/ParallaxImage). Scenes without a
 * depth map fall back to the ReelsBasic Ken Burns image.
 */
export const ReelsParallax: React.FC<ReelsProps> = (props) => <Reel {...props} parallax />;
