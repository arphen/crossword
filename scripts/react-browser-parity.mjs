// Compare the real Vue/React pages with identical provider-neutral data.
// Requires Flask at VUE_PARITY_URL and Vite at REACT_PARITY_URL.
import { chromium } from 'playwright';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import assert from 'node:assert/strict';

const movementTrace = process.env.PARITY_TRACE === 'movement';
const expectedCheckpoints = movementTrace ? 11 : 15;
const output = new URL(movementTrace ? '../reports/react-movement-parity/' : '../reports/react-parity/', import.meta.url);
mkdirSync(output, { recursive: true });
const urls = { vue: process.env.VUE_PARITY_URL ?? 'http://127.0.0.1:5001/', react: process.env.REACT_PARITY_URL ?? 'http://127.0.0.1:5174/' };
// Rotationally symmetric 15x15 synthetic grid; no published puzzle content.
const rows = ['...#.......#...', '...#.......#...', '.......#.......', '##...#...#...##', '.....#...#.....', '...#.......#...', '.....#...#.....', '##...#...#...##', '.....#...#.....', '...#.......#...', '.....#...#.....', '##...#...#...##', '.......#.......', '...#.......#...', '...#.......#...'];
const entries = [];
let number = 0;
const character = (x, y) => ({ letters: x === 4 && y === 0 ? 'QU' : 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[(y * 15 + x) % 26], is_circled: x === 1 && y === 0, is_shaded: x === 2 && y === 0 });
for (let y = 0; y < 15; y++) for (let x = 0; x < 15; x++) {
  if (rows[y][x] === '#') continue;
  const across = x === 0 || rows[y][x - 1] === '#';
  const down = y === 0 || rows[y - 1][x] === '#';
  if (!across && !down) continue;
  number++;
  for (const direction of ['across', 'down']) {
    if (!(direction === 'across' ? across : down)) continue;
    const characters = [];
    for (let i = 0; ; i++) {
      const cx = x + (direction === 'across' ? i : 0), cy = y + (direction === 'down' ? i : 0);
      if (cy >= 15 || cx >= 15 || rows[cy][cx] === '#') break;
      characters.push(character(cx, cy));
    }
    entries.push({ clue_number: number, clue_text: `Synthetic ${direction} clue ${number}: ${number % 3 ? 'a short test entry' : 'a longer clue to exercise wrapping and alignment'}`, direction, start_x: x, start_y: y, characters });
  }
}
const fixture = { metadata: { date: '260829', title: 'Synthetic parity board', authors: ['Parity Fixture Author'], width: 15, height: 15, notepad: 'Synthetic fixture: circled, shaded and rebus cells.' }, entries };
writeFileSync(new URL('fixture.json', output), JSON.stringify(fixture, null, 2));
const executablePath = process.env.CHROME_BIN ?? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/chromium'].find(existsSync);
const browser = await chromium.launch({ ...(executablePath ? { executablePath } : {}), headless: true });
const report = { browser: browser.version(), urls, viewport: { width: 1440, height: 1000 }, fixture: 'fixture.json', normalization: 'Fresh contexts, en-US/UTC, fixed Date and paused interval timers; screenshots disable CSS animations and hide caret. HTTP fixture routes intercepted; sockets blocked. DOM normalizes whitespace/class order, omits Vue comments and React wrapper. Pass criterion: DOM equality plus <0.1% differing pixels; Residual pixel differences remain unresolved; measured text boxes include small x-position/width deltas (see main-board-geometry.json). This tolerance is a bounded visual check, not proof of exact parity or of the residual cause.', states: [], errors: [] };
const pages = {};
const captures = {};
try {
  for (const [name, url] of Object.entries(urls)) {
    const context = await browser.newContext({ viewport: report.viewport, deviceScaleFactor: 1, colorScheme: 'light', locale: 'en-US', timezoneId: 'UTC' });
    await context.addInitScript(() => {
      const NativeDate = Date;
      window.Date = class extends NativeDate { constructor(...args) { super(...(args.length ? args : [1790000000000])); } static now() { return 1790000000000; } };
      // Interval callbacks (scoreboard timer and socket polling) aren't under test here.
      window.setInterval = () => 1;
      localStorage.clear();
      localStorage.setItem('lastCachingTime', String(Date.now()));
    });
    await context.route('**/*', async route => {
      const request = route.request(), u = new URL(request.url());
      if (u.origin !== new URL(url).origin) return route.abort();
      if (u.pathname.startsWith('/socket.io')) return route.abort();
      if (u.pathname.startsWith('/random_crossword/')) return route.fulfill({ json: fixture });
      if (u.pathname.startsWith('/api/completed_puzzles')) return route.fulfill({ json: u.pathname === '/api/completed_puzzles' ? [] : { completed: false } });
      if (u.pathname.startsWith('/api/')) return route.abort();
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => report.errors.push({ app: name, message: error.message }));
    page.on('dialog', dialog => dialog.dismiss());
    await page.goto(url);
    await page.waitForFunction(() => document.querySelectorAll('.grid-cell').length === 225);
    await page.evaluate(() => document.fonts.ready);
    pages[name] = page;
  }
  async function snapshot(page) {
    return page.evaluate(() => {
      const normalize = value => value.replace(/\s+/g, ' ').trim();
      const walk = element => ({ tag: element.tagName, classes: [...new Set(element.classList)].sort(), text: normalize([...element.childNodes].filter(n => n.nodeType === Node.TEXT_NODE).map(n => n.textContent).join('')), ...(element.matches('input,select') ? { value: element.value, checked: element.checked ?? false } : {}), attrs: Object.fromEntries(['id', 'data-row', 'data-cell', 'data-solution', 'maxlength', 'aria-label', 'href', 'title'].filter(key => element.hasAttribute(key)).map(key => [key, element.getAttribute(key)])), children: [...element.children].map(walk) });
      return { tree: walk(document.querySelector('#app')), focus: document.activeElement.getAttribute('aria-label'), direction: document.body.getAttribute('data-active-direction'), scheme: document.documentElement.style.getPropertyValue('color-scheme') };
    });
  }
  async function checkpoint(id, action, verify) {
    const values = {};
    for (const [name, page] of Object.entries(pages)) {
      if (action) await action(page);
      // Wait for React/Vue commits and focus callbacks, without a timing sleep.
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      if (verify) await verify(page);
      values[name] = await snapshot(page);
      captures[name] = await page.screenshot({ path: new URL(`${id}-${name}.png`, output).pathname, animations: 'disabled', caret: 'hide' });
    }
    if (id === '01-main-board') {
      const geometry = {};
      for (const [name, page] of Object.entries(pages)) geometry[name] = await page.locator('.info-bar span, .clue-text').evaluateAll(elements => elements.map(el => { const r = el.getBoundingClientRect(); return { text: el.textContent, x: r.x, y: r.y, width: r.width, height: r.height }; }));
      writeFileSync(new URL('main-board-geometry.json', output), JSON.stringify(geometry, null, 2));
    }
    const a = PNG.sync.read(captures.vue), b = PNG.sync.read(captures.react), diff = new PNG({ width: a.width, height: a.height });
    const pixels = pixelmatch(a.data, b.data, diff.data, a.width, a.height, { threshold: 0.1 });
    writeFileSync(new URL(`${id}-diff.png`, output), PNG.sync.write(diff));
    writeFileSync(new URL(`${id}-dom.json`, output), JSON.stringify(values, null, 2));
    let domEqual = true;
    try { assert.deepEqual(values.react, values.vue); } catch (error) {
      domEqual = false;
      console.error(`${id}: ${error.message}`);
    }
    report.states.push({ id, domEqual, differentPixels: pixels, totalPixels: a.width * a.height, ratio: pixels / (a.width * a.height) });
    console.log(`${id}: DOM ${domEqual ? 'equal' : 'DIFF'}, screenshot ${pixels} different pixels`);
  }
  const cell = (page, row, col) => page.locator(`input[data-row="${row}"][data-cell="${col}"]`);
  if (movementTrace) {
    const focusIs = async (page, row, col) => assert.equal(await cell(page, row, col).evaluate(el => el === document.activeElement), true);
    const steps = [
      ['m01-select-across', page => page.locator('#across .clue-text').first().click(), 0, 0],
      ['m02-perpendicular-down', page => page.keyboard.press('ArrowDown'), 0, 0],
      ['m03-repeat-down', page => page.keyboard.press('ArrowDown'), 1, 0],
      ['m04-down-end', page => page.keyboard.press('ArrowDown'), 2, 0],
      ['m05-skip-black-down', page => page.keyboard.press('ArrowDown'), 4, 0],
      ['m06-backspace-skip-black', async page => { await page.keyboard.press('Q'); await page.keyboard.press('Backspace'); }, 4, 0],
      ['m07-clear-occupied-and-back', page => page.keyboard.press('Backspace'), 2, 0],
      ['m08-perpendicular-right', page => page.keyboard.press('ArrowRight'), 2, 0],
      ['m09-repeat-right', page => page.keyboard.press('ArrowRight'), 2, 1],
      ['m10-left', page => page.keyboard.press('ArrowLeft'), 2, 0],
      ['m11-left-boundary', page => page.keyboard.press('ArrowLeft'), 2, 0],
    ];
    for (const [id, action, row, col] of steps) await checkpoint(id, action, async page => {
      await focusIs(page, row, col);
      assert.equal(await page.locator('#across .highlighted-clue .clue-number').textContent(), '1.');
      assert.equal(await page.evaluate(() => document.body.dataset.activeDirection), 'across');
      assert.deepEqual(await page.locator('.grid-cell.highlighted-cell input').evaluateAll(inputs => inputs.map(el => [Number(el.dataset.row), Number(el.dataset.cell)])), [[0, 0], [0, 1], [0, 2]]);
      if (id === 'm07-clear-occupied-and-back') assert.equal(await cell(page, 4, 0).inputValue(), '');
    });
  } else {
  await checkpoint('01-main-board', null, async page => {
    assert.equal(await page.locator('.grid-cell').count(), 225);
    assert.equal(await page.locator('.rebus-indicator').count(), 1);
    assert.equal(await page.locator('#across li').count(), entries.filter(e => e.direction === 'across').length);
    assert.equal(await page.locator('#down li').count(), entries.filter(e => e.direction === 'down').length);
  });
  await checkpoint('02-clue-focus', page => page.locator('#across .clue-text').first().click(), async page => {
    assert.equal(await cell(page, 0, 0).evaluate(el => el === document.activeElement), true);
    assert.equal(await page.locator('#across .highlighted-clue').count(), 1);
    assert.equal(await page.locator('.clue-column.active').getAttribute('data-label'), 'ACROSS');
  });
  await checkpoint('03-input', async page => { await page.keyboard.press('A'); await page.keyboard.press('X'); }, async page => {
    assert.equal(await cell(page, 0, 0).inputValue(), 'A');
    assert.equal(await cell(page, 0, 1).inputValue(), 'X');
    assert.equal(await cell(page, 0, 2).evaluate(el => el === document.activeElement), true);
  });
  await checkpoint('04-check', page => page.locator('#check-all').click(), async page => {
    assert.match(await cell(page, 0, 1).getAttribute('class'), /red/);
    assert.equal(await page.locator('.stat-value').nth(3).textContent(), '90');
  });
  await checkpoint('05-clear-checks', page => page.locator('#check-all').click(), async page => assert.equal(await page.locator('.grid input.red').count(), 0));
  await checkpoint('06-mini-cell', page => page.locator('#down .state').nth(1).click(), async page => {
    assert.equal(await cell(page, 1, 0).evaluate(el => el === document.activeElement), true);
    assert.equal(await page.locator('#across .highlighted-clue').count(), 1); // Vue's stale active-clue quirk
  });
  await checkpoint('07-reveal-cell', page => cell(page, 0, 2).click({ button: 'right' }), async page => {
    assert.equal(await cell(page, 0, 2).inputValue(), 'C');
    assert.equal(await page.locator('.stat-value').nth(2).textContent(), '1');
  });
  await checkpoint('08-rebus', async page => { await cell(page, 0, 4).click(); await page.keyboard.press('Space'); }, async page => assert.equal(await page.locator('.rebus-context-menu').count(), 1));
  await checkpoint('09-rebus-save', async page => { await page.locator('.rebus-context-menu-input').fill('QU'); await page.locator('.rebus-context-menu-button:not(.cancel)').click(); }, async page => assert.equal(await cell(page, 0, 4).inputValue(), 'QU'));
  await checkpoint('10-dark', page => page.locator('.theme-switch label').click(), async page => assert.equal(await page.evaluate(() => document.documentElement.style.getPropertyValue('color-scheme')), 'dark'));
  await checkpoint('11-solved-modal', page => page.locator('#overview-button').click(), async page => assert.equal(await page.locator('.modal-header h2').textContent(), 'Solved Puzzles'));
  await checkpoint('12-cache-modal', async page => { await page.locator('.modal-close-button').click(); await page.locator('#cache-button').click(); }, async page => assert.equal(await page.locator('.cache-item').count(), 5));
  await checkpoint('13-multiplayer-modal', async page => { await page.locator('.modal-close-button').click(); await page.locator('#multiplayer-button').click(); }, async page => assert.equal(await page.locator('.multiplayer-start').count(), 1));
  await checkpoint('14-load-cancel', async page => { await page.locator('.modal-close-button').click(); await page.locator('#weekday-select').selectOption('friday'); await page.locator('#get-puzzle-button').click(); }, async page => {
    assert.equal(await cell(page, 0, 0).inputValue(), 'A');
    // Verified against the running Vue reference: neither app reverts the select
    // after a cancelled reload; only the load itself is suppressed.
    assert.equal(await page.locator('#weekday-select').inputValue(), 'friday');
  });
  await checkpoint('15-crossing-direction-change', async page => {
    await page.locator('#down .clue-text').first().click();
    await page.keyboard.press('ArrowRight');
  }, async page => {
    // The first perpendicular arrow switches movement direction only. It must
    // neither advance focus nor silently replace Vue's selected Down clue.
    assert.equal(await cell(page, 0, 0).evaluate(el => el === document.activeElement), true);
    assert.equal(await page.locator('.clue-column.active').getAttribute('data-label'), 'ACROSS');
    assert.equal(await page.locator('#down .highlighted-clue .clue-number').textContent(), '1.');
    assert.equal(await page.locator('#across .highlighted-clue').count(), 0);
    assert.equal(await page.evaluate(() => document.body.dataset.activeDirection), 'down');
    assert.deepEqual(await page.locator('.grid-cell.highlighted-cell input').evaluateAll(inputs => inputs.map(el => [Number(el.dataset.row), Number(el.dataset.cell)])), [[0, 0], [1, 0], [2, 0]]);
    assert.deepEqual(await page.locator('#across .affected-clue .clue-number').allTextContents(), ['1.', '14.', '17.']);
    assert.equal(await page.locator('#across .intersection-cell-down').count(), 3);
  });
  }
} catch (error) {
  report.errors.push({ harness: error.stack });
  console.error(error);
} finally {
  await browser.close();
  report.passed = report.errors.length === 0 && report.states.length === expectedCheckpoints && report.states.every(s => s.domEqual && s.differentPixels / s.totalPixels < 0.001);
  writeFileSync(new URL('results.json', output), JSON.stringify(report, null, 2));
}
if (!report.passed) process.exitCode = 1;
