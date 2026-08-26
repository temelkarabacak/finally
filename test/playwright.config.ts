import { defineConfig, devices } from "@playwright/test";

/**
 * E2E harness config. baseURL comes from BASE_URL (set by
 * docker-compose.test.yml to the compose service DNS name); no auto-started
 * dev server config here because compose starts the app container, not
 * Playwright itself.
 *
 * workers: 1 + fullyParallel: false are load-bearing, not a performance
 * choice: every spec shares one seeded $10,000 portfolio inside one app
 * container, so parallel execution would let a trade in one spec invalidate
 * a balance assertion in another. Serial execution also means an
 * interrupted run leaves no partially-mutated shared state to clean up.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  reporter: "list",
  timeout: 30000,
  expect: {
    timeout: 10000,
  },
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:8000",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
