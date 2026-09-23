import React from "react";
import type { ReelsProps } from "../props";
import { Reel } from "../components/Reel";

/** Roadmap 1.5 — images + Ken Burns + kinetic word captions + audio + CTA. */
export const ReelsBasic: React.FC<ReelsProps> = (props) => <Reel {...props} parallax={false} />;
