import React from "react";
import { AnimatedText, fitFontSize, type TextAnim } from "../motion/text";
import { Glow } from "../motion/fx/Glow";
import type { Rect } from "../motion/layout/safeArea";
import type { Look } from "../motion/styles/look";

/**
 * A headline (hook / scene title / CTA text) inside a region of the safe area.
 * Font size is auto-fitted to the region width + theme maxLines; `glow` wraps it
 * in the neon Glow fx.
 */
export const Headline: React.FC<{
  text: string;
  anim: TextAnim | string | null | undefined;
  fallback: TextAnim;
  look: Look;
  region: Pick<Rect, "left" | "top" | "width" | "height">;
  size: number;
  maxLines?: number;
  startFrame: number;
  durationFrames?: number;
  exitFrame?: number | null;
  glow?: number;
  align?: "left" | "center" | "right";
}> = ({ text, anim, fallback, look, region, size, maxLines, startFrame, durationFrames, exitFrame, glow = 0, align }) => {
  const lines = maxLines ?? look.theme.headline.maxLines;
  const fitted = fitFontSize(text, region.width, lines, size, look.display.charEm * (look.display.uppercase ? 1.08 : 1), 44);
  const style = look.text(fitted, { boxWidth: region.width, boxHeight: region.height, ...(align ? { align } : {}) });
  const node = (
    <AnimatedText
      anim={anim}
      fallback={fallback}
      text={text}
      startFrame={startFrame}
      durationFrames={durationFrames}
      exitFrame={exitFrame}
      style={style}
    />
  );
  return (
    <div style={{ position: "absolute", left: region.left, top: region.top, width: region.width, height: region.height }}>
      {glow > 0 ? (
        <Glow color={look.colors.accent} radius={glow}>
          {node}
        </Glow>
      ) : (
        node
      )}
    </div>
  );
};
