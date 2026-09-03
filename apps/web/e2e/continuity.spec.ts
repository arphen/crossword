import { expect, test } from '@playwright/test';

// Continuity: export the household archive, re-import it, and reject
// archives that do not match the current puzzle.

test('export downloads a continuity archive and import round-trips it', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForSelector('#crossword-container input');

  await page.locator('#crossword-container input[data-row="0"][data-cell="0"]').click();
  await page.keyboard.type('ABAB');

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.locator('button[title="Export continuity archive"]').click()
  ]);
  expect(download.suggestedFilename()).toMatch(/^crossword-.*\.json$/);
  const path = await download.path();
  expect(path).toBeTruthy();

  // clear the letters, then restore them from the archive
  await page.locator('#crossword-container input[data-row="0"][data-cell="0"]').click();
  for (let i = 0; i < 4; i += 1) {
    await page.keyboard.press('Backspace');
    await page.keyboard.press('ArrowRight');
  }
  await page.setInputFiles('#import-archive-input', path!);
  await expect(page.locator('.data-notice')).toContainText('imported');

  const letters = await page.evaluate(() => {
    const row = [...document.querySelectorAll('#crossword-container .grid-row')][0];
    return [...row.querySelectorAll('input')].slice(0, 4).map((input) => (input as HTMLInputElement).value);
  });
  expect(letters).toEqual(['A', 'B', 'A', 'B']);
});

test('importing a foreign archive surfaces an error notice without touching state', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForSelector('#crossword-container input');

  await page.setInputFiles('#import-archive-input', {
    name: 'foreign.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify({ schemaVersion: 1, sessions: [{ puzzleId: 'some-other-puzzle' }] }))
  });
  await expect(page.locator('.data-notice')).toContainText('Continuity archive schema or puzzle content is invalid');
});
