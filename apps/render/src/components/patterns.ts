// Background pattern tiles (pure: name + colour → CSS background layer).
// Everything is inline SVG / CSS gradients — no image assets, no @remotion/shapes.
import type { PatternName } from "../motion/styles/patterns";

export interface PatternLayer {
  /** CSS background-image value. */
  image: string;
  /** CSS background-size ("auto" for gradients that fill the frame). */
  size: string;
  /** Tile size in px for drift wrapping (0 = no drift). */
  tile: [number, number];
}

const svg = (w: number, h: number, body: string) =>
  `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${body}</svg>`,
  )}")`;

const tile = (w: number, h: number, body: string): PatternLayer => ({ image: svg(w, h, body), size: `${w}px ${h}px`, tile: [w, h] });

const r = (n: number) => Math.round(n * 10) / 10;

/** Stepped (abr/ikat) diamond outline as polygon points. */
function steppedDiamond(cx: number, cy: number, hw: number, hh: number, steps: number): string {
  const dx = hw / steps;
  const dy = hh / steps;
  const pts: [number, number][] = [];
  for (let i = 0; i < steps; i++) pts.push([cx + i * dx, cy - hh + i * dy], [cx + (i + 1) * dx, cy - hh + i * dy]);
  for (let i = 0; i < steps; i++) pts.push([cx + hw - i * dx, cy + i * dy], [cx + hw - i * dx, cy + (i + 1) * dy]);
  for (let i = 0; i < steps; i++) pts.push([cx - i * dx, cy + hh - i * dy], [cx - (i + 1) * dx, cy + hh - i * dy]);
  for (let i = 0; i < steps; i++) pts.push([cx - hw + i * dx, cy - i * dy], [cx - hw + i * dx, cy - (i + 1) * dy]);
  return pts.map(([x, y]) => `${r(x)},${r(y)}`).join(" ");
}

function ikat(c: string): PatternLayer {
  const W = 140;
  const H = 220;
  const motif = (cx: number, cy: number) =>
    `<polygon points="${steppedDiamond(cx, cy, 52, 96, 8)}" fill="${c}"/>` +
    `<polygon points="${steppedDiamond(cx, cy, 34, 62, 6)}" fill="#000" fill-opacity="0.55"/>` +
    `<polygon points="${steppedDiamond(cx, cy, 16, 30, 4)}" fill="${c}"/>` +
    // feathered (blurred-dye) dashes along the edge, the ikat signature
    [-1, 1]
      .map((s) =>
        [0.25, 0.5, 0.75]
          .map((k) => `<rect x="${r(cx + s * 52 * (1 - k) - (s > 0 ? 0 : 14))}" y="${r(cy - 96 + 96 * k * 2 - 3)}" width="14" height="5" fill="${c}" fill-opacity="0.5"/>`)
          .join(""),
      )
      .join("");
  return tile(W, H, motif(W / 2, H / 2) + motif(0, 0) + motif(W, 0) + motif(0, H) + motif(W, H));
}

function adras(c: string): PatternLayer {
  const W = 160;
  const H = 240;
  const band = (x0: number, w: number, amp: number, op: number) => {
    const left: string[] = [];
    const right: string[] = [];
    for (let y = 0; y <= H; y += 12) {
      const s = Math.sin((y / H) * Math.PI * 2);
      left.push(`${r(x0 + amp * s)},${y}`);
      right.unshift(`${r(x0 + w + amp * s * 0.6)},${y}`);
    }
    return `<polygon points="${[...left, ...right].join(" ")}" fill="${c}" fill-opacity="${op}"/>`;
  };
  return tile(W, H, band(8, 34, 10, 1) + band(62, 12, 8, 0.55) + band(92, 44, 12, 0.8) + band(146, 8, 6, 0.4));
}

function suzani(c: string): PatternLayer {
  const W = 220;
  const rosette = (cx: number, cy: number, R: number) => {
    let petals = "";
    for (let k = 0; k < 8; k++) {
      const a = (k * 45 * Math.PI) / 180;
      petals += `<ellipse cx="${r(cx + Math.cos(a) * R * 1.45)}" cy="${r(cy + Math.sin(a) * R * 1.45)}" rx="${r(R * 0.28)}" ry="${r(R * 0.55)}" transform="rotate(${k * 45 + 90} ${r(cx + Math.cos(a) * R * 1.45)} ${r(cy + Math.sin(a) * R * 1.45)})" fill="${c}"/>`;
    }
    return (
      petals +
      `<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${c}" stroke-width="${r(R * 0.22)}"/>` +
      `<circle cx="${cx}" cy="${cy}" r="${r(R * 0.45)}" fill="${c}"/>` +
      `<circle cx="${cx}" cy="${cy}" r="${r(R * 0.72)}" fill="none" stroke="${c}" stroke-width="2" stroke-dasharray="4 5"/>`
    );
  };
  return tile(W, W, rosette(W / 2, W / 2, 40) + [0, W].flatMap((x) => [0, W].map((y) => rosette(x, y, 22))).join(""));
}

function girih(c: string): PatternLayer {
  const W = 120;
  const star = (cx: number, cy: number, R: number, rIn: number) => {
    const pts: string[] = [];
    for (let k = 0; k < 16; k++) {
      const a = ((k * 22.5 - 90) * Math.PI) / 180;
      const rr = k % 2 === 0 ? R : rIn;
      pts.push(`${r(cx + Math.cos(a) * rr)},${r(cy + Math.sin(a) * rr)}`);
    }
    return `<polygon points="${pts.join(" ")}" fill="none" stroke="${c}" stroke-width="4" stroke-linejoin="round"/>`;
  };
  const cx = W / 2;
  const lines =
    `<path d="M${cx} ${cx - 44}V0M${cx} ${cx + 44}V${W}M${cx - 44} ${cx}H0M${cx + 44} ${cx}H${W}" stroke="${c}" stroke-width="4"/>` +
    `<path d="M${cx - 31} ${cx - 31}L0 0M${cx + 31} ${cx - 31}L${W} 0M${cx - 31} ${cx + 31}L0 ${W}M${cx + 31} ${cx + 31}L${W} ${W}" stroke="${c}" stroke-width="2" stroke-opacity="0.6"/>`;
  return tile(W, W, star(cx, cx, 44, 30) + star(cx, cx, 20, 14) + lines + [0, W].flatMap((x) => [0, W].map((y) => star(x, y, 16, 11))).join(""));
}

function stars(c: string): PatternLayer {
  const W = 280;
  const sparkle = (x: number, y: number, s: number) =>
    `<path d="M${x} ${y - s}Q${x} ${y} ${x + s} ${y}Q${x} ${y} ${x} ${y + s}Q${x} ${y} ${x - s} ${y}Q${x} ${y} ${x} ${y - s}Z" fill="${c}"/>`;
  return tile(
    W,
    W,
    `<defs><mask id="m"><rect width="${W}" height="${W}" fill="#fff"/><circle cx="92" cy="78" r="30" fill="#000"/></mask></defs>` +
      `<circle cx="76" cy="90" r="34" fill="${c}" mask="url(#m)"/>` +
      sparkle(200, 60, 12) +
      sparkle(230, 190, 7) +
      sparkle(40, 220, 9) +
      sparkle(150, 250, 5) +
      sparkle(130, 150, 4) +
      [
        [20, 30],
        [250, 110],
        [170, 110],
        [100, 200],
        [260, 260],
      ]
        .map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2" fill="${c}"/>`)
        .join(""),
  );
}

function confetti(c: string): PatternLayer {
  const W = 240;
  const items = [
    `<rect x="20" y="30" width="26" height="10" rx="3" transform="rotate(25 33 35)"/>`,
    `<circle cx="140" cy="40" r="7"/>`,
    `<polygon points="200,90 216,118 184,118"/>`,
    `<rect x="70" y="120" width="10" height="28" rx="3" transform="rotate(-30 75 134)"/>`,
    `<path d="M150 170q10-14 20 0t20 0" fill="none" stroke="${c}" stroke-width="6" stroke-linecap="round"/>`,
    `<circle cx="40" cy="200" r="5"/>`,
    `<rect x="190" y="200" width="22" height="9" rx="3" transform="rotate(-50 201 204)"/>`,
    `<polygon points="100,60 110,78 90,78" transform="rotate(20 100 70)"/>`,
  ];
  return tile(W, W, `<g fill="${c}">${items.join("")}</g>`);
}

/** Paper fibres: fractal noise tinted with the pattern colour. */
function paper(c: string): PatternLayer {
  const [R, G, B] = [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16) / 255);
  return tile(
    300,
    300,
    `<filter id="p"><feTurbulence type="fractalNoise" baseFrequency="0.75" numOctaves="3" seed="7" stitchTiles="stitch"/>` +
      `<feColorMatrix values="0 0 0 0 ${r(R ?? 0)} 0 0 0 0 ${r(G ?? 0)} 0 0 0 0 ${r(B ?? 0)} 1.4 0 0 0 -0.55"/></filter>` +
      `<rect width="300" height="300" filter="url(#p)"/>` +
      `<path d="M10 40q60 8 120 -4M160 210q50 10 110 -6M40 150q40 6 70 -2" stroke="${c}" stroke-width="1" fill="none" stroke-opacity="0.5"/>`,
  );
}

/** CSS layer for a pattern (retroGrid is drawn by ThemeBackground itself). */
export function patternLayer(name: PatternName, color: string): PatternLayer | null {
  switch (name) {
    case "ikat":
      return ikat(color);
    case "adras":
      return adras(color);
    case "suzani":
      return suzani(color);
    case "girih":
      return girih(color);
    case "stars":
      return stars(color);
    case "confetti":
      return confetti(color);
    case "paper":
      return paper(color);
    case "dots":
      return tile(44, 44, `<circle cx="22" cy="22" r="4.5" fill="${color}"/>`);
    case "halftone":
      return tile(28, 28, `<circle cx="7" cy="7" r="6.5" fill="${color}"/><circle cx="21" cy="21" r="6.5" fill="${color}"/>`);
    case "grid":
      return tile(72, 72, `<path d="M0 0.75H72M0.75 0V72" stroke="${color}" stroke-width="1.5"/>`);
    case "lines":
      return tile(80, 64, `<path d="M0 63H80" stroke="${color}" stroke-width="2"/>`);
    case "waves":
      return tile(200, 56, `<path d="M0 28Q25 8 50 28T100 28T150 28T200 28" fill="none" stroke="${color}" stroke-width="3"/>`);
    case "stripes":
      return { image: `repeating-linear-gradient(135deg, ${color} 0 14px, transparent 14px 48px)`, size: "auto", tile: [0, 0] };
    case "scanlines":
      return { image: `repeating-linear-gradient(180deg, ${color} 0 2px, transparent 2px 6px)`, size: "auto", tile: [0, 0] };
    case "retroGrid":
      return null;
  }
}
