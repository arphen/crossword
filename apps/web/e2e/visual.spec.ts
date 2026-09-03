import { expect, test } from '@playwright/test';
import { openSolver } from './helpers';

// Visual baselines for the owner to eyeball. The stats row (time) is masked:
// it is the one deliberately dynamic surface.

async function shot(page: import('@playwright/test').Page, name: string) {
  await expect(page).toHaveScreenshot(name, {
    animations: 'disabled',
    fullPage: false,
    mask: [page.locator('.indicator-bar'), page.locator('.data-notice')]
  });
}

// Baselines are captured on darwin; cross-platform font rendering differs,
// so visual comparison stays local and CI runs journeys + paint guards.
test.skip(Boolean(process.env.CI), 'visual baselines are darwin-local');

test.describe('visual baselines (legacy replica)', () => {
  test('panorama 1440 with a typed entry', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openSolver(page);
    await page.locator('#crossword-container input[data-row="0"][data-cell="0"]').click();
    await page.keyboard.type('ABAB', { delay: 30 });
    await page.waitForTimeout(200);
    await shot(page, 'panorama-1440.png');
  });

  test('standard 1136 stacked mode', async ({ page }) => {
    await page.setViewportSize({ width: 1136, height: 900 });
    await openSolver(page);
    await page.locator('#crossword-container input[data-row="0"][data-cell="0"]').click();
    await page.waitForTimeout(200);
    await shot(page, 'standard-1136.png');
  });

  test('night mode', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openSolver(page);
    await page.locator('.theme-switch input').evaluate((el) => (el as HTMLInputElement).click());
    await page.waitForTimeout(200);
    await shot(page, 'panorama-1440-night.png');
  });

  test('harness half-collapsed fixture', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/harness?fixture=half-collapsed');
    await page.waitForSelector('#crossword-container');
    await page.waitForTimeout(250);
    await shot(page, 'harness-half-collapsed.png');
  });
});
