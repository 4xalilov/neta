import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { fitFontSize, splitLines, plainText } from "../motion/text";
import { Card, Divider } from "../motion/layout";
import { regions } from "../motion/layout/safeArea";
import type { Look } from "../motion/styles/look";
import { Headline } from "./Headline";

/**
 * Call-to-action card in the theme look. Mount it inside a <Sequence> covering
 * the last CTA_SECONDS: the card springs up from below, the text animates with
 * theme.ctaTextAnim. Sits above the caption band, inside the safe area.
 */
export const CTA: React.FC<{ text: string; look: Look }> = ({ text, look }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const p = spring({ frame, fps, config: { damping: 14, stiffness: 120, mass: 0.8 } });
  const y = interpolate(p, [0, 1], [420, 0]);
  const region = regions(width, height).cta;
  const padX = 48;
  const innerW = region.width - padX * 2;
  const charEm = look.display.charEm * (look.display.uppercase ? 1.08 : 1);
  const size = fitFontSize(text, innerW, 3, 64, charEm, 40);
  const lines = splitLines(plainText(text), Math.max(4, Math.floor(innerW / (size * charEm)))).length;
  const textH = Math.ceil(lines * size * 1.15) + 16;
  const cardH = textH + 40 + 44 + 24;
  const top = region.bottom - cardH;
  return (
    <div style={{ position: "absolute", left: region.left, top, width: region.width, height: cardH, transform: `translateY(${y}px)`, opacity: interpolate(p, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }) }}>
      <Card
        surface={look.colors.surface}
        glass={look.theme.card.glass}
        radius={look.theme.card.radius}
        padding={0}
        style={{ position: "absolute", inset: 0 }}
      />
      <Divider color={look.colors.accent} width={96} thickness={8} startFrame={4} style={{ position: "absolute", top: 40, left: 0, right: 0 }} />
      <Headline
        text={text}
        anim={look.theme.ctaTextAnim}
        fallback="BounceIn"
        look={look}
        region={{ left: padX, top: 40 + 8 + 24, width: innerW, height: textH }}
        size={size}
        maxLines={3}
        startFrame={6}
        durationFrames={Math.round(24 * look.theme.tempo)}
        align="center"
      />
    </div>
  );
};
