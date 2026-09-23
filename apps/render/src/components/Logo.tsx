import React from "react";
import { Img } from "remotion";

/** Optional brand logo, small, top-left (inside Instagram's safe area). */
export const Logo: React.FC<{ src?: string | null }> = ({ src }) => {
  if (!src) return null;
  return (
    <Img
      src={src}
      style={{
        position: "absolute",
        top: 96,
        left: 64,
        height: 88,
        maxWidth: 280,
        objectFit: "contain",
        filter: "drop-shadow(0 4px 12px rgba(0,0,0,0.45))",
      }}
    />
  );
};
