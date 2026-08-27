import { defineConfig, devices } from "@playwright/test";

const e2ePython = process.env.OSIP_E2E_PYTHON ?? "../.venv/bin/python";
const apiPort = process.env.OSIP_E2E_API_PORT ?? "8765";
const webPort = process.env.OSIP_E2E_WEB_PORT ?? "4173";
const apiUrl = `http://127.0.0.1:${apiPort}`;
const webUrl = `http://127.0.0.1:${webPort}`;

export default defineConfig({
  testDir: "./e2e",
  snapshotPathTemplate: "{testDir}/{testFilePath}-snapshots/{arg}{ext}",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? [["html", { open: "never" }], ["list"]] : "list",
  use: {
    baseURL: webUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  expect: {
    // A small perceptual allowance absorbs anti-aliasing noise only. Full-page
    // screenshots must be captured on the same platform that generates the
    // committed baseline (see the update-e2e-snapshots CI job) - a dimension
    // mismatch fails toHaveScreenshot regardless of this ratio.
    toHaveScreenshot: { animations: "disabled", threshold: 0.2, maxDiffPixelRatio: 0.03 }
  },
  webServer: [
    {
      command: `OSIP_E2E_PORT=${apiPort} ${e2ePython} ../scripts/e2e_backend.py`,
      url: `${apiUrl}/health`,
      timeout: 30_000,
      reuseExistingServer: false
    },
    {
      // scripts/e2e_backend.py seeds every fixture (OSIP workbooks and the
      // sanitized multi-source demo) as uploader_id="e2e-uploader" - the
      // frontend's own default local identity is "local-operator"
      // (session.ts), which intentionally doesn't match it, so this test
      // browser needs its own override to see that seeded data at all.
      command: `VITE_PROXY_TARGET=${apiUrl} VITE_ACTOR_ID=e2e-uploader npm run dev -- --host 127.0.0.1 --port ${webPort}`,
      url: webUrl,
      timeout: 30_000,
      reuseExistingServer: false
    }
  ],
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } }
    }
  ]
});
