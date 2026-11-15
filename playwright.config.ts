import { defineConfig, devices } from "@playwright/test";

const port = 3100;

export default defineConfig({
  testDir: "e2e",
  testIgnore: ["out/**", ".next/**", "hardware/**", "trend/**", "validation/**", "mapdata/**"],
  reporter: "line",
  // a retried test is reported as flaky, so a slow machine does not hide a real failure
  retries: 1,
  expect: { timeout: 10_000 },
  use: { baseURL: `http://localhost:${port}` },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `python3 -m http.server ${port} --bind 127.0.0.1 --directory out`,
    url: `http://localhost:${port}/mission/`,
    reuseExistingServer: false,
    stderr: "ignore",
    timeout: 30_000,
  },
});
