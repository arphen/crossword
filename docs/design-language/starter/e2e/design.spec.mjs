// Design contracts: the measurable half of the guide, checked in every project
// (viewport x theme) and across the mini/micro view tiers, each with a screenshot.
import cfg from './design.config.mjs';
import { applyView, expect, expectContracts, expectFocusRing, settle, test } from './design-helpers.mjs';

const theme = () => test.info().project.metadata.theme ?? 'dark';

test.describe('design contracts', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(cfg.page);
    await cfg.setup?.(page);
  });

  for (const luma of cfg.lumas) {
    for (const vibrance of cfg.vibrances) {
      test(`[D1] view matrix: ${luma} / ${vibrance}`, async ({ page }) => {
        await applyView(page, cfg, { theme: theme(), luma, vibrance });
        await settle(page);
        await expectContracts(page, cfg, { luma });
        await expect(page).toHaveScreenshot(`view-${luma}-${vibrance}.png`);
      });
    }
  }

  test('[D2] keyboard focus is visible', async ({ page }) => {
    await settle(page);
    await expectFocusRing(page);
  });

  // Runs only in the reduced-motion project (see playwright.config.mjs).
  test('[D3] reduced motion removes motion and keeps light', { tag: '@reduced' }, async ({ page }) => {
    const emulated = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
    expect(emulated, 'prefers-reduced-motion must be emulated, or this test proves nothing').toBe(true);
    await applyView(page, cfg, { theme: 'dark', luma: 'standard', vibrance: 'vivid' });
    await page.locator('.lane > li').nth(2).click();
    await page.waitForTimeout(400);
    await expectContracts(page, cfg, { luma: 'standard', reduced: true });
    // The light stays: the selected chip still carries its flame.
    const shadow = await page.locator('li.is-selected > .chip').first().evaluate((el) => getComputedStyle(el).boxShadow);
    expect(shadow, 'the selection keeps its glow when motion is off').not.toBe('none');
    await expect(page).toHaveScreenshot('reduced-motion-selected.png');
  });
});
