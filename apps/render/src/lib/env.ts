// Node-side (worker / local render) browser options derived from env.
// Never import this from composition code — it runs in the browser bundle.

export type ChromeMode = "headless-shell" | "chrome-for-testing";

export interface BrowserOptions {
  browserExecutable: string | null;
  chromeMode: ChromeMode;
}

/**
 * REMOTION_BROWSER       – path to a preinstalled Chrome/Chromium; when unset Remotion
 *                          downloads chrome-headless-shell itself (needs network).
 * REMOTION_CHROME_MODE   – override: "headless-shell" | "chrome-for-testing".
 *                          Default: "chrome-for-testing" when REMOTION_BROWSER is a full
 *                          Chrome (>=132 dropped `--headless=old`), else "headless-shell".
 */
export function browserOptionsFromEnv(env: NodeJS.ProcessEnv = process.env): BrowserOptions {
  const browserExecutable = env.REMOTION_BROWSER?.trim() || null;
  const override = env.REMOTION_CHROME_MODE;
  const chromeMode: ChromeMode =
    override === "headless-shell" || override === "chrome-for-testing"
      ? override
      : browserExecutable
        ? "chrome-for-testing"
        : "headless-shell";
  return { browserExecutable, chromeMode };
}
