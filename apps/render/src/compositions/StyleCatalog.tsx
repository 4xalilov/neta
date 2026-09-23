import React, { useMemo } from "react";
import { z } from "zod";
import { AbsoluteFill, Series, useVideoConfig, type CalculateMetadataFunction } from "remotion";
import { evenWords } from "../lib/captions";
import { BRAND_DEFAULTS, placeholderImage } from "../props";
import { getTheme, resolveLook, THEME_NAMES, type Look } from "../motion/styles";
import { Captions } from "../motion/captions";
import { FilmGrain, LensFlare, Particles, ProgressBar, Vignette, ChromaticAberration } from "../motion/fx";
import { Chip, regions, SafeAreaOverlay } from "../motion/layout";
import { getTextPreset, type TextAnim } from "../motion/text";
import { ThemeBackground } from "../components/ThemeBackground";
import { KenBurnsImage } from "../components/KenBurnsImage";
import { Headline } from "../components/Headline";

/** Frames per theme segment and the frame `render:catalog` grabs as a still. */
export const CATALOG_SEGMENT = 130;
export const CATALOG_STILL_FRAME = 100;

export const styleCatalogSchema = z.object({
  /** Themes to show (in order); default = all. */
  themes: z.array(z.string()).default([...THEME_NAMES]),
  /** Paint the Instagram unsafe zones (review aid). */
  showSafeArea: z.boolean().default(false),
});
export type StyleCatalogProps = z.output<typeof styleCatalogSchema>;

export const catalogDefaultProps: StyleCatalogProps = { themes: [...THEME_NAMES], showSafeArea: false };

export const calculateCatalogMetadata: CalculateMetadataFunction<StyleCatalogProps> = ({ props }) => {
  const p = styleCatalogSchema.parse(props);
  return { durationInFrames: Math.max(1, p.themes.length) * CATALOG_SEGMENT, props: p };
};

/** Demo copy per text preset, so every preset shows what it is good at. */
const DEMO_TEXT: Record<TextAnim, string> = {
  WordPop: "Reels *5 daqiqada* tayyor",
  CharCascade: "Oʻzbekcha sifat",
  MaskWipe: "Yangi kolleksiya",
  TypeWriter: "Bugun boshlang",
  SlideMask: "Biznesingiz uchun aqlli yechim",
  Glitch: "Tizim *yangilandi*",
  Counter: "1 500 000 soʻm",
  Highlighter: "Narx *30%* arzon",
  Split3D: "Uch qadamda natija",
  Scramble: "Sirli *taklif*",
  Kinetic: "Bugun *faqat* bugun chegirma",
  Outline2Fill: "Hoziroq yozing",
  BounceIn: "Obuna boʻling!",
  BlurFocus: "Nafislik *har* detalda",
};

const Segment: React.FC<{ look: Look; showSafeArea: boolean }> = ({ look, showSafeArea }) => {
  const { width, height } = useVideoConfig();
  const theme = look.theme;
  const reg = regions(width, height);
  const I = theme.fxIntensity;
  const words = useMemo(() => evenWords("Har bir soʻz oʻz vaqtida yonadi", 0.3, 4.3), []);
  const img = useMemo(() => placeholderImage(theme.colors.primary, theme.colors.bg, ""), [theme]);
  const primary = theme.defaultTextAnim;
  const secondary = theme.secondaryTextAnim;
  const dur = (a: TextAnim) => Math.round(getTextPreset(a).meta.defaultDuration * theme.tempo);
  let scene: React.ReactNode = <KenBurnsImage src={img} sceneIndex={0} mode={theme.kenBurns} />;
  if (theme.fx.includes("chromatic")) scene = <ChromaticAberration amount={2}>{scene}</ChromaticAberration>;
  const glow = theme.fx.includes("glow") ? (I.glow ?? 22) : 0;
  const secondTop = reg.headline.bottom + 40;
  return (
    <AbsoluteFill style={{ background: look.colors.bg }}>
      <ThemeBackground look={look} />
      <AbsoluteFill style={{ opacity: 0.55 }}>{scene}</AbsoluteFill>
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.2) 45%, rgba(0,0,0,0.6) 100%)" }} />
      {theme.fx.includes("vignette") ? <Vignette intensity={I.vignette ?? 0.5} /> : null}
      {theme.fx.includes("particles") ? <Particles color={theme.particlesColor ?? look.colors.accent} count={36} seed={theme.name} /> : null}
      {theme.fx.includes("lensFlare") ? <LensFlare intensity={0.35} color={look.colors.accent} /> : null}
      <div style={{ position: "absolute", left: reg.safe.left, top: reg.safe.top - 10, display: "flex", gap: 16, alignItems: "center" }}>
        <Chip text={theme.label} fontFamily={look.body.stack} background={look.colors.accent} color={look.colors.onHighlight} fontSize={30} startFrame={0} />
        <span style={{ fontFamily: look.body.stack, fontWeight: 600, fontSize: 26, color: look.colors.text, opacity: 0.8 }}>
          {primary} · {secondary} · {theme.captionPreset} · {theme.defaultTransition}
        </span>
      </div>
      <Headline
        text={DEMO_TEXT[primary]}
        anim={primary}
        fallback={primary}
        look={look}
        region={{ ...reg.headline, top: reg.headline.top + 60, height: reg.headline.height - 60 }}
        size={theme.headline.hookSize}
        startFrame={3}
        durationFrames={dur(primary)}
        exitFrame={CATALOG_SEGMENT - 16}
        glow={glow}
      />
      <Headline
        text={DEMO_TEXT[secondary]}
        anim={secondary}
        fallback={secondary}
        look={look}
        region={{ left: reg.safe.left, top: secondTop, width: reg.safe.width, height: 260 }}
        size={Math.round(theme.headline.size * 0.8)}
        maxLines={2}
        startFrame={24}
        durationFrames={dur(secondary)}
        exitFrame={CATALOG_SEGMENT - 14}
        glow={glow}
      />
      <Captions groups={[{ words }]} preset={theme.captionPreset} look={look.caption} />
      {theme.fx.includes("grain") ? <FilmGrain intensity={I.grain ?? 0.07} /> : null}
      {theme.fx.includes("progressBar") ? <ProgressBar color={look.colors.accent} /> : null}
      {showSafeArea ? <SafeAreaOverlay /> : null}
    </AbsoluteFill>
  );
};

/**
 * Review sheet for Studio: every theme for CATALOG_SEGMENT frames with its
 * default (hook) and secondary text preset, caption preset and fx stack over a
 * demo scene. `npm run render:catalog` grabs one still per theme.
 */
export const StyleCatalog: React.FC<StyleCatalogProps> = ({ themes, showSafeArea }) => {
  const looks = useMemo(() => themes.map((t) => resolveLook(getTheme(t), { ...BRAND_DEFAULTS })), [themes]);
  return (
    <Series>
      {looks.map((look, i) => (
        <Series.Sequence key={`${look.theme.name}${i}`} durationInFrames={CATALOG_SEGMENT} name={look.theme.label}>
          <Segment look={look} showSafeArea={showSafeArea} />
        </Series.Sequence>
      ))}
    </Series>
  );
};
