import React, { useMemo } from "react";
import { AbsoluteFill, Html5Audio, interpolate, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { TransitionSeries } from "@remotion/transitions";
import type { ReelsProps, Scene } from "../props";
import { CTA_SECONDS, sceneFrames, sceneStarts, sequenceFramesVar, transitionList } from "../lib/timing";
import { getTheme, resolveLook, type Look } from "../motion/styles";
import { pickTransition } from "../motion/transitions";
import { normalizeFx, type FxName } from "../motion/fx/names";
import { ChromaticAberration, FilmGrain, LensFlare, LightLeak, Particles, ProgressBar, Shake, Vignette } from "../motion/fx";
import { Captions, type StaticCaption } from "../motion/captions";
import { regions } from "../motion/layout/safeArea";
import { SafeAreaOverlay } from "../motion/layout/SafeArea";
import { getTextPreset } from "../motion/text";
import { ThemeBackground } from "./ThemeBackground";
import { KenBurnsImage } from "./KenBurnsImage";
import { ParallaxImage } from "./ParallaxImage";
import { Headline } from "./Headline";
import { Logo } from "./Logo";
import { CTA } from "./CTA";

/** Hook headline window (s) and scene-title window (s) — docs/11. */
export const HOOK_SECONDS = 3;
export const TITLE_SECONDS = 2.5;
const MIN_TEXT_FRAMES = 20;

interface TextWindow {
  start: number;
  end: number;
}

/** Top gradient behind headlines, faded in/out around a text window (frames). */
export function scrimOpacity(frame: number, windows: TextWindow[]): number {
  return Math.max(
    0,
    ...windows.map((w) =>
      interpolate(frame, [w.start - 4, w.start + 6, w.end - 6, w.end + 4], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    ),
  );
}

const HeadlineScrim: React.FC<{ windows: TextWindow[]; strength: number }> = ({ windows, strength }) => {
  const frame = useCurrentFrame();
  const o = scrimOpacity(frame, windows) * strength;
  if (o <= 0) return null;
  return (
    <AbsoluteFill
      style={{ opacity: o, background: "linear-gradient(180deg, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.75) 30%, rgba(0,0,0,0) 58%)" }}
    />
  );
};

/**
 * RGB split burst on the cut that settles to 0 within 12 frames (then the plain
 * image renders — the 3-layer split costs ~2× render time, so not every frame).
 */
const ChromaticPulse: React.FC<{ amount: number; children: React.ReactNode }> = ({ amount, children }) => {
  const frame = useCurrentFrame();
  const a = interpolate(frame, [0, 12], [amount, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <ChromaticAberration amount={a}>{children}</ChromaticAberration>;
};

const SceneLayer: React.FC<{
  scene: Scene;
  index: number;
  parallax: boolean;
  look: Look;
  fx: Set<FxName>;
  title: TextWindow | null;
}> = ({ scene, index, parallax, look, fx, title }) => {
  const theme = look.theme;
  const I = theme.fxIntensity;
  let image: React.ReactNode =
    parallax && scene.depthUrl ? (
      <ParallaxImage src={scene.imageUrl} depthSrc={scene.depthUrl} sceneIndex={index} />
    ) : (
      <KenBurnsImage src={scene.imageUrl} sceneIndex={index} mode={scene.kenBurns ?? theme.kenBurns} />
    );
  if (fx.has("chromatic")) image = <ChromaticPulse amount={I.chromatic ?? 10}>{image}</ChromaticPulse>;
  if (fx.has("shake")) {
    const s = I.shake ?? 12;
    image = (
      <Shake intensity={s} decayFrames={18} seed={`impact${index}`}>
        <Shake intensity={s * 0.18} seed={`hand${index}`}>
          {image}
        </Shake>
      </Shake>
    );
  }
  const anim = scene.textAnim ?? theme.defaultTextAnim;
  const { width, height } = useVideoConfig();
  const region = regions(width, height).headline;
  return (
    <AbsoluteFill>
      {image}
      {fx.has("lightLeak") ? (
        <Sequence durationInFrames={45} name="LightLeak">
          <LightLeak intensity={I.lightLeak ?? 0.55} seed={index} />
        </Sequence>
      ) : null}
      {title && scene.title ? <HeadlineScrim windows={[title]} strength={theme.headline.scrim} /> : null}
      {title && scene.title ? (
        <Headline
          text={scene.title}
          anim={anim}
          fallback={theme.defaultTextAnim}
          look={look}
          region={region}
          size={theme.headline.size}
          startFrame={title.start}
          durationFrames={Math.round(getTextPreset(anim, theme.defaultTextAnim).meta.defaultDuration * theme.tempo)}
          exitFrame={title.end - 12}
          glow={fx.has("glow") ? (I.glow ?? 22) : 0}
        />
      ) : null}
    </AbsoluteFill>
  );
};

/**
 * Shared layout of ReelsBasic / ReelsParallax, driven by a StyleTheme
 * (props.style) plus per-scene overrides (textAnim, title, transition, fx,
 * kenBurns, captionPreset). Old props (no style) render with the "bold" theme.
 */
export const Reel: React.FC<ReelsProps & { parallax: boolean; debugSafeArea?: boolean }> = ({
  audioUrl,
  cta,
  scenes,
  brand,
  parallax,
  style,
  hookText,
  captionPreset,
  debugSafeArea = false,
}) => {
  const { fps, durationInFrames, width, height } = useVideoConfig();
  const theme = useMemo(() => getTheme(style), [style]);
  const look = useMemo(() => resolveLook(theme, brand), [theme, brand]);
  const reg = regions(width, height);

  const frames = useMemo(() => sceneFrames(scenes, fps), [scenes, fps]);
  const starts = sceneStarts(frames);
  const picks = scenes.map((s, i) =>
    i === 0
      ? null
      : pickTransition(s.transition ?? theme.defaultTransition, {
          width,
          height,
          accent: look.colors.accent,
          index: i,
          fallback: theme.defaultTransition,
          durationInFrames: !s.transition || s.transition === theme.defaultTransition ? theme.transitionFrames : undefined,
        }),
  );
  const trans = transitionList(
    frames,
    picks.map((p) => (p && p.name !== "none" ? p.durationInFrames : 0)),
  );
  const seqFrames = sequenceFramesVar(frames, trans);

  const ctaFrames = cta ? Math.min(durationInFrames, Math.round(CTA_SECONDS * fps)) : 0;
  const ctaStart = durationInFrames - ctaFrames;

  // Hook: 0–3 s (never overlapping the CTA).
  const hookEnd = Math.min(Math.round(HOOK_SECONDS * fps), frames[0] ?? 0, cta ? ctaStart - 4 : durationInFrames);
  const hook: TextWindow | null = hookText && hookEnd >= MIN_TEXT_FRAMES ? { start: 3, end: hookEnd } : null;
  const hookAnim = scenes[0]?.textAnim ?? theme.defaultTextAnim;

  // Scene titles: first 2.5 s of the scene (local frames), clipped by the scene and the CTA.
  const titles: (TextWindow | null)[] = scenes.map((s, i) => {
    if (!s.title || (i === 0 && hook)) return null;
    const start = i === 0 ? 4 : Math.max(2, Math.round((trans[i] ?? 0) / 2));
    let end = Math.min(Math.round(TITLE_SECONDS * fps), frames[i]!);
    if (cta) end = Math.min(end, ctaStart - 4 - starts[i]!);
    return end - start >= MIN_TEXT_FRAMES ? { start, end } : null;
  });

  const themeFx = theme.fx;
  const sceneFx = scenes.map((s) => new Set<FxName>([...themeFx, ...normalizeFx(s.fx)]));
  const anyFx = (n: FxName) => themeFx.includes(n);
  const I = theme.fxIntensity;

  const captionGroups = useMemo(() => scenes.map((s) => ({ words: s.words, preset: s.captionPreset })), [scenes]);
  const staticCaptions = useMemo<StaticCaption[]>(() => {
    const out: StaticCaption[] = [];
    let t = 0;
    for (const s of scenes) {
      if (s.subtitle && s.words.length === 0) out.push({ text: s.subtitle, start: t, end: t + s.durationS, preset: s.captionPreset });
      t += s.durationS;
    }
    return out;
  }, [scenes]);

  const series: React.ReactNode[] = [];
  scenes.forEach((scene, i) => {
    const pick = picks[i];
    if (i > 0 && pick && trans[i]! > 0) {
      const timed = trans[i] === pick.durationInFrames ? pick : pickTransition(pick.name, { width, height, accent: look.colors.accent, index: i, durationInFrames: trans[i] });
      series.push(<TransitionSeries.Transition key={`t${i}`} presentation={timed.presentation} timing={timed.timing} />);
    }
    series.push(
      <TransitionSeries.Sequence key={`s${i}`} durationInFrames={seqFrames[i]!} name={`Scene ${i + 1}`}>
        <SceneLayer scene={scene} index={i} parallax={parallax} look={look} fx={sceneFx[i]!} title={titles[i]!} />
      </TransitionSeries.Sequence>,
    );
  });

  return (
    <AbsoluteFill style={{ backgroundColor: look.colors.bg }}>
      <ThemeBackground look={look} />
      <TransitionSeries>{series}</TransitionSeries>
      {/* Legibility scrims: caption band (always) and headline area (while a title is on screen). */}
      <AbsoluteFill style={{ background: "linear-gradient(180deg, transparent 55%, rgba(0,0,0,0.55) 100%)" }} />
      {/* Hook scrim here; scene-title scrims live inside each scene, under the title. */}
      {hook ? <HeadlineScrim windows={[hook]} strength={theme.headline.scrim} /> : null}
      {anyFx("vignette") ? <Vignette intensity={I.vignette ?? 0.5} /> : null}
      {anyFx("particles") ? <Particles color={theme.particlesColor ?? look.colors.accent} count={36} seed={theme.name} /> : null}
      {anyFx("lensFlare") ? <LensFlare intensity={0.35} color={look.colors.accent} /> : null}
      {hook ? (
        <Sequence durationInFrames={hook.end + 1} name="Hook">
          <Headline
            text={hookText!}
            anim={hookAnim}
            fallback={theme.defaultTextAnim}
            look={look}
            region={{ ...reg.headline, height: reg.headline.height + 120 }}
            size={theme.headline.hookSize}
            startFrame={hook.start}
            durationFrames={Math.round(getTextPreset(hookAnim, theme.defaultTextAnim).meta.defaultDuration * theme.tempo)}
            exitFrame={hook.end - 12}
            glow={anyFx("glow") ? (I.glow ?? 22) : 0}
          />
        </Sequence>
      ) : null}
      <Logo src={brand.logoUrl} />
      {cta ? (
        <Sequence from={ctaStart} durationInFrames={ctaFrames} name="CTA">
          <CTA text={cta} look={look} />
        </Sequence>
      ) : null}
      <Captions groups={captionGroups} staticCaptions={staticCaptions} preset={captionPreset ?? theme.captionPreset} look={look.caption} />
      {anyFx("grain") ? <FilmGrain intensity={I.grain ?? 0.07} /> : null}
      {anyFx("progressBar") ? <ProgressBar color={look.colors.accent} /> : null}
      {debugSafeArea ? <SafeAreaOverlay /> : null}
      {audioUrl ? <Html5Audio src={audioUrl} /> : null}
    </AbsoluteFill>
  );
};
