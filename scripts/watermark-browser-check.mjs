import { chromium } from 'playwright';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const base = process.env.WATERMARK_URL ?? 'http://127.0.0.1:5001/';
const output = new URL('../reports/watermark/', import.meta.url);
mkdirSync(output, { recursive: true });
const fixture = JSON.parse(readFileSync(new URL('../reports/react-parity/fixture.json', import.meta.url), 'utf8'));
const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const report = { url: base, viewport: { width: 846, height: 1722 }, errors: [] };
try {
  const page = await browser.newPage({ viewport: report.viewport, colorScheme: 'dark' });
  page.on('pageerror', e => report.errors.push(e.message));
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.origin !== new URL(base).origin || u.pathname.startsWith('/socket.io')) return route.abort();
    if (u.pathname.startsWith('/random_crossword/')) return route.fulfill({ json: fixture });
    if (u.pathname.startsWith('/api/completed_puzzles')) return route.fulfill({ json: { completed: false } });
    return route.continue();
  });
  await page.addInitScript(() => { localStorage.setItem('lastCachingTime', String(Date.now())); window.setInterval = () => 1; });
  await page.goto(base);
  await page.locator('#down li').first().waitFor();
  const cdp = await page.context().newCDPSession(page);
  async function measure() {
    const { root } = await cdp.send('DOM.getDocument');
    const result = {};
    for (const direction of ['ACROSS', 'DOWN']) {
      const selector = `.clue-column[data-label="${direction}"]`;
      const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root.nodeId, selector });
      const { node } = await cdp.send('DOM.describeNode', { nodeId, depth: 1 });
      const pseudo = node.pseudoElements.find(el => el.pseudoType === 'before');
      const { model } = await cdp.send('DOM.getBoxModel', { backendNodeId: pseudo.backendNodeId });
      result[direction] = await page.locator(selector).evaluate(el => {
        const r = el.getBoundingClientRect(), list = el.querySelector('ul');
        return { container: { x: r.x, y: r.y, width: r.width, height: r.height }, content: getComputedStyle(el, '::before').content, scrollTop: list.scrollTop, scrollHeight: list.scrollHeight, clientHeight: list.clientHeight };
      });
      result[direction].watermark = model.border;
    }
    return result;
  }
  report.before = await measure();
  await page.screenshot({ path: new URL('before.png', output).pathname, animations: 'disabled' });
  await page.locator('#down').evaluate(el => { el.scrollTop = el.scrollHeight; });
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  report.after = await measure();
  await page.screenshot({ path: new URL('after.png', output).pathname, animations: 'disabled' });
  assert.ok(report.after.DOWN.scrollTop > 0, 'Down list must actually scroll');
  assert.equal(report.after.DOWN.content, '"DOWN"');
  assert.equal(report.after.ACROSS.content, '"ACROSS"');
  for (const direction of ['ACROSS', 'DOWN']) {
    assert.deepEqual(report.after[direction].watermark, report.before[direction].watermark, `${direction} watermark moved`);
    assert.deepEqual(report.after[direction].container, report.before[direction].container);
  }
  report.themeViewport = { width: 1440, height: 1000 };
  await page.setViewportSize(report.themeViewport);
  report.themes = {};
  for (const theme of ['light', 'dark']) {
    await page.evaluate(theme => document.documentElement.style.setProperty('color-scheme', theme), theme);
    report.themes[theme] = {};
    for (const inactive of ['ACROSS', 'DOWN']) {
      const activeList = inactive === 'ACROSS' ? '#down' : '#across';
      await page.locator(`${activeList} .clue-text`).first().click();
      const selector = `.clue-column[data-label="${inactive}"].inactive`;
      await page.locator(selector).waitFor();
      await page.screenshot({ path: new URL(`${theme}-${inactive.toLowerCase()}-inactive.png`, output).pathname, animations: 'disabled' });
      const state = await page.locator(selector).evaluate(el => {
        const style = getComputedStyle(el, '::before');
        return { color: style.color, opacity: style.opacity, inheritedColor: getComputedStyle(el).color, content: style.content, display: style.display, visibility: style.visibility };
      });
      report.themes[theme][inactive] = state;
      assert.equal(state.color, state.inheritedColor);
      assert.ok(Number(state.opacity) >= 0.3, `${theme} ${inactive} opacity too low`);
      assert.equal(state.content, `"${inactive}"`);
      assert.notEqual(state.display, 'none');
      assert.equal(state.visibility, 'visible');
    }
  }
  for (const direction of ['ACROSS', 'DOWN']) assert.notEqual(report.themes.light[direction].color, report.themes.dark[direction].color);
  assert.deepEqual(report.errors, []);
  report.passed = true;
  console.log(JSON.stringify(report, null, 2));
} catch (error) { report.passed = false; report.errors.push(error.stack); console.error(error); process.exitCode = 1; }
finally { await browser.close(); writeFileSync(new URL('results.json', output), JSON.stringify(report, null, 2)); }
