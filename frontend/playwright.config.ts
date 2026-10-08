import { defineConfig, devices } from "@playwright/test";
import type { Project } from "@playwright/test";

const suite = process.env.PLAYWRIGHT_SUITE ?? "mocked";
if (!["mocked", "integration", "visual"].includes(suite)) {
  throw new Error(`Unknown PLAYWRIGHT_SUITE: ${suite}`);
}
const isCI = Boolean(process.env.CI);
const isIntegration = suite === "integration";
const port = Number(process.env.PLAYWRIGHT_PORT ?? 4187);
if (!Number.isInteger(port) || port < 1024 || port > 65535) {
  throw new Error("PLAYWRIGHT_PORT must be an integer between 1024 and 65535");
}

function integrationURL(): string {
  const value = process.env.PLAYWRIGHT_INTEGRATION_BASE_URL;
  if (!value) {
    throw new Error(
      "Set PLAYWRIGHT_INTEGRATION_BASE_URL to the dedicated test frontend origin. See README.md.",
    );
  }
  const url = new URL(value);
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  ) {
    throw new Error(
      "PLAYWRIGHT_INTEGRATION_BASE_URL must be an HTTP(S) origin without credentials, path, query or hash",
    );
  }
  return url.origin;
}

const baseURL = isIntegration ? integrationURL() : `http://127.0.0.1:${port}`;
const smoke = /@smoke|@responsive/;
const desktop = { viewport: { width: 1440, height: 900 } };
const projects: Record<string, Project[]> = {
  mocked: [
    { name: "mocked-chromium", use: { ...devices["Desktop Chrome"], ...desktop } },
    { name: "mocked-firefox", grep: smoke, use: { ...devices["Desktop Firefox"], ...desktop } },
    { name: "mocked-webkit", grep: smoke, use: { ...devices["Desktop Safari"], ...desktop } },
    { name: "mocked-android", grep: smoke, use: { ...devices["Pixel 7"] } },
    { name: "mocked-ios", grep: smoke, use: { ...devices["iPhone 13"] } },
    { name: "mocked-tablet", grep: /@responsive/, use: { ...devices["iPad Mini"] } },
  ],
  integration: [
    { name: "integration-chromium", use: { ...devices["Desktop Chrome"], ...desktop } },
    { name: "integration-webkit", grep: /@smoke/, use: { ...devices["iPhone 13"] } },
  ],
  visual: [
    { name: "visual-desktop", use: { ...devices["Desktop Chrome"], ...desktop } },
    { name: "visual-mobile", use: { ...devices["Pixel 7"] } },
  ],
};

export default defineConfig({
  testDir: "./e2e",
  testMatch: `${suite}/**/*.spec.ts`,
  fullyParallel: !isIntegration,
  workers: isIntegration || isCI ? 1 : 2,
  forbidOnly: isCI,
  failOnFlakyTests: isCI,
  retries: isCI ? 1 : 0,
  timeout: 30_000,
  expect: {
    timeout: 5_000,
    toHaveScreenshot: { animations: "disabled", caret: "hide", maxDiffPixels: 0 },
  },
  outputDir: `test-results/${suite}`,
  snapshotPathTemplate: "{testDir}/visual/__screenshots__/{projectName}/{testFilePath}/{arg}{ext}",
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["junit", { outputFile: `test-results/${suite}.xml` }],
  ],
  use: {
    baseURL,
    locale: "ru-RU",
    timezoneId: "Europe/Moscow",
    colorScheme: "light",
    storageState: { cookies: [], origins: [] },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    serviceWorkers: isIntegration ? "allow" : "block",
  },
  projects: projects[suite],
  webServer: isIntegration
    ? undefined
    : {
        command: `npm run dev -- --host 127.0.0.1 --port ${port} --strictPort`,
        url: baseURL,
        reuseExistingServer: false,
        timeout: 60_000,
        env: { VITE_API_URL: "/api", VITE_PROXY_TARGET: "http://127.0.0.1:1" },
      },
});
