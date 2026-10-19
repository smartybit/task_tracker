import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testIgnore: process.env.PREFIX_TESTS === "true" ? [] : ["**/instances.spec.ts"],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  // Account setup and complete task trees span many real API operations.
  timeout: process.env.PREFIX_TESTS === "true" ? 180_000 : 90_000,
  // Two live stacks add request/render latency; root acceptance keeps 5-second assertions.
  expect: { timeout: process.env.PREFIX_TESTS === "true" ? 15_000 : 5_000 },
  use: {
    baseURL: process.env.BASE_URL ?? "http://frontend:5173",
    ignoreHTTPSErrors: process.env.PREFIX_TESTS === "true",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
