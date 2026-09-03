import { expect, test } from '@playwright/test';
import { gridCell, openSolver } from './helpers';

// Geometry assertions per the review release matrix: compositions must
// fit their viewports and keep the grid primary — screenshots alone
// cannot prove this.

test('panorama keeps three columns beside the grid at 1440', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openSolver(page);
  const geo = await page.evaluate(() => {
    const box = (sel: string) => {
      const el = document.querySelector(sel);
      const r = el?.getBoundingClientRect();
      return r ? { x: Math.round(r.x), w: Math.round(r.width) } : null;
    };
    return {
      across: box('.clue-column'),
      grid: box('#crossword-container'),
      down: box('.clue-column[data-label="DOWN"]')
    };
  });
  expect(geo.across?.x).toBeLessThan(geo.grid!.x);
  expect(geo.grid!.x).toBeLessThan(geo.down!.x);
  expect(geo.grid!.w).toBeGreaterThanOrEqual(480);
});

test('compact desktop stacks with the grid first at 1136', async ({ page }) => {
  await page.setViewportSize({ width: 1136, height: 900 });
  await openSolver(page);
  const geo = await page.evaluate(() => {
    const box = (sel: string) => {
      const el = document.querySelector(sel);
      const r = el?.getBoundingClientRect();
      return r ? { y: Math.round(r.y), w: Math.round(r.width), right: Math.round(r.right) } : null;
    };
    return {
      grid: box('#crossword-container'),
      across: box('.clue-column'),
      viewport: 1136
    };
  });
  // grid above the clue field, grid first in reading order
  expect(geo.grid!.y).toBeLessThan(geo.across!.y);
  // clue lane is wide enough for readable clue lines (not squeezed halves)
  expect(geo.across!.w).toBeGreaterThanOrEqual(700);
  // nothing hangs outside the viewport
  expect(geo.across!.right).toBeLessThanOrEqual(geo.viewport);
});

test('mobile portrait fits the grid and avoids horizontal scroll at 390', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.waitForSelector('#crossword-container input');
  const geo = await page.evaluate(() => {
    const grid = document.querySelector('.grid')?.getBoundingClientRect();
    return {
      gridWidth: Math.round(grid?.width ?? 0),
      scrollWidth: document.documentElement.scrollWidth,
      viewport: 390
    };
  });
  expect(geo.gridWidth).toBeLessThanOrEqual(390);
  expect(geo.scrollWidth).toBeLessThanOrEqual(geo.viewport);
});

test('inputs accept fill (paste/IME path), not only physical keydown', async ({ page }) => {
  await page.setViewportSize({ width: 1136, height: 900 });
  await openSolver(page);
  await gridCell(page, 'real-cell-0-0').fill('A');
  await expect(gridCell(page, 'real-cell-0-0')).toHaveValue('A');
});
