// Shared helpers: a console guard on every test, view-setting helpers, and the design
// contracts (the measurable half of the guide) expressed as Playwright assertions.
import { expect, test as base } from '@playwright/test';

export { expect };

// Every test fails if the page throws or logs a console error.
export const test = base.extend({
  consoleGuard: [
    async ({ page }, use) => {
      const errors = [];
      page.on('pageerror', (e) => errors.push(String(e)));
      page.on('console', (m) => {
        if (m.type() === 'error' && !m.location().url.includes('favicon')) errors.push(m.text());
      });
      await use();
      expect(errors, 'console errors during the test').toEqual([]);
    },
    { auto: true },
  ],
});

/** Set the view attributes on the root element (the data-* contract, guide 5.3). */
export async function applyView(page, cfg, view) {
  await page.evaluate(({ root, attrs, view }) => {
    const el = document.querySelector(root);
    for (const [key, attr] of Object.entries(attrs)) if (view[key] != null) el.setAttribute(attr, view[key]);
  }, { root: cfg.rootSelector, attrs: cfg.attrs, view });
}

/** Wait until every finite animation and transition has finished. Never use sleeps. */
export async function settle(page) {
  await page.waitForFunction(() => document.getAnimations().every((a) => a.playState !== 'running' || a.effect?.getComputedTiming().iterations === Infinity));
  await page.evaluate(() => document.fonts?.ready);
}

/** Runs inside the page: serialised by Playwright, so it must not reference anything outside. */
function probe(c) {
  const out = [];
  const add = (id, ok, detail) => out.push({ id, ok, detail });
  const toRGB = (css) => {
    const cv = document.createElement('canvas'); cv.width = cv.height = 1;
    const x = cv.getContext('2d', { willReadFrequently: true });
    x.clearRect(0, 0, 1, 1); x.fillStyle = '#000'; x.fillStyle = css; x.fillRect(0, 0, 1, 1);
    const d = x.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((p, q) => q - p); return (hi + 0.05) / (lo + 0.05); };
  const over = (top, under) => [0, 1, 2].map((i) => top[i] * top[3] + under[i] * (1 - top[3])).concat(1);
  const effectiveBg = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage.includes('gradient')) return { gradient: true };
      const bg = toRGB(cs.backgroundColor);
      if (bg[3] > 0) layers.push(bg);
      if (bg[3] >= 0.99) break;
    }
    let acc = [255, 255, 255, 1];
    for (const l of layers.reverse()) acc = over(l, acc);
    return { rgb: acc };
  };
  const root = document.querySelector(c.rootSelector);
  if (!root) { add('root', false, `no element matches rootSelector ${c.rootSelector}`); return out; }

  // R14: nothing loops
  const infinite = document.getAnimations().filter((a) => a.effect?.getComputedTiming().iterations === Infinity);
  add('no-infinite-animations', infinite.length === 0, infinite.length ? `${infinite.length} infinite: ${infinite.map((a) => a.animationName || a.transitionProperty).join(', ')}` : 'none');

  // R17: reduced motion removes motion but keeps light
  if (c.reduced) {
    const running = document.getAnimations().filter((a) => a.playState === 'running' && (a.effect?.getComputedTiming().activeDuration ?? 0) > 0);
    add('reduced-motion-stops-motion', running.length === 0, running.length ? `${running.length} still running: ${running.map((a) => a.animationName || a.transitionProperty).slice(0, 5).join(', ')}` : 'no running animations');
  }

  // Tokens resolve on the root
  const rs = getComputedStyle(root);
  const missing = (c.requiredTokens ?? []).filter((t) => rs.getPropertyValue(t).trim() === '');
  add('tokens-resolve', missing.length === 0, missing.length ? `unset on root: ${missing.join(', ')}` : `${(c.requiredTokens ?? []).length} resolve`);

  // R18: low-bloom tiers remove bloom
  if (c.luma && c.luma !== 'standard' && c.lowBloom) {
    const bad = Object.entries(c.lowBloom).filter(([k, v]) => rs.getPropertyValue(k).trim() !== v).map(([k, v]) => `${k} is "${rs.getPropertyValue(k).trim()}", want "${v}"`);
    add('low-bloom-tier', bad.length === 0, bad.length ? bad.join('; ') : 'bloom tokens lowered');
  }

  // R1/R2/R26/R27: identity is published, shown on 2+ surfaces, and colour follows rank
  const rankOf = (el) => el.style.getPropertyValue('--rank').trim() || getComputedStyle(el).getPropertyValue('--rank').trim();
  const bySel = (c.rankWearers ?? []).map((s) => [...document.querySelectorAll(s)].map(rankOf).filter((r) => r !== ''));
  if ((c.rankWearers ?? []).length) {
    const distinct = new Set(bySel.flat());
    add('identity-ranks-published', distinct.size >= 4, `${distinct.size} distinct ranks published (need 4+)`);
    const shared = [...distinct].filter((r) => bySel.filter((list) => list.includes(r)).length >= 2);
    add('identity-on-two-surfaces', shared.length > 0 || bySel.length < 2, bySel.length < 2 ? 'only one wearer selector configured' : `${shared.length} rank(s) appear on 2+ surfaces`);
  }
  if ((c.colorWearers ?? []).length) {
    const groups = new Map();
    for (const s of c.colorWearers) for (const el of document.querySelectorAll(s)) {
      const r = rankOf(el); if (r === '') continue;
      const pole = c.poleAttr ? (el.closest(`[${c.poleAttr}]`)?.getAttribute(c.poleAttr) ?? '') : '';
      const key = `${r}|${pole}`;
      groups.set(key, [...(groups.get(key) ?? []), toRGB(getComputedStyle(el).color).slice(0, 3).map(Math.round).join(',')]);
    }
    const bad = [...groups].filter(([, v]) => new Set(v).size > 1).map(([k]) => k);
    add('identity-colour-follows-rank', bad.length === 0, bad.length ? `same rank and pole, different colour: ${bad.slice(0, 4).join('; ')}` : `${groups.size} rank groups consistent`);
    const colours = new Set([...groups.values()].map((v) => v[0]));
    add('identity-colours-vary', colours.size >= Math.min(4, groups.size), `${colours.size} distinct identity colours across ${groups.size} groups`);
  }

  // R5: legibility is lightness. Measured contrast on solid backgrounds.
  for (const p of c.textPairs ?? []) {
    const els = [...document.querySelectorAll(p.text)].slice(0, 40);
    if (!els.length) { add(`contrast ${p.text}`, false, 'selector matched nothing'); continue; }
    let worst = Infinity; let checked = 0; let skipped = 0;
    for (const el of els) {
      const bg = effectiveBg(el);
      if (bg.gradient) { skipped++; continue; }
      worst = Math.min(worst, ratio(over(toRGB(getComputedStyle(el).color), bg.rgb), bg.rgb)); checked++;
    }
    add(`contrast ${p.text}`, checked > 0 && worst >= (p.min ?? 4.5), checked ? `worst ${worst.toFixed(2)}:1 over ${checked}, need ${p.min ?? 4.5}${skipped ? ` (${skipped} on gradients not measured)` : ''}` : 'every element sat on a gradient: test a solid surface');
  }

  // R10: glass budget; no repeated blur
  const glass = [...document.querySelectorAll('*')].filter((el) => { const b = getComputedStyle(el).backdropFilter; return b && b !== 'none'; });
  const sig = new Map();
  for (const el of glass) { const k = `${el.tagName}.${el.className}`; sig.set(k, (sig.get(k) ?? 0) + 1); }
  const repeated = [...sig].filter(([, n]) => n >= 3).map(([k]) => k);
  add('glass-budget', glass.length <= c.maxGlass && repeated.length === 0, `${glass.length} elements with backdrop-filter (limit ${c.maxGlass})${repeated.length ? `; repeated: ${repeated.join(', ')}` : ''}`);

  // No horizontal overflow at this viewport. Two measurements, because either alone can lie:
  //  1. scrollWidth against the REAL viewport width. On a phone the layout viewport grows to fit
  //     overflow, so innerWidth can never reveal it.
  //  2. every visible element's right edge. A root with overflow-x: clip (used to hide the
  //     backlight layer) clips overflowing content instead of making a scrollbar, so scrollWidth
  //     stays small while content is cut off. Elements inside their own horizontal scroller are fine.
  const vw = c.viewportWidth ?? window.innerWidth;
  const wide = document.documentElement.scrollWidth - vw;
  const cut = [];
  for (const el of root.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || r.right <= vw + 1) continue;
    if (getComputedStyle(el).visibility === 'hidden') continue;
    let scrolls = false;
    for (let p = el.parentElement; p && p !== root; p = p.parentElement) if (getComputedStyle(p).overflowX !== 'visible') { scrolls = true; break; }
    if (!scrolls) cut.push(`${el.tagName.toLowerCase()}${el.className ? '.' + String(el.className).split(' ')[0] : ''} ends at ${Math.round(r.right)}`);
  }
  add('no-horizontal-overflow', wide <= 1 && cut.length === 0,
    wide > 1 ? `page is ${wide}px wider than the ${vw}px viewport` : cut.length ? `${cut.length} element(s) extend past ${vw}px: ${cut.slice(0, 3).join('; ')}` : 'fits');
  return out;
}

/** Assert every design contract. Uses soft assertions so one run reports all failures. */
export async function expectContracts(page, cfg, state = {}) {
  const results = await page.evaluate(probe, { ...cfg, setup: undefined, viewportWidth: page.viewportSize()?.width, ...state });
  for (const r of results) expect.soft(r.ok, `${r.id}: ${r.detail}`).toBe(true);
}

/** Keyboard users must see where focus is. */
export async function expectFocusRing(page) {
  await page.keyboard.press('Tab');
  const ring = await page.evaluate(() => {
    const e = document.activeElement;
    if (!e || e === document.body) return { ok: false, detail: 'Tab focused nothing' };
    const s = getComputedStyle(e);
    const ok = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== 'none');
    return { ok: !!ok, detail: ok ? 'ring present' : `${e.tagName}.${e.className} has no outline or ring` };
  });
  expect(ring.ok, `focus ring: ${ring.detail}`).toBe(true);
}
