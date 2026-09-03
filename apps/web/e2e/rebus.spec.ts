import { expect, test } from '@playwright/test';

// Rebus parity: right-clicking a rebus cell accepts a multi-letter token,
// stored in the session and shown in the input.

test('rebus cell accepts a multi-letter token via context menu', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/harness?fixture=rebus');
  await page.waitForSelector('#crossword-container input');

  page.on('dialog', (dialog) => dialog.accept('AN'));
  await page.locator('#crossword-container input[data-cell-id="cell-0-0"]').click({ button: 'right' });

  const input = page.locator('#crossword-container input[data-cell-id="cell-0-0"]');
  await expect(input).toHaveValue('AN');
});

test('context menu on non-rebus cells keeps the browser default', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/harness?fixture=rebus');
  await page.waitForSelector('#crossword-container input');

  const native = await page.evaluate(() => {
    const input = document.querySelector<HTMLInputElement>('#crossword-container input[data-cell-id="cell-1-1"]');
    if (!input) return 'missing';
    const event = new MouseEvent('contextmenu', { bubbles: true, cancelable: true });
    input.dispatchEvent(event);
    return event.defaultPrevented ? 'prevented' : 'default';
  });
  expect(native).toBe('default');
});
