import { expect, test } from '@playwright/test';
import { gridCell, openSolver } from './helpers';

// The household play loop on the ported legacy grid: real inputs, legacy
// key semantics (arrows switch direction at their family edge), and zero
// repeated cell numbers.

test.describe('play journeys (legacy replica)', () => {
  test('typing lands letters in the grid inputs at the owner window size', async ({ page }) => {
    await page.setViewportSize({ width: 1136, height: 900 });
    await openSolver(page);

    await gridCell(page, 'real-cell-0-0').click();
    await page.keyboard.type('ABAB', { delay: 40 });

    const letters = await page.evaluate(() => {
      const row = [...document.querySelectorAll('#crossword-container .grid-row')][0];
      return [...row.querySelectorAll('input')]
        .slice(0, 4)
        .map((input) => (input as HTMLInputElement).value);
    });
    expect(letters).toEqual(['A', 'B', 'A', 'B']);
  });

  test('arrows move within the direction and switch direction at the family edge', async ({ page }) => {
    await page.setViewportSize({ width: 1136, height: 900 });
    await openSolver(page);

    await gridCell(page, 'real-cell-0-0').click();
    await page.keyboard.press('ArrowRight');
    await expect(gridCell(page, 'real-cell-0-1')).toBeFocused();

    // moving down from an across selection switches to Down, staying put
    await page.keyboard.press('ArrowDown');
    await expect(gridCell(page, 'real-cell-0-1')).toBeFocused();

    // now Down is active: ArrowDown moves down the column
    await page.keyboard.press('ArrowDown');
    await expect(gridCell(page, 'real-cell-1-1')).toBeFocused();
  });

  test('clicking a clue-spine answer cell focuses the grid input', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openSolver(page);

    await page.locator('#across .state').first().click();
    await page.keyboard.type('A');

    // the letter lands in the grid input; selection advances within the entry
    await expect(gridCell(page, 'real-cell-0-0')).toHaveValue('A');
    await expect(gridCell(page, 'real-cell-0-1')).toBeFocused();
  });

  test('grid cell numbers never repeat the same figure (no 17/17)', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openSolver(page);

    const duplicates = await page.evaluate(() =>
      [...document.querySelectorAll('.clue-index')].filter((el) => {
        const match = /^(\d+)\/\1$/.exec(el.textContent?.trim() ?? '');
        return match !== null;
      }).length
    );
    expect(duplicates).toBe(0);
  });

  test('dialogs are semantically modal: escape closes, close is labelled', async ({ page }) => {
    await page.setViewportSize({ width: 1136, height: 900 });
    await openSolver(page);

    await page.locator('#complete-button').click();
    const dialog = page.locator('.modal-content[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute('aria-modal', 'true');
    await expect(page.locator('#solved-modal-title')).toBeVisible();
    await expect(page.locator('.modal-content[role="dialog"] .modal-close-button')).toBeFocused();

    await page.keyboard.press('Escape');
    await expect(page.locator('.modal-content[role="dialog"]')).toHaveCount(0);
  });

  test('night mode toggle flips the color scheme and persists across reload', async ({ page }) => {
    await page.setViewportSize({ width: 1136, height: 900 });
    await openSolver(page);

    await page.locator('.theme-switch input').evaluate((el) => (el as HTMLInputElement).click());
    await expect(page.locator('html')).toHaveCSS('color-scheme', 'dark');

    await page.reload();
    await page.waitForSelector('#crossword-container');
    await expect(page.locator('html')).toHaveCSS('color-scheme', 'dark');

    await page.locator('.theme-switch input').evaluate((el) => (el as HTMLInputElement).click());
    await expect(page.locator('html')).toHaveCSS('color-scheme', 'light');
  });
});
