import { expect, test } from '@playwright/test';

// The full loop: fill every white cell from its solution, the domain marks
// the session complete, and the solved modal opens (legacy behavior).

test('completing the grid opens the solved modal and records the solve', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForSelector('#crossword-container input');

  const inputs = page.locator('#crossword-container input');
  const count = await inputs.count();
  expect(count).toBeGreaterThan(100);

  for (let i = 0; i < count; i += 1) {
    const input = inputs.nth(i);
    const solution = (await input.getAttribute('data-solution')) ?? '';
    if (!solution) continue;
    if ((await input.inputValue()) === solution) continue;
    await input.click();
    await page.keyboard.type(solution, { delay: 10 });
  }

  await expect(page.locator('.modal-overlay')).toBeVisible();
  await expect(page.locator('.modal-content')).toContainText('complete in');

  // completion is recorded for the overview list
  await page.locator('.modal-close-button').click();
  await page.locator('.icon-button[title="Solved puzzles"]').click();
  await expect(page.locator('.solved-puzzles-list')).toBeVisible();
});
