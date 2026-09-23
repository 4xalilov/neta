// Remotion CLI config (used by `npm run studio` and `npx remotion render`).
// The worker (src/worker.ts) and src/renderLocal.ts call @remotion/renderer
// directly and pass the same options explicitly — see src/lib/env.ts.
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setEntryPoint("src/index.ts");

// Use a preinstalled Chromium instead of letting Remotion download
// chrome-headless-shell (offline CI, Docker image with apt chromium, ...).
const browser = process.env.REMOTION_BROWSER;
if (browser) {
  Config.setBrowserExecutable(browser);
  // A full Chrome/Chromium >= 132 no longer supports `--headless=old`,
  // so it must be driven in "chrome-for-testing" mode (`--headless=new`).
  Config.setChromeMode(
    process.env.REMOTION_CHROME_MODE === "headless-shell" ? "headless-shell" : "chrome-for-testing",
  );
}
