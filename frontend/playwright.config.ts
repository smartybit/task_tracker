import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testIgnore: process.env.PREFIX_TESTS === "true" ? [] : ["**/instances.spec.ts"],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  // Account setup and complete task trees span many real API operations.
  timeout: 90_000,
  use: {
    baseURL: process.env.BASE_URL ?? "http://frontend:5173",
    ignoreHTTPSErrors: process.env.PREFIX_TESTS === "true",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
