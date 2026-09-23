import React, { useMemo, useState } from "react";
import { AbsoluteFill, Html5Audio, Sequence, useVideoConfig } from "remotion";
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import type { ReelsProps } from "../props";
import { CTA_SECONDS, sceneFrames, sequenceFrames, transitionFrames } from "../lib/timing";
import { ensureFont } from "../lib/fonts";
import { Background } from "./Background";
import { KenBurnsImage } from "./KenBurnsImage";
import { ParallaxImage } from "./ParallaxImage";
import { Subtitles, type StaticCaption } from "./Subtitles";
import { Logo } from "./Logo";
import { CTA } from "./CTA";

/** Shared layout of ReelsBasic / ReelsParallax. */
export const Reel: React.FC<ReelsProps & { parallax: boolean }> = ({
  audioUrl,
  cta,
  scenes,
  brand,
  parallax,
}) => {
  const { fps, durationInFrames } = useVideoConfig();
  const [fontFamily] = useState(() => ensureFont(brand.font));

  const frames = useMemo(() => sceneFrames(scenes, fps), [scenes, fps]);
  const transition = transitionFrames(frames);
  const seqFrames = sequenceFrames(frames, transition);

  const wordGroups = useMemo(() => scenes.map((s) => s.words), [scenes]);
  const staticCaptions = useMemo<StaticCaption[]>(() => {
    const out: StaticCaption[] = [];
    let t = 0;
    for (const s of scenes) {
      if (s.subtitle && s.words.length === 0) out.push({ text: s.subtitle, start: t, end: t + s.durationS });
      t += s.durationS;
    }
    return out;
  }, [scenes]);

  const series: React.ReactNode[] = [];
  scenes.forEach((scene, i) => {
    if (i > 0 && transition > 0) {
      series.push(
        <TransitionSeries.Transition
          key={`t${i}`}
          presentation={fade()}
          timing={linearTiming({ durationInFrames: transition })}
        />,
      );
    }
    series.push(
      <TransitionSeries.Sequence key={`s${i}`} durationInFrames={seqFrames[i]!}>
        {parallax && scene.depthUrl ? (
          <ParallaxImage src={scene.imageUrl} depthSrc={scene.depthUrl} sceneIndex={i} />
        ) : (
          <KenBurnsImage src={scene.imageUrl} sceneIndex={i} />
        )}
      </TransitionSeries.Sequence>,
    );
  });

  const ctaFrames = Math.min(durationInFrames, Math.round(CTA_SECONDS * fps));

  return (
    <AbsoluteFill style={{ backgroundColor: brand.bg }}>
      <Background bg={brand.bg} surface={brand.surface} />
      <TransitionSeries>{series}</TransitionSeries>
      {/* Legibility scrim behind the caption band. */}
      <AbsoluteFill
        style={{
          background: "linear-gradient(180deg, transparent 55%, rgba(0,0,0,0.55) 100%)",
        }}
      />
      <Logo src={brand.logoUrl} />
      {cta ? (
        <Sequence from={durationInFrames - ctaFrames} durationInFrames={ctaFrames} name="CTA">
          <CTA text={cta} brand={brand} fontFamily={fontFamily} />
        </Sequence>
      ) : null}
      <Subtitles
        wordGroups={wordGroups}
        staticCaptions={staticCaptions}
        color={brand.color}
        accent={brand.accent}
        fontFamily={fontFamily}
      />
      {audioUrl ? <Html5Audio src={audioUrl} /> : null}
    </AbsoluteFill>
  );
};
