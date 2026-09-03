import { expect, test } from '@playwright/test';

import { gridCell, openSolver } from './helpers';

test.describe('solver workflow contract', () => {
  test('checking a mistake paints it and editing clears the stale error', async ({ page }) => {
    await openSolver(page);
    const firstCell = gridCell(page, 'real-cell-0-0');

    await firstCell.click();
    await page.keyboard.type('X');
    await page.getByRole('button', { name: 'Check' }).click();
    await expect(firstCell).toHaveClass(/red/);

    await firstCell.click();
    await page.keyboard.type('A');
    await expect(firstCell).toHaveValue('A');
    await expect(firstCell).not.toHaveClass(/red/);
  });

  test('pause blocks input until the session is resumed', async ({ page }) => {
    await openSolver(page);
    const firstCell = gridCell(page, 'real-cell-0-0');

    await firstCell.click();
    await page.getByRole('button', { name: 'Pause' }).click();
    await expect(page.getByRole('button', { name: 'Resume' })).toBeVisible();

    await firstCell.click();
    await page.keyboard.type('A');
    await expect(firstCell).toHaveValue('');

    await page.getByRole('button', { name: 'Resume' }).click();
    await firstCell.click();
    await page.keyboard.type('A');
    await expect(firstCell).toHaveValue('A');
  });

  test('reveal requires confirmation and records assistance', async ({ page }) => {
    await openSolver(page);
    const firstCell = gridCell(page, 'real-cell-0-0');
    page.once('dialog', (dialog) => dialog.accept());

    await page.getByRole('button', { name: 'Reveal' }).click();
    await expect(firstCell).toHaveValue('A');
    await expect(page.locator('.stat-item').filter({ hasText: 'Reveals' }).locator('.stat-value')).toHaveText('1');
  });

  test('initial solving stays local and does not call provider routes', async ({ page }) => {
    const providerRequests: string[] = [];
    page.on('request', (request) => {
      if (/\/(?:crossword_by_date|random_crossword)(?:\?|\/|$)/.test(new URL(request.url()).pathname)) {
        providerRequests.push(request.url());
      }
    });

    await openSolver(page);
    expect(providerRequests).toEqual([]);
  });
});