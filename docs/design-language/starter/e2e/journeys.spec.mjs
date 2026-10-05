// User journeys. EVERY journey in JOURNEYS.md has a test here whose title starts with
// its id, "[J1]", and ends in at least one screenshot. The static audit enforces that.
// Replace these demo journeys with your product's.
import cfg from './design.config.mjs';
import { applyView, expect, expectContracts, settle, test } from './design-helpers.mjs';

const theme = () => test.info().project.metadata.theme ?? 'dark';
const root = (page) => page.locator(cfg.rootSelector);

test.beforeEach(async ({ page }) => {
  await page.goto(cfg.page);
  await applyView(page, cfg, { theme: theme() });
  await cfg.setup?.(page);
});

test('[J1] First view: lanes, ground and tiles at rest', async ({ page }) => {
  await test.step('the page settles with nothing looping', async () => {
    await settle(page);
    await expectContracts(page, cfg, {});
  });
  await test.step('the resting state is captured', async () => {
    await expect(page).toHaveScreenshot('j1-first-view.png');
  });
});

test('[J2] Select a clue: the flame ignites once and settles', async ({ page }) => {
  const row = page.locator('#lane-a > li').nth(2);
  await test.step('click an item', async () => {
    await row.click();
    await expect(row).toHaveClass(/is-selected/);
    await expect(root(page)).toHaveAttribute('data-direction', 'across');
  });
  await test.step('the glow flare returns to rest (--glow-pulse is 1)', async () => {
    await settle(page);
    const pulse = await row.locator('.chip').evaluate((el) => getComputedStyle(el).getPropertyValue('--glow-pulse').trim());
    expect(pulse).toBe('1');
  });
  await test.step('only one item in the lane is selected, and contracts hold', async () => {
    await expect(page.locator('#lane-a > li.is-selected')).toHaveCount(1);
    await expectContracts(page, cfg, {});
    await expect(page).toHaveScreenshot('j2-selected.png');
  });
});

test('[J3] Dim the screen from the View panel: bloom drops and the choice persists', async ({ page }) => {
  await test.step('open the panel and choose Dim', async () => {
    await page.locator('.view-cluster-summary').click();
    await page.locator('.view-choice[data-key="luma"][data-value="dim"]').click();
    await expect(root(page)).toHaveAttribute(cfg.attrs.luma, 'dim');
    await settle(page);
    await expectContracts(page, cfg, { luma: 'dim' });
    await expect(page).toHaveScreenshot('j3-panel-dim.png');
  });
  await test.step('the choice survives a reload (stored beats the default)', async () => {
    await page.reload();
    await expect(root(page)).toHaveAttribute(cfg.attrs.luma, 'dim');
  });
});

test('[J4] Reset restores the defaults', async ({ page }) => {
  await page.locator('.view-cluster-summary').click();
  await page.locator('.view-choice[data-key="luma"][data-value="veil"]').click();
  await expect(root(page)).toHaveAttribute(cfg.attrs.luma, 'veil');
  await page.locator('.view-reset').click();
  await expect(root(page)).toHaveAttribute(cfg.attrs.luma, 'standard');
  await settle(page);
  await expect(page).toHaveScreenshot('j4-reset.png');
});

test('[J5] Scrolling a lane moves the territory light', async ({ page }) => {
  const ground = page.locator('#ground');
  const before = await ground.evaluate((el) => el.style.getPropertyValue('--ta-top'));
  await page.locator('#lane-a').evaluate((el) => { el.scrollTop = el.scrollHeight; });
  await expect.poll(() => ground.evaluate((el) => el.style.getPropertyValue('--ta-top'))).not.toBe(before);
  await settle(page);
  await expect(page).toHaveScreenshot('j5-scrolled.png');
});
