import React from "react";
import { AbsoluteFill } from "remotion";
import { GradientMesh } from "../motion/fx/GradientMesh";
import type { Look } from "../motion/styles/look";
import { Background } from "./Background";

/** Backdrop behind the images (visible in transitions / text-only frames). */
export const ThemeBackground: React.FC<{ look: Look }> = ({ look }) => {
  const bg = look.theme.background;
  if (bg.kind === "mesh") return <GradientMesh base={look.colors.bg} colors={bg.colors} />;
  if (bg.kind === "solid")
    return (
      <AbsoluteFill
        style={{ background: `radial-gradient(ellipse at 50% 35%, ${look.colors.surface} 0%, ${bg.colors[0] ?? look.colors.bg} 70%)` }}
      />
    );
  return <Background bg={look.colors.bg} surface={look.colors.surface} />;
};
