import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { activeWordIndex, pageAt, pageWords, type CaptionPage, type Word } from "../../lib/captions";
import { uzbekSafe } from "../../lib/fonts";
import { springs } from "../easings";
import { CAPTION_META, isCaptionPreset, type CaptionPreset } from "./registry";

export interface CaptionLook {
  fontFamily: string;
  fontWeight?: number;
  color: string;
  accent: string;
  /** Box colour for boxHighlight (defaults to accent). */
  highlight?: string;
  onHighlight?: string;
  surface?: string;
  uppercase?: boolean;
  /** Outline px (karaoke / boxHighlight / bigWord). docs/08: 6 px black. */
  stroke?: number;
  /** Multiplier on the preset font size. */
  scale?: number;
}

export interface CaptionGroup {
  /** Word timings (seconds from composition start) of one scene. */
  words: Word[];
  preset?: CaptionPreset | string | null;
}

export interface StaticCaption {
  text: string;
  start: number;
  end: number;
  preset?: CaptionPreset | string | null;
}

type TaggedPage = CaptionPage & { preset: CaptionPreset };

/** Page every scene's words with its preset's budget; pages never span scenes. */
export function pageGroups(groups: CaptionGroup[], fallback: CaptionPreset): TaggedPage[] {
  const pages: TaggedPage[] = [];
  for (const g of groups) {
    const preset = isCaptionPreset(g.preset) ? g.preset : fallback;
    const m = CAPTION_META[preset];
    for (const p of pageWords(g.words, m.maxChars, m.maxLines)) pages.push({ ...p, preset });
  }
  pages.sort((a, b) => a.start - b.start);
  return pages.map((p, i) => {
    const next = pages[i + 1];
    return next && next.start < p.end ? { ...p, end: Math.max(p.start, next.start) } : p;
  });
}

const baseText = (look: CaptionLook, size: number, stroke: number): React.CSSProperties => ({
  fontFamily: look.fontFamily,
  fontWeight: look.fontWeight ?? 800,
  fontSize: size * (look.scale ?? 1),
  lineHeight: 1.18,
  letterSpacing: "-0.01em",
  textTransform: look.uppercase ? "uppercase" : undefined,
  WebkitTextStroke: stroke ? `${stroke}px #000` : undefined,
  paintOrder: stroke ? "stroke fill" : undefined,
  textShadow: stroke ? "0 6px 18px rgba(0,0,0,0.55), 0 0 2px #000" : "0 4px 16px rgba(0,0,0,0.45)",
});

/** Band anchored 22 % from the bottom (docs/08), inside the side margins. */
const Band: React.FC<{ children: React.ReactNode; scale?: number; style?: React.CSSProperties }> = ({ children, scale = 1, style }) => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <div
      style={{
        position: "absolute",
        left: 60,
        right: 60,
        bottom: "22%",
        textAlign: "center",
        transform: `scale(${scale})`,
        transformOrigin: "50% 100%",
        ...style,
      }}
    >
      {children}
    </div>
  </AbsoluteFill>
);

interface RenderArgs {
  page: TaggedPage;
  t: number;
  frame: number;
  fps: number;
  look: CaptionLook;
}

const pop = (frame: number, fps: number, start: number) =>
  spring({ frame: frame - Math.round(start * fps), fps, config: { damping: 9, stiffness: 260, mass: 0.6 } });

function Karaoke({ page, t, frame, fps, look }: RenderArgs) {
  const active = activeWordIndex(page, t);
  const pageIn = spring({ frame: frame - Math.round(page.start * fps), fps, config: { damping: 14, stiffness: 200 } });
  let k = 0;
  return (
    <Band scale={0.9 + 0.1 * pageIn} style={baseText(look, CAPTION_META.karaoke.fontSize, look.stroke ?? 6)}>
      {page.lines.map((line, li) => (
        <div key={li}>
          {line.map((word, wi) => {
            const isActive = k++ === active;
            return (
              <span
                key={wi}
                style={{
                  display: "inline-block",
                  margin: "0 0.14em",
                  color: isActive ? look.accent : look.color,
                  transform: `scale(${isActive ? 0.85 + 0.21 * pop(frame, fps, word.start) : 1})`,
                  transformOrigin: "50% 70%",
                }}
              >
                {word.w}
              </span>
            );
          })}
        </div>
      ))}
    </Band>
  );
}

function BoxHighlight({ page, t, frame, fps, look }: RenderArgs) {
  const active = activeWordIndex(page, t);
  const pageIn = spring({ frame: frame - Math.round(page.start * fps), fps, config: springs.snappy });
  const box = look.highlight ?? look.accent;
  let k = 0;
  return (
    <Band scale={0.85 + 0.15 * pageIn} style={{ ...baseText(look, CAPTION_META.boxHighlight.fontSize, look.stroke ?? 5), lineHeight: 1.3 }}>
      {page.lines.map((line, li) => (
        <div key={li}>
          {line.map((word, wi) => {
            const isActive = k++ === active;
            const p = isActive ? pop(frame, fps, word.start) : 0;
            return (
              <span
                key={wi}
                style={{
                  display: "inline-block",
                  margin: "0.04em 0.06em",
                  padding: "0 0.14em",
                  borderRadius: "0.18em",
                  background: isActive ? box : "transparent",
                  color: isActive ? (look.onHighlight ?? "#0B0F19") : look.color,
                  WebkitTextStroke: isActive ? "0px transparent" : undefined,
                  textShadow: isActive ? "none" : undefined,
                  transform: `scale(${isActive ? 0.9 + 0.16 * p : 1}) rotate(${isActive ? -2 * (1 - Math.min(1, p)) : 0}deg)`,
                  boxShadow: isActive ? "0 10px 30px rgba(0,0,0,0.45)" : undefined,
                }}
              >
                {word.w}
              </span>
            );
          })}
        </div>
      ))}
    </Band>
  );
}

function PillGlass({ page, t, frame, fps, look }: RenderArgs) {
  const active = activeWordIndex(page, t);
  const pageIn = spring({ frame: frame - Math.round(page.start * fps), fps, config: springs.snappy });
  let k = 0;
  return (
    <Band scale={1} style={{ display: "flex", justifyContent: "center" }}>
      <div
        style={{
          ...baseText(look, CAPTION_META.pillGlass.fontSize, 0),
          textShadow: "none",
          fontWeight: look.fontWeight ?? 700,
          background: `${look.surface ?? "#131A2A"}99`,
          backdropFilter: "blur(22px) saturate(1.5)",
          border: "2px solid rgba(255,255,255,0.18)",
          borderRadius: 48,
          padding: "22px 40px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
          opacity: Math.min(1, pageIn * 1.5),
          transform: `translateY(${(1 - pageIn) * 40}px)`,
        }}
      >
        {page.lines.map((line, li) => (
          <div key={li}>
            {line.map((word, wi) => {
              const idx = k++;
              const spoken = idx <= active;
              return (
                <span
                  key={wi}
                  style={{
                    display: "inline-block",
                    margin: "0 0.12em",
                    color: idx === active ? look.accent : look.color,
                    opacity: spoken ? 1 : 0.45,
                  }}
                >
                  {word.w}
                </span>
              );
            })}
          </div>
        ))}
      </div>
    </Band>
  );
}

function BigWord({ page, t, frame, fps, look }: RenderArgs) {
  const active = Math.max(0, activeWordIndex(page, t));
  const word = page.words[active]!;
  const p = spring({ frame: frame - Math.round(word.start * fps), fps, config: springs.bouncy });
  const len = Math.max(1, word.w.length);
  // Shrink long words so they fit 960 px (≈ 0.62 em per glyph).
  const size = Math.min(CAPTION_META.bigWord.fontSize, Math.floor(960 / (len * 0.62))) * (look.scale ?? 1);
  const accent = /\d/.test(word.w) || active % 3 === 2;
  return (
    <Band style={{ ...baseText(look, size / (look.scale ?? 1), look.stroke ?? 8), lineHeight: 1 }}>
      <span
        style={{
          display: "inline-block",
          color: accent ? look.accent : look.color,
          transform: `scale(${0.5 + 0.5 * p})`,
          opacity: Math.min(1, p * 3),
          whiteSpace: "nowrap",
        }}
      >
        {word.w}
      </span>
    </Band>
  );
}

function LineByLine({ page, t, frame, fps, look }: RenderArgs) {
  const active = activeWordIndex(page, t);
  const f0 = Math.round(page.start * fps);
  const p = interpolate(frame - f0, [0, 9], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: (x) => 1 - Math.pow(1 - x, 4) });
  return (
    <Band style={{ ...baseText(look, CAPTION_META.lineByLine.fontSize, 0), fontWeight: look.fontWeight ?? 700, textShadow: "0 4px 20px rgba(0,0,0,0.7)" }}>
      <div style={{ overflow: "hidden", paddingBottom: "0.1em" }}>
        <div style={{ transform: `translateY(${(1 - p) * 105}%)` }}>
          {page.words.map((word, i) => (
            <span key={i} style={{ display: "inline-block", margin: "0 0.12em", color: i === active ? look.accent : look.color, opacity: i <= active ? 1 : 0.55 }}>
              {word.w}
            </span>
          ))}
        </div>
      </div>
      <div style={{ width: 120 * p, height: 5, borderRadius: 3, background: look.accent, margin: "10px auto 0" }} />
    </Band>
  );
}

const RENDERERS: Record<CaptionPreset, (a: RenderArgs) => React.ReactElement> = {
  karaoke: Karaoke,
  boxHighlight: BoxHighlight,
  pillGlass: PillGlass,
  bigWord: BigWord,
  lineByLine: LineByLine,
};

/**
 * Word-timed captions with per-scene presets. Scenes without word timings can
 * show a static `subtitle` (rendered in the same preset look, no highlight).
 */
export const Captions: React.FC<{
  groups: CaptionGroup[];
  staticCaptions?: StaticCaption[];
  preset?: CaptionPreset;
  look: CaptionLook;
}> = ({ groups, staticCaptions = [], preset = "karaoke", look }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const safeGroups = useMemo(
    () => groups.map((g) => ({ ...g, words: g.words.map((w) => ({ ...w, w: uzbekSafe(w.w, look.fontFamily) })) })),
    [groups, look.fontFamily],
  );
  const pages = useMemo(() => pageGroups(safeGroups, preset), [safeGroups, preset]);
  const page = pageAt(pages, t) as TaggedPage | null;
  if (page) return RENDERERS[page.preset]({ page, t, frame, fps, look });

  const s = staticCaptions.find((c) => t >= c.start && t < c.end);
  if (!s) return null;
  const sp = isCaptionPreset(s.preset) ? s.preset : preset;
  const text = uzbekSafe(s.text, look.fontFamily);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <Band style={{ ...baseText(look, 66, sp === "pillGlass" || sp === "lineByLine" ? 0 : (look.stroke ?? 6)), color: look.color }}>
        {text}
      </Band>
    </AbsoluteFill>
  );
};
