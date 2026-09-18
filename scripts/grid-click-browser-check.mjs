import { chromium } from 'playwright';
import { readFileSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import assert from 'node:assert/strict';
const fixture = JSON.parse(readFileSync(new URL('../reports/react-parity/fixture.json', import.meta.url), 'utf8'));
const out = new URL('../reports/grid-click/', import.meta.url);
mkdirSync(out, { recursive: true });
// Playwright's bundled Chromium is the default; CHROME_BIN or a standard
// Chrome/Chromium location wins, matching the other browser harnesses.
const chromeBin = process.env.CHROME_BIN ?? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/chromium', '/usr/bin/google-chrome'].find(existsSync);
const browser = await chromium.launch({ ...(chromeBin ? { executablePath: chromeBin } : {}), headless: true });
const report = {};
try {
  for (const [name, url] of Object.entries({ vue: process.env.VUE_PARITY_URL ?? 'http://127.0.0.1:5001/legacy/', react: process.env.REACT_PARITY_URL ?? 'http://127.0.0.1:5001/' })) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
    await context.addInitScript(() => { localStorage.setItem('lastCachingTime', String(Date.now())); window.setInterval = () => 1; });
    await context.route('**/*', route => {
      const u = new URL(route.request().url());
      if (u.origin !== new URL(url).origin || u.pathname.startsWith('/socket.io')) return route.abort();
      if (u.pathname.startsWith('/random_crossword/')) return route.fulfill({ json: fixture });
      if (u.pathname.startsWith('/api/completed_puzzles')) return route.fulfill({ json: { completed: false } });
      return route.continue();
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(url);
    const input = page.locator('input[data-row="2"][data-cell="1"]');
    await input.click();
    async function snapshot() {
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      return page.evaluate(() => ({
        active: [...document.querySelectorAll('.highlighted-clue')].map(el => `${el.closest('ul').id}:${el.querySelector('.clue-number').textContent.trim()}`),
        affected: [...document.querySelectorAll('.affected-clue')].map(el => `${el.closest('ul').id}:${el.querySelector('.clue-number').textContent.trim()}`),
        cells: [...document.querySelectorAll('.grid-cell.highlighted-cell input')].map(el => `${el.dataset.row},${el.dataset.cell}`),
        focus: document.activeElement.getAttribute('aria-label'), direction: document.body.dataset.activeDirection
      }));
    }
    const across = await snapshot();
    assert.deepEqual(across.active, ['across:17.']);
    assert.deepEqual(across.cells, Array.from({ length: 7 }, (_, col) => `2,${col}`));
    assert.equal(across.focus, 'grid cell 2-1');
    assert.ok(across.affected.includes('down:2.'));
    // Arrow switches input direction; clicking the SAME focused cell must
    // update selection too (an onFocus-only binding would miss this).
    await page.keyboard.press('ArrowDown');
    await input.click();
    const down = await snapshot();
    assert.deepEqual(down.active, ['down:2.']);
    assert.deepEqual(down.cells, ['0,1', '1,1', '2,1']);
    assert.equal(down.focus, 'grid cell 2-1');
    assert.ok(down.affected.includes('across:17.'));
    assert.equal(down.direction, 'down');
    // Arrow-driven selection: parallel move, then perpendicular switch, must
    // keep active clue/highlight/crossings in sync with the focused cell.
    const arrowSteps = [];
    const arrowSnapshot = async label => {
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      // Check settled colors with real transitions enabled, rather than sampling
      // only two frames into the stylesheet's 0.4–0.6 second transition.
      await page.waitForFunction(() => [...document.querySelectorAll('.clue-column')].every(el => {
        const style = getComputedStyle(el, '::before');
        if (el.classList.contains('active')) {
          return style.opacity === '0.45' && style.color === (el.dataset.label === 'ACROSS'
            ? 'rgba(255, 152, 0, 0.75)' : 'rgba(33, 150, 243, 0.75)');
        }
        return style.color === 'rgb(0, 0, 0)' && style.opacity === '0.3';
      }), null, { timeout: 5000 });
      arrowSteps.push({ label, ...(await page.evaluate(() => ({
        active: [...document.querySelectorAll('.highlighted-clue')].map(el => `${el.closest('ul').id}:${el.querySelector('.clue-number').textContent.trim()}`),
        cells: [...document.querySelectorAll('.grid-cell.highlighted-cell input')].map(el => `${el.dataset.row},${el.dataset.cell}`),
        focus: document.activeElement.getAttribute('aria-label'),
        direction: document.body.dataset.activeDirection ?? null,
        watermarkColors: Object.fromEntries([...document.querySelectorAll('.clue-column')].map(el => [el.dataset.label, { color: getComputedStyle(el, '::before').color, opacity: getComputedStyle(el, '::before').opacity }])),
        helperCellColor: (() => { const cell = document.querySelector('.grid-cell.highlighted-cell'); return cell ? getComputedStyle(cell, '::before').borderColor : null; })(),
      }))) });
    };
    await page.keyboard.press('ArrowRight');   // switch from down to across, without moving
    await arrowSnapshot('after perpendicular ArrowRight');
    await page.keyboard.press('ArrowDown');    // perpendicular switch to down
    await arrowSnapshot('after perpendicular ArrowDown');
    await page.keyboard.press('ArrowUp');      // moves within down word
    await arrowSnapshot('after ArrowUp within down');
    assert.deepEqual(arrowSteps[0].active, ['across:17.']);
    assert.deepEqual(arrowSteps[1].active, ['down:2.']);
    assert.deepEqual(arrowSteps[2].active, ['down:2.']);
    for (const step of arrowSteps) {
      assert.ok(step.active.length === 1, `no active clue after ${step.label}`);
      assert.ok(step.cells.length > 0, `no highlighted cells after ${step.label}`);
    }
    const { ACROSS: wmAcross2, DOWN: wmDown2 } = arrowSteps[1].watermarkColors;
    assert.match(wmDown2.color, /33, 150, 243/, 'active down watermark not blue');
    assert.match(wmAcross2.color, /^rgb\(0, 0, 0\)$/, 'inactive across watermark not grayed text color');
    assert.equal(wmAcross2.opacity, '0.3', 'inactive across watermark opacity not 0.3');
    // Helper-cell highlight border must match the active direction's color.
    assert.match(arrowSteps[0].helperCellColor, /255, 152, 0/, 'across helper-cell highlight not orange');
    assert.match(arrowSteps[1].helperCellColor, /33, 150, 243/, 'down helper-cell highlight not blue');
    const { ACROSS: wmAcross, DOWN: wmDown } = arrowSteps[0].watermarkColors;
    assert.match(wmAcross.color, /255, 152, 0/, 'active across watermark not orange');
    assert.match(wmDown.color, /^rgb\(0, 0, 0\)$/, 'inactive down watermark not grayed text color');
    assert.equal(wmDown.opacity, '0.3', 'inactive down watermark opacity not 0.3');
    // Cross the black square below Down 1: selection must follow focus into
    // the next word, not be overwritten by the keydown's source coordinates.
    await page.locator('#down .clue-text').first().click();
    for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowDown');
    const boundary = await snapshot();
    const destination = fixture.entries.find(e => e.direction === 'down' && e.start_x === 0 && e.start_y === 4);
    assert.ok(destination, 'fixture must contain a down word at (4,0)');
    assert.equal(boundary.focus, 'grid cell 4-0');
    assert.deepEqual(boundary.active, [`down:${destination.clue_number}.`]);
    assert.deepEqual(boundary.cells, destination.characters.map((_, i) => `${4 + i},0`));
    assert.deepEqual(errors, []);
    await page.screenshot({ path: new URL(`${name}-down.png`, out).pathname, animations: 'disabled' });
    report[name] = { across, down, arrowSteps, boundary };
    await context.close();
  }
  assert.deepEqual(report.react, report.vue);
  report.passed = true;
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
  writeFileSync(new URL('results.json', out), JSON.stringify(report, null, 2));
}
