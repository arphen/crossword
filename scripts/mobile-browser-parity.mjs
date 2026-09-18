// Real mobile routes + Socket.IO join, synthetic puzzle HTTP response only.
// Creates two isolated in-memory rooms; never writes completion/puzzle storage.
import { chromium } from 'playwright';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const out = new URL('../reports/react-mobile-parity/', import.meta.url);
mkdirSync(out, { recursive: true });
const urls = { vue: process.env.VUE_PARITY_URL ?? 'http://127.0.0.1:5001/legacy/', react: process.env.REACT_PARITY_URL ?? 'http://127.0.0.1:5001/' };
const fixture = { entries: [
  { clue_number: 1, clue_text: 'Feline', direction: 'across', start_x: 0, start_y: 0, characters: [...'CAT'].map(letters => ({ letters })) },
  { clue_number: 1, clue_text: 'Rogue', direction: 'down', start_x: 0, start_y: 0, characters: [...'CAD'].map(letters => ({ letters })) },
  { clue_number: 3, clue_text: 'Canine', direction: 'across', start_x: 0, start_y: 2, characters: [...'DOG'].map(letters => ({ letters })) },
] };
const executablePath = process.env.CHROME_BIN ?? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/chromium'].find(existsSync);
const browser = await chromium.launch({ ...(executablePath ? { executablePath } : {}), headless: true });
const report = { browser: browser.version(), viewport: { width: 390, height: 844 }, states: [], errors: [], notes: 'Real mobile routes/Socket.IO initial join with isolated ephemeral rooms. Synthetic HTTP puzzle. No device keyboard emulation; Chromium desktop engine at mobile viewport. Screenshot tolerance <0.1%, color threshold 0.1.' };
const pages = {};
try {
  for (const [engine, base] of Object.entries(urls)) {
    const context = await browser.newContext({ viewport: report.viewport, deviceScaleFactor: 1, colorScheme: 'light' });
    const origin = new URL(base).origin;
    const response = await context.request.post(`${origin}/api/multiplayer/create`, { data: { date: '260829' } });
    assert.equal(response.status(), 200);
    const { room_id } = await response.json();
    await context.route('**/*', route => {
      const u = new URL(route.request().url());
      if (u.origin !== origin) return route.abort();
      if (u.pathname.startsWith('/crossword_by_date/')) return route.fulfill({ json: fixture });
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', e => report.errors.push({ engine, error: e.message }));
    const mobilePath = engine === 'vue' ? '/legacy/mobile' : '/mobile';
    await page.goto(`${origin}${mobilePath}/${room_id}/across`);
    await page.locator('.clue-item').first().waitFor();
    pages[engine] = page;
  }
  async function capture(id, action, verify) {
    const states = {}, shots = {};
    for (const [engine, page] of Object.entries(pages)) {
      if (action) await action(page);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      if (verify) await verify(page);
      states[engine] = await page.evaluate(() => {
        const root = document.querySelector('#app');
        function walk(el) {
          return { tag: el.tagName, classes: [...el.classList].sort(), text: [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').replace(/\s+/g, ' ').trim(), value: el.matches('input') ? el.value : null, children: [...el.children].map(walk) };
        }
        return { tree: walk(root), focusedTag: document.activeElement.tagName,
          focusedClue: document.activeElement.closest('.clue-item')?.querySelector('.clue-number').textContent.trim() ?? null,
          activeIndex: [...root.querySelectorAll('.clue-item.active .char-box')].findIndex(el => el.classList.contains('active-cell')) };
      });
      shots[engine] = PNG.sync.read(await page.screenshot({ path: new URL(`${id}-${engine}.png`, out).pathname, animations: 'disabled', caret: 'hide' }));
    }
    writeFileSync(new URL(`${id}-dom.json`, out), JSON.stringify(states, null, 2));
    const a = shots.vue, b = shots.react, diff = new PNG({ width: a.width, height: a.height });
    const pixels = pixelmatch(a.data, b.data, diff.data, a.width, a.height, { threshold: 0.1 });
    writeFileSync(new URL(`${id}-diff.png`, out), PNG.sync.write(diff));
    let domEqual = true;
    try { assert.deepEqual(states.react, states.vue); } catch (error) { domEqual = false; console.error(error.message); }
    report.states.push({ id, domEqual, differentPixels: pixels, ratio: pixels / (a.width * a.height) });
    console.log(`${id}: DOM ${domEqual ? 'equal' : 'DIFF'}, ${pixels} differing pixels`);
  }
  const activeCell = async page => page.locator('.active-cell').textContent();
  await capture('01-loaded', null, async page => assert.equal(await page.locator('.clue-item').count(), 2));
  await capture('02-selected', page => page.locator('.clue-text').first().click(), async page => assert.equal(await page.locator('input').evaluate(el => el === document.activeElement), true));
  await capture('03-type', page => page.keyboard.type('CA'), async page => {
    assert.deepEqual(await page.locator('.clue-item.active .char-box').allTextContents().then(a => a.map(t => t.trim())), ['C', 'A', '']);
    assert.equal((await activeCell(page)).trim(), '');
  });
  await capture('04-backspace', page => page.keyboard.press('Backspace'), async page => assert.deepEqual(await page.locator('.clue-item.active .char-box').allTextContents().then(a => a.map(t => t.trim())), ['C', '', '']));
  await capture('05-correct-word', page => page.keyboard.type('AT'));
  await capture('06-check', page => page.locator('.check-btn').click(), async page => assert.equal(await page.locator('.correct').count(), 3));
  await capture('07-reorder', page => page.locator('.check-btn').click(), async page => assert.deepEqual((await page.locator('.clue-number').allTextContents()).map(t => t.trim()), ['3', '1']));
  await capture('08-refocus-solved', page => page.locator('.clue-item.solved .char-box').nth(1).click(), async page => assert.equal(await page.locator('input').evaluate(el => el === document.activeElement), true));
  await capture('09-switch-clue', page => page.locator('.clue-item').first().locator('.char-box').nth(2).click(), async page => assert.equal(await page.locator('input').evaluate(el => el === document.activeElement), true));
  await capture('10-final-cell-input', page => page.keyboard.type('G'), async page => assert.equal((await activeCell(page)).trim(), 'G'));
} catch (error) { report.errors.push({ harness: error.stack }); console.error(error); }
finally {
  await browser.close();
  report.passed = report.errors.length === 0 && report.states.length === 10 && report.states.every(s => s.domEqual && s.ratio < 0.001);
  writeFileSync(new URL('results.json', out), JSON.stringify(report, null, 2));
}
if (!report.passed) process.exitCode = 1;
