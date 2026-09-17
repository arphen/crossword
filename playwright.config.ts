import { defineConfig, devices } from '@playwright/test';

const backendPort = process.env.CROSSWORD_E2E_BACKEND_PORT ?? '5002';
const backendURL = `http://127.0.0.1:${backendPort}`;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1, // One disposable backend database; avoid cross-test races.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  outputDir: 'test-results/e2e',
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: backendURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    serviceWorkers: 'block',
  },
  projects: [{ name: 'desktop-chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } }],
  webServer: {
    // Exercise the same built React + Flask routes as make run, with an
    // isolated database and synthetic puzzles instead of private providers.
    command: 'npm run build && npm --workspace @crossword/react-port run build && uv run --no-sync python scripts/ci-server.py',
    url: `${backendURL}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: 'pipe',
    stderr: 'pipe',
    env: { PYTHONUNBUFFERED: '1', CROSSWORD_E2E_BACKEND_PORT: backendPort },
  },
});
