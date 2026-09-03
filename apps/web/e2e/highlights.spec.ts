import { expect, test } from '@playwright/test';
import { backgroundColor, openSolver } from './helpers';

// Paint-regression guards, now against the ported legacy stylesheet. The
// shipped bug class was "state correct, paint transparent" (an undefined CSS
// variable) — these assertions read the RENDERED result.

test.describe('highlight paint (legacy look)', () => {
  test('the active grid input highlights like the legacy app', async ({ page }) => {
    await openSolver(page);
    await page.locator('#crossword-container input[data-row="0"][data-cell="0"]').click();

    const highlighted = await backgroundColor(page, '.grid-cell.highlighted-cell');
    expect(highlighted).not.toBe('rgba(0, 0, 0, 0)');
    expect(highlighted).not.toBe('transparent');
  });

  test('the active clue row paints the legacy highlight', async ({ page }) => {
    await openSolver(page);
    await page.locator('#crossword-container input[data-row="0"][data-cell="0"]').click();

    const clue = page.locator('#across li.highlighted-clue').first();
    const paint = await clue.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(paint).not.toBe('rgba(0, 0, 0, 0)');
    expect(paint).not.toBe('transparent');
  });

  test('crossing clues tint in the opposite direction family', async ({ page }) => {
    await openSolver(page);
    await page.locator('#crossword-container input[data-row="0"][data-cell="0"]').click();

    const acrossCanvas = await backgroundColor(page, '#app');
    const affected = page.locator('#down li.affected-clue').first();
    const bg = await affected.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(bg).not.toBe('rgba(0, 0, 0, 0)');
    expect(bg).not.toBe(acrossCanvas);
    // legacy affected tint IS flag blue at 20% (rgb(33, 150, 243))
    expect(bg).toContain('33, 150, 243');
  });

  test('down selection switches the grid highlight to blue (data-active-direction)', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openSolver(page);
    await page.locator('#down li').first().click();

    const paint = await page.evaluate(() => ({
      attr: document.body.getAttribute('data-active-direction'),
      bg: (() => {
        const cell = document.querySelector('.grid-cell.highlighted-cell');
        return cell ? getComputedStyle(cell).backgroundColor : null;
      })()
    }));
    expect(paint.attr).toBe('down');
    // body[data-active-direction="down"] paints rgba(33, 150, 243, 0.25)
    expect(paint.bg).toContain('33, 150, 243');
  });

  test('the rotated field marks render at legacy scale', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openSolver(page);

    const mark = await page.locator('.clue-column').first().evaluate((el) => {
      const cs = getComputedStyle(el, '::before');
      return { content: cs.content, fontSize: parseFloat(cs.fontSize), opacity: parseFloat(cs.opacity), color: cs.color };
    });
    // exact-look contract (ADR 0003): the owner tuned these values in the
    // legacy app; the replica must render them byte-identically
    expect(mark.content).toContain('ACROSS');
    expect(mark.fontSize).toBe(240);
    expect(mark.opacity).toBe(0.45);
    expect(mark.color).toBe('rgba(255, 152, 0, 0.75)');
  });

  test('grid inputs keep the legacy cell size', async ({ page }) => {
    await openSolver(page);
    const cellSize = await page
      .locator('.grid-cell input')
      .first()
      .evaluate((el) => {
        const cs = getComputedStyle(el);
        return { w: parseFloat(cs.width), h: parseFloat(cs.height) };
      });
    // var(--cell-size) = 2.5rem at 16px root
    expect(cellSize.w).toBeGreaterThanOrEqual(34);
    expect(cellSize.h).toBeGreaterThanOrEqual(34);
  });
});
