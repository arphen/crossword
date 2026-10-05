// Playwright config for the Afterglow e2e suite.
//
// One project per (viewport x theme), so every journey and every design contract
// is screenshotted in each. A separate project replays the reduced-motion tests.
// Baselines live in __screenshots__/ and are COMMITTED. Generate them in the same
// environment CI uses (Linux), not on a laptop: see guide 17.4.
import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';

const here = fileURLToPath(new URL('.', import.meta.url));
const port = Number(process.env.E2E_PORT ?? 4173);
const baseURL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${port}`;
// Use a system Chromium when Playwright's own build is not installed:
//   CHROME_PATH=/usr/bin/chromium npx playwright test
const executablePath = process.env.CHROME_PATH || undefined;

const desktop = { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } };
const phone = { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 };
const project = (name, base, theme, extra = {}) => ({
  name,
  metadata: { theme },
  grepInvert: /@reduced/,
  use: { ...base, colorScheme: theme, ...extra },
});

export default defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.mjs$/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,          // a stray test.only must fail CI
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [['list'], ['github'], ['html', { open: 'never', outputFolder: 'playwright-report' }]]
    : [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  snapshotPathTemplate: '{testDir}/__screenshots__/{projectName}/{testFilePath}/{arg}{ext}',
  expect: {
    timeout: 10_000,
    // Finite CSS animations are fast-forwarded to their end state; infinite ones are
    // cancelled (and the design probes fail separately if any exist).
    // `threshold` is the per-pixel colour tolerance. Playwright's default (0.2) waves through a
    // visible hue shift: a mutation that recoloured the tiles slipped past it. 0.05 catches it and
    // stays stable across repeated runs in the same environment. `maxDiffPixelRatio` then allows
    // a few anti-aliased pixels, never a recoloured surface.
    toHaveScreenshot: { animations: 'disabled', caret: 'hide', scale: 'css', threshold: 0.05, maxDiffPixelRatio: 0.002 },
  },
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    serviceWorkers: 'block',
    launchOptions: { executablePath },
  },
  projects: [
    project('desktop-dark', desktop, 'dark'),
    project('desktop-light', desktop, 'light'),
    project('phone-dark', phone, 'dark'),
    {
      name: 'reduced-motion',
      metadata: { theme: 'dark' },
      grep: /@reduced/,
      // NOTE: `reducedMotion` is not a top-level `use` option in Playwright 1.55; it is silently
      // ignored. It must go through contextOptions. The D3 test asserts the emulation is on.
      use: { ...desktop, colorScheme: 'dark', contextOptions: { reducedMotion: 'reduce' } },
    },
  ],
  webServer: {
    command: 'node serve.mjs',
    cwd: here,
    url: `${baseURL}/demo.html`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: { E2E_PORT: String(port) },
  },
});
