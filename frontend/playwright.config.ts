import { defineConfig, devices } from "@playwright/test";

const useExternalServers = ["1", "true", "yes"].includes(
  (process.env.PLAYWRIGHT_EXTERNAL_SERVERS ?? "").toLowerCase(),
);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: useExternalServers
    ? undefined
    : {
        command: "python ../scripts/run_fullstack.py --reset-seed",
        url: "http://127.0.0.1:5173/",
        reuseExistingServer: false,
        timeout: 180_000,
        gracefulShutdown: { signal: "SIGTERM", timeout: 10_000 },
        env: {
          VITE_API_BASE_URL: "/api/v1",
          VITE_DATA_SOURCE: "api",
          VITE_ENABLE_TECHNICAL_VIEW: "false",
        },
      },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
