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
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    serviceWorkers: 'block',
  },
  projects: [{ name: 'desktop-chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } }],
  webServer: [
    {
      command: 'uv run --no-sync python scripts/ci-server.py',
      url: `${backendURL}/api/health`,
      reuseExistingServer: false,
      timeout: 30_000,
      stdout: 'pipe',
      stderr: 'pipe',
      env: { PYTHONUNBUFFERED: '1' },
    },
    {
      // Build the actual React port first: preview never builds implicitly.
      command: 'npm --workspace @crossword/react-port run build && npm --workspace @crossword/react-port exec -- vite preview --host 127.0.0.1 --port 4173 --strictPort',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: 'pipe',
      stderr: 'pipe',
      env: { CROSSWORD_BACKEND: backendURL },
    },
  ],
});
