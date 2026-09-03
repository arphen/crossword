import { expect, test, type Page } from '@playwright/test';

// The two blind spots that shipped real bugs: DOM state without paint, and
// paint without geometry. These helpers reason about the RENDERED result.

export async function backgroundColor(page: Page, selector: string): Promise<string> {
  return page.locator(selector).first().evaluate((el) => getComputedStyle(el).backgroundColor);
}

export function gridCell(page: Page, cellId: string) {
  return page.locator(`#crossword-container input[data-cell-id="${cellId}"]`);
}

export async function openSolver(page: Page) {
  await page.goto('/');
  await page.waitForSelector('#crossword-container input');
  await page.waitForTimeout(250);
}
