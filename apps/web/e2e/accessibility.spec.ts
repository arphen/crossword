import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { openSolver } from './helpers';

async function expectNoSeriousA11yViolations(page: Parameters<typeof openSolver>[0]) {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((violation) =>
    violation.impact === 'serious' || violation.impact === 'critical'
  );
  expect(serious, serious.map((violation) => `${violation.id}: ${violation.help}`).join('\n')).toEqual([]);
}

test.describe('accessibility contract', () => {
  test('the interactive solver has no serious or critical violations', async ({ page }) => {
    await page.setViewportSize({ width: 1136, height: 900 });
    await openSolver(page);
    await expectNoSeriousA11yViolations(page);
  });

  test('the forced-colors fixture keeps its semantic structure', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' });
    await page.goto('/harness?fixture=special-cells&mode=forced');
    await page.waitForSelector('#crossword-container input');
    await expectNoSeriousA11yViolations(page);
  });
});