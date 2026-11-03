import { defineConfig, devices } from '@playwright/test';

/**
 * FaceSnap E2E configuration.
 *
 * Runs against `http://localhost:3001` by default. Start the dev servers first:
 *
 *   Terminal 1: cd backend && uvicorn app.main:app --reload --port 8002
 *   Terminal 2: cd frontend && npm run dev -- -p 3001
 *
 * Then:  npx playwright test
 *
 * CI can use the `webServer` option instead (uncomment) to spin the dev server
 * itself; that requires the frontend dev command and a running backend.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  // webServer: {
  //   command: 'npm run dev -- -p 3001',
  //   url: 'http://localhost:3001',
  //   reuseExistingServer: !process.env.CI,
  //   workingDirectory: './frontend',
  // },
  projects: [
    {
      name: 'chromium',
      use: devices['Desktop Chrome'],
    },
  ],
});
