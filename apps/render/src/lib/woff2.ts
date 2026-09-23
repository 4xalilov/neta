// Minimal WOFF2 → cmap reader (test helper): enough to answer "does this font
// file contain code point X?". Uses Node's built-in brotli.
import { brotliDecompressSync } from "node:zlib";

const KNOWN_TAGS = [
  "cmap", "head", "hhea", "hmtx", "maxp", "name", "OS/2", "post", "cvt ", "fpgm", "glyf", "loca", "prep", "CFF ", "VORG", "EBDT",
  "EBLC", "gasp", "hdmx", "kern", "LTSH", "PCLT", "VDMX", "vhea", "vmtx", "BASE", "GDEF", "GPOS", "GSUB", "EBSC", "JSTF", "MATH",
  "CBDT", "CBLC", "COLR", "CPAL", "SVG ", "sbix", "acnt", "avar", "bdat", "bloc", "bsln", "cvar", "fdsc", "feat", "fmtx", "fvar",
  "gvar", "hsty", "just", "lcar", "mort", "morx", "opbd", "prop", "trak", "Zapf", "Silf", "Glat", "Gloc", "Feat", "Sill",
];

function readBase128(buf: Buffer, pos: { o: number }): number {
  let v = 0;
  for (let i = 0; i < 5; i++) {
    const b = buf[pos.o++]!;
    v = v * 128 + (b & 0x7f);
    if (!(b & 0x80)) return v;
  }
  throw new Error("bad UIntBase128");
}

/** Decompressed `cmap` table of a WOFF2 file. */
export function woff2Cmap(file: Buffer): Buffer {
  if (file.toString("latin1", 0, 4) !== "wOF2") throw new Error("not a WOFF2 file");
  const numTables = file.readUInt16BE(12);
  const compressedSize = file.readUInt32BE(20);
  const pos = { o: 48 };
  const tables: { tag: string; length: number }[] = [];
  for (let i = 0; i < numTables; i++) {
    const flags = file[pos.o++]!;
    const idx = flags & 0x3f;
    const version = flags >> 6;
    let tag: string;
    if (idx === 63) {
      tag = file.toString("latin1", pos.o, pos.o + 4);
      pos.o += 4;
    } else tag = KNOWN_TAGS[idx]!;
    const orig = readBase128(file, pos);
    const transformed = tag === "glyf" || tag === "loca" ? version === 0 : version !== 0;
    const length = transformed ? readBase128(file, pos) : orig;
    tables.push({ tag, length });
  }
  const data = brotliDecompressSync(file.subarray(pos.o, pos.o + compressedSize));
  let off = 0;
  for (const t of tables) {
    if (t.tag === "cmap") return data.subarray(off, off + t.length);
    off += t.length;
  }
  throw new Error("no cmap table");
}

/** Does the cmap map `cp` to a glyph? Supports formats 4 and 12. */
export function cmapHas(cmap: Buffer, cp: number): boolean {
  const n = cmap.readUInt16BE(2);
  const subtables: number[] = [];
  for (let i = 0; i < n; i++) {
    const platform = cmap.readUInt16BE(4 + i * 8);
    const encoding = cmap.readUInt16BE(6 + i * 8);
    const offset = cmap.readUInt32BE(8 + i * 8);
    if (platform === 0 || (platform === 3 && (encoding === 1 || encoding === 10))) subtables.push(offset);
  }
  for (const o of subtables) {
    const format = cmap.readUInt16BE(o);
    if (format === 12) {
      const groups = cmap.readUInt32BE(o + 12);
      for (let g = 0; g < groups; g++) {
        const start = cmap.readUInt32BE(o + 16 + g * 12);
        const end = cmap.readUInt32BE(o + 20 + g * 12);
        if (cp >= start && cp <= end) return true;
      }
    } else if (format === 4 && cp <= 0xffff) {
      const segX2 = cmap.readUInt16BE(o + 6);
      const endO = o + 14;
      const startO = endO + segX2 + 2;
      const deltaO = startO + segX2;
      const rangeO = deltaO + segX2;
      for (let s = 0; s < segX2 / 2; s++) {
        const end = cmap.readUInt16BE(endO + s * 2);
        const start = cmap.readUInt16BE(startO + s * 2);
        if (cp < start || cp > end) continue;
        if (start === 0xffff) return false;
        const rangeOffset = cmap.readUInt16BE(rangeO + s * 2);
        if (rangeOffset === 0) return true;
        const glyphAddr = rangeO + s * 2 + rangeOffset + (cp - start) * 2;
        return cmap.readUInt16BE(glyphAddr) !== 0;
      }
    }
  }
  return false;
}
