import { defineConfig, devices } from '@playwright/test';

const backendPort = process.env.CROSSWORD_E2E_BACKEND_PORT ?? '5002';
const backendURL = `http://127.0.0.1:${backendPort}`;

// CI builds the frontend in its own step, so building again here only spends
// the server-start budget. Locally there is no such step, so build first.
const serveCommand = 'uv run --no-sync python scripts/ci-server.py';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1, // One disposable backend database; avoid cross-test races.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  outputDir: 'test-results/e2e',
  // `list` names each test as it finishes, so a hung or failed run in the CI log
  // says which test it was; `dot` gave no names at all.
  reporter: [
    [process.env.CI ? 'list' : 'dot'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
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
    command: process.env.CI ? serveCommand : `npm run build && ${serveCommand}`,
    url: `${backendURL}/api/health`,
    reuseExistingServer: false,
    // Cold runners import the Flask app slowly; a 60 s ceiling was being hit.
    timeout: 180_000,
    stdout: 'pipe',
    stderr: 'pipe',
    env: { PYTHONUNBUFFERED: '1', CROSSWORD_E2E_BACKEND_PORT: backendPort },
  },
});
