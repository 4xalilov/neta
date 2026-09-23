import React, { useMemo } from "react";
import { z } from "zod";
import { AbsoluteFill, Sequence, type CalculateMetadataFunction } from "remotion";
import { THEME_NAMES } from "../motion/styles";
import { ensureFont } from "../lib/fonts";
import { CATALOG_STILL_FRAME, Segment, catalogLooks } from "./StyleCatalog";

/**
 * Contact sheet of the theme catalog: every theme's StyleCatalog segment,
 * frozen at CATALOG_STILL_FRAME and scaled into a grid with a name caption.
 * `npm run render:catalog` renders it to out/catalog/_sheet.png.
 */
export const catalogSheetSchema = z.object({
  themes: z.array(z.string()).default([...THEME_NAMES]),
  columns: z.number().int().min(1).max(12).default(6),
  /** Cell scale of the 1080×1920 frame (0.25 → 270×480). */
  cellScale: z.number().min(0.1).max(1).default(0.25),
  frame: z.number().int().min(0).default(CATALOG_STILL_FRAME),
});
export type CatalogSheetProps = z.output<typeof catalogSheetSchema>;
export const catalogSheetDefaultProps: CatalogSheetProps = catalogSheetSchema.parse({});

const PAD = 40;
const GAP = 20;
const HEADER = 110;
const CAPTION = 64;
const W = 1080;
const H = 1920;

export function sheetLayout(count: number, columns: number, cellScale: number) {
  const cw = Math.round(W * cellScale);
  const ch = Math.round(H * cellScale);
  const rows = Math.max(1, Math.ceil(count / columns));
  const width = PAD * 2 + columns * cw + (columns - 1) * GAP;
  const height = PAD * 2 + HEADER + rows * (ch + CAPTION) + (rows - 1) * GAP;
  // Remotion needs even dimensions for video; keep stills even too.
  return { cw, ch, rows, width: width + (width % 2), height: height + (height % 2) };
}

export const calculateSheetMetadata: CalculateMetadataFunction<CatalogSheetProps> = ({ props }) => {
  const p = catalogSheetSchema.parse(props);
  const { width, height } = sheetLayout(p.themes.length, p.columns, p.cellScale);
  return { width, height, durationInFrames: 1, props: p };
};

export const CatalogSheet: React.FC<CatalogSheetProps> = ({ themes, columns, cellScale, frame }) => {
  const looks = useMemo(() => catalogLooks(themes), [themes]);
  const { cw, ch } = sheetLayout(themes.length, columns, cellScale);
  const ui = ensureFont("Inter");
  return (
    <AbsoluteFill style={{ background: "#0B0F19", fontFamily: ui, color: "#E6EAF2" }}>
      <div style={{ position: "absolute", left: PAD, top: PAD, height: HEADER, display: "flex", alignItems: "baseline", gap: 24 }}>
        <span style={{ fontSize: 52, fontWeight: 800 }}>Neta · uslublar katalogi</span>
        <span style={{ fontSize: 30, fontWeight: 500, color: "#8B95AD" }}>
          {themes.length} ta tema · kadr {frame}
        </span>
      </div>
      {looks.map((look, i) => {
        const col = i % columns;
        const row = Math.floor(i / columns);
        const left = PAD + col * (cw + GAP);
        const top = PAD + HEADER + row * (ch + CAPTION + GAP);
        return (
          <div key={`${look.theme.name}${i}`} style={{ position: "absolute", left, top, width: cw, height: ch + CAPTION }}>
            <div style={{ position: "absolute", left: 0, top: 0, width: cw, height: ch, overflow: "hidden", borderRadius: 10, background: look.colors.bg }}>
              <div style={{ position: "absolute", left: 0, top: 0, width: W, height: H, transform: `scale(${cellScale})`, transformOrigin: "0 0" }}>
                {/* from = −frame: the sheet's frame 0 is the segment's frame `frame`. */}
                <Sequence from={-frame} width={W} height={H} name={look.theme.name}>
                  <Segment look={look} showSafeArea={false} />
                </Sequence>
              </div>
            </div>
            <div style={{ position: "absolute", left: 0, top: ch + 8, width: cw, fontSize: 24, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {look.theme.name}
            </div>
            <div style={{ position: "absolute", left: 0, top: ch + 38, width: cw, fontSize: 18, fontWeight: 500, color: "#8B95AD", whiteSpace: "nowrap", overflow: "hidden" }}>
              {look.theme.meta?.family ?? "—"} · {look.theme.fonts.display.family}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
