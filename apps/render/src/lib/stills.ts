// Node-side still rendering for the theme catalog (render:catalog, theme:validate).
// One bundle + one browser per process; stills are rendered in parallel tabs.
import { mkdir, stat } from "node:fs/promises";
import path from "node:path";
import { openBrowser, renderStill, selectComposition } from "@remotion/renderer";
import { browserOptionsFromEnv } from "./env";
import { getServeUrl } from "../render";
import { CATALOG_STILL_FRAME } from "../compositions/StyleCatalog";

type Browser = Awaited<ReturnType<typeof openBrowser>>;

export interface StillSession {
  serveUrl: string;
  browser: Browser;
  browserExecutable: string | null;
  chromeMode: ReturnType<typeof browserOptionsFromEnv>["chromeMode"];
  close: () => Promise<void>;
}

export async function openStillSession(): Promise<StillSession> {
  const serveUrl = await getServeUrl();
  const { browserExecutable, chromeMode } = browserOptionsFromEnv();
  const browser = await openBrowser("chrome", { browserExecutable, chromeMode, logLevel: "error" });
  return { serveUrl, browser, browserExecutable, chromeMode, close: () => browser.close({ silent: true }) };
}

export interface StillResult {
  output: string;
  bytes: number;
  ms: number;
}

/** Render one composition frame to a PNG. */
export async function renderPng(
  s: StillSession,
  opts: { id: string; inputProps: Record<string, unknown>; output: string; frame?: number; scale?: number },
): Promise<StillResult> {
  const t0 = Date.now();
  await mkdir(path.dirname(opts.output), { recursive: true });
  const common = {
    serveUrl: s.serveUrl,
    inputProps: opts.inputProps,
    browserExecutable: s.browserExecutable,
    chromeMode: s.chromeMode,
    puppeteerInstance: s.browser,
    logLevel: "error" as const,
  };
  const composition = await selectComposition({ ...common, id: opts.id });
  await renderStill({
    ...common,
    composition,
    output: opts.output,
    frame: opts.frame ?? 0,
    scale: opts.scale ?? 1,
    imageFormat: "png",
    overwrite: true,
    timeoutInMilliseconds: 120000,
  });
  const { size } = await stat(opts.output);
  return { output: opts.output, bytes: size, ms: Date.now() - t0 };
}

/** The StyleCatalog still of one theme (by name, or a full theme object). */
export function renderThemeStill(
  s: StillSession,
  opts: { theme: string | Record<string, unknown>; output: string; scale?: number; frame?: number; showSafeArea?: boolean },
): Promise<StillResult> {
  const inputProps =
    typeof opts.theme === "string"
      ? { themes: [opts.theme], themeObjects: [], showSafeArea: !!opts.showSafeArea }
      : { themes: [], themeObjects: [opts.theme], showSafeArea: !!opts.showSafeArea };
  return renderPng(s, { id: "StyleCatalog", inputProps, output: opts.output, frame: opts.frame ?? CATALOG_STILL_FRAME, scale: opts.scale ?? 0.5 });
}

/** Run `fn` over `items` with at most `n` in flight. */
export async function pool<T, R>(items: T[], n: number, fn: (item: T, i: number) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let next = 0;
  const worker = async () => {
    while (next < items.length) {
      const i = next++;
      out[i] = await fn(items[i]!, i);
    }
  };
  await Promise.all(Array.from({ length: Math.max(1, Math.min(n, items.length)) }, worker));
  return out;
}
