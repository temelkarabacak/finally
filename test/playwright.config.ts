import { defineConfig, devices } from "@playwright/test";

/**
 * Runs against an already-running FinAlly container. `docker-compose.test.yml`
 * starts the app and points BASE_URL at it; locally, default to the port a
 * hand-started container publishes.
 */
const baseURL = process.env.BASE_URL ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./e2e",
  // The whole suite mutates one shared SQLite database, so specs must not interleave.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL,
    viewport: { width: 1600, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
