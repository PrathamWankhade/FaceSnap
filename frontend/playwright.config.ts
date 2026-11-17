import { defineConfig, devices } from '@playwright/test';

/**
 * FaceSnap E2E configuration.
 *
 * `npm run test:e2e` starts the Next.js dev server on port 3001 itself. The
 * unauthenticated specs in `e2e/` do not need the backend; specs that do would
 * need it started separately (see docs/testing.md).
 *
 * Override the target with `PLAYWRIGHT_BASE_URL` when testing a deployed build.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3001',
    trace: 'on-first-retry',
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: 'npm run dev -- -p 3001',
        url: 'http://localhost:3001',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
  projects: [
    {
      name: 'chromium',
      use: devices['Desktop Chrome'],
    },
  ],
});
