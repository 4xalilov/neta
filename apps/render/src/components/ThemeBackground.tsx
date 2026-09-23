import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { GradientMesh } from "../motion/fx/GradientMesh";
import type { Look } from "../motion/styles/look";
import { Background } from "./Background";
import { patternLayer } from "./patterns";

const gradient = (angle: number, colors: string[]) =>
  colors.length > 1 ? `linear-gradient(${angle}deg, ${colors.join(", ")})` : colors[0]!;

/** Synthwave horizon: sky gradient, striped sun, scrolling perspective grid. */
const RetroGrid: React.FC<{ colors: string[]; ink: string; opacity: number }> = ({ colors, ink, opacity }) => {
  const frame = useCurrentFrame();
  const [sky0, sky1, sun] = [colors[0]!, colors[1] ?? colors[0]!, colors[2] ?? ink];
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${sky0} 0%, ${sky1} 52%, ${sky0} 100%)`, overflow: "hidden" }}>
      {/* Sun sitting on the horizon (55 %), clipped there; horizontal cut-outs across its lower half. */}
      <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: "55%", overflow: "hidden" }}>
        <div
          style={{
            position: "absolute",
            left: "50%",
            bottom: -240,
            width: 560,
            height: 560,
            marginLeft: -280,
            borderRadius: "50%",
            overflow: "hidden",
            background: `linear-gradient(180deg, #FFD36E 0%, ${sun} 75%)`,
            opacity: 0.6,
          }}
        >
          <div style={{ position: "absolute", left: 0, right: 0, top: "42%", bottom: 0, background: `repeating-linear-gradient(180deg, transparent 0 28px, ${sky1} 28px 40px)` }} />
        </div>
      </div>
      <div style={{ position: "absolute", left: -1200, right: -1200, top: "55%", bottom: -400, perspective: 520, perspectiveOrigin: "50% 0%" }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            transform: "rotateX(62deg)",
            transformOrigin: "50% 0%",
            backgroundImage: `linear-gradient(${ink} 3px, transparent 3px), linear-gradient(90deg, ${ink} 3px, transparent 3px)`,
            backgroundSize: "120px 120px",
            backgroundPosition: `0 ${(frame * 3) % 120}px`,
            opacity,
          }}
        />
      </div>
      <AbsoluteFill style={{ background: `linear-gradient(180deg, transparent 50%, ${sky0}00 54%, ${ink}33 55.2%, transparent 57%)` }} />
    </AbsoluteFill>
  );
};

/** Backdrop behind the images (visible in transitions / text-only frames). */
export const ThemeBackground: React.FC<{ look: Look }> = ({ look }) => {
  const frame = useCurrentFrame();
  const bg = look.theme.background;
  if (bg.kind === "mesh") return <GradientMesh base={look.colors.bg} colors={bg.colors} />;
  if (bg.kind === "solid")
    return (
      <AbsoluteFill
        style={{ background: `radial-gradient(ellipse at 50% 35%, ${look.colors.surface} 0%, ${bg.colors[0] ?? look.colors.bg} 70%)` }}
      />
    );
  if (bg.kind === "gradient") return <AbsoluteFill style={{ background: gradient(bg.angle, bg.colors) }} />;
  if (bg.kind === "pattern") {
    const ink = bg.patternColor ?? look.colors.accent;
    const name = bg.pattern ?? "dots";
    if (name === "retroGrid") return <RetroGrid colors={bg.colors} ink={ink} opacity={bg.patternOpacity} />;
    const layer = patternLayer(name, ink);
    // Slow diagonal drift (0.4 px/frame), wrapped to the tile so it never jumps.
    const [tw, th] = layer?.tile ?? [0, 0];
    const dx = tw ? (frame * 0.4) % tw : 0;
    const dy = th ? (frame * 0.4) % th : 0;
    return (
      <AbsoluteFill style={{ background: gradient(bg.angle, bg.colors) }}>
        {layer ? (
          <AbsoluteFill
            style={{
              backgroundImage: layer.image,
              backgroundSize: layer.size,
              backgroundRepeat: "repeat",
              backgroundPosition: `${dx}px ${dy}px`,
              opacity: bg.patternOpacity,
            }}
          />
        ) : null}
      </AbsoluteFill>
    );
  }
  return <Background bg={look.colors.bg} surface={look.colors.surface} />;
};
