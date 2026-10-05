#!/usr/bin/env node
// audit-static.mjs: a static audit of a project's source against the Afterglow
// design language. No dependencies, no browser. Node 18+.
//
//   node audit-static.mjs --src src
//   node audit-static.mjs --src src --skip economy="no open/closed items (brief 16.2 #3)"
//   node audit-static.mjs --config design-check.config.json --json audit.json
//   node audit-static.mjs --src . --ignore ui     (skip a directory or file by name)
//   node audit-static.mjs --src src --e2e-dir tests/e2e --workflows .github/workflows
//
// The e2e checks enforce "every user journey is tested, with screenshots, in CI":
//   JOURNEYS.md rows "| J1 |" must each have a Playwright test titled "[J1] ..."; every tag must
//   have a row; there must be screenshot assertions and committed baselines; no skipped, fixme or
//   only tests; reducedMotion must go through contextOptions; a CI workflow must run
//   `playwright test` and upload the report.
//
// Exit codes: 0 pass · 1 one or more FAIL · 2 misuse (for example skipping a core check).
//
// CORE checks cannot be skipped. Only `economy` and `celebration` can be skipped,
// and only with a written reason, which is printed loudly so the user can overrule it.
// A report with SKIPs or WARNs is not "done" until the user has seen the reasons.

import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { extname, join, relative } from 'node:path';

// ---------------------------------------------------------------- arguments
const argv = process.argv.slice(2);
const opt = (name) => { const i = argv.indexOf(name); return i === -1 ? undefined : argv[i + 1]; };
const all = (name) => argv.flatMap((a, i) => (a === name ? [argv[i + 1]] : []));
let config = {};
if (opt('--config')) config = JSON.parse(readFileSync(opt('--config'), 'utf8'));
const src = opt('--src') ?? config.src ?? 'src';
const strict = argv.includes('--strict');
const e2eDir = opt('--e2e-dir') ?? config.e2eDir ?? 'tests/e2e';
const workflowsDir = opt('--workflows') ?? config.workflows ?? '.github/workflows';
const journeysFile = opt('--journeys') ?? config.journeys ?? join(e2eDir, 'JOURNEYS.md');
const maxGlass = Number(opt('--max-glass') ?? config.maxGlass ?? 5);
const maxImportant = Number(config.maxImportant ?? 20);
const maxHex = Number(config.maxHex ?? 60);
const requiredTokens = (opt('--tokens')?.split(',') ?? config.tokens ?? [
  '--ramp-l', '--ramp-c', '--ember-alpha', '--flame-alpha', '--halo-alpha',
  '--glow-pulse', '--ease-out', '--dur-quick',
]);
const skips = { ...(config.skip ?? {}) };
for (const s of all('--skip')) {
  const eq = s.indexOf('=');
  if (eq === -1) { console.error(`--skip needs id="reason", got "${s}"`); process.exit(2); }
  skips[s.slice(0, eq)] = s.slice(eq + 1).replace(/^"|"$/g, '');
}
const SKIPPABLE = new Set(['economy', 'celebration']);
for (const [id, reason] of Object.entries(skips)) {
  if (!SKIPPABLE.has(id)) { console.error(`Check "${id}" is core and cannot be skipped. Skippable: ${[...SKIPPABLE].join(', ')}.`); process.exit(2); }
  if (reason.trim().length < 15) { console.error(`Skip "${id}" needs a real reason (15+ characters), got "${reason}".`); process.exit(2); }
}

// -------------------------------------------------------------------- files
const EXT = new Set(['.css', '.scss', '.less', '.vue', '.svelte', '.astro', '.html', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']);
const STYLE_EXT = new Set(['.css', '.scss', '.less']);
const IGNORE = new Set(['node_modules', '.git', 'dist', 'build', 'coverage', '.next', '.nuxt', '.svelte-kit', '.output', ...all('--ignore'), ...(config.ignore ?? [])]);
const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    if (IGNORE.has(name)) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p);
    else if (EXT.has(extname(name))) files.push(p);
  }
})(src);

// Blank out comments but keep line numbers, so matches point at real code.
function stripComments(text, ext) {
  const blank = (m) => m.replace(/[^\n]/g, ' ');
  let out = text.replace(/\/\*[\s\S]*?\*\//g, blank).replace(/<!--[\s\S]*?-->/g, blank);
  if (ext !== '.css') out = out.replace(/(^|[^:'"`\\])\/\/[^\n]*/g, (m, p) => p + ' '.repeat(m.length - p.length));
  return out;
}
const docs = files.map((file) => {
  const ext = extname(file);
  const raw = readFileSync(file, 'utf8');
  return { file: relative('.', file), ext, raw, code: stripComments(raw, ext), isStyle: STYLE_EXT.has(ext) };
});
// "css-ish" text: style sheets plus the <style> blocks of components.
const cssText = docs.map((d) => (d.isStyle ? d.code : (d.code.match(/<style[\s\S]*?<\/style>/g) ?? []).join('\n'))).join('\n');
const nonStyle = docs.filter((d) => !d.isStyle);

function hits(regex, list = docs) {
  const found = [];
  for (const d of list) {
    d.code.split('\n').forEach((line, i) => { if (regex.test(line)) found.push(`${d.file}:${i + 1}  ${line.trim().slice(0, 110)}`); });
  }
  return found;
}
const anyIn = (regex, list = nonStyle) => list.some((d) => regex.test(d.code));

// ------------------------------------------------------------------- checks
const results = [];
const add = (id, level, status, summary, detail = []) => results.push({ id, level, status, summary, detail });
const pass = (cond) => (cond ? 'PASS' : 'FAIL');

// C1 no looping motion (R14)
{
  const re = /animation[^;{}]*\binfinite\b|animation-iteration-count\s*:\s*infinite|iterations\s*:\s*(Infinity|['"]infinite)|repeat\s*:\s*-1|\bloop\s*:\s*true/;
  const found = hits(re);
  add('no-infinite', 'core', pass(!found.length), found.length ? `${found.length} looping animation(s). Nothing loops (R14).` : 'No looping animations.', found);
}

// C2 glass budget (R10)
{
  const blocks = [];
  // `backdrop-filter: none` is a reset, not glass.
  for (const m of cssText.matchAll(/([^{}]+)\{([^{}]*backdrop-filter\s*:(?!\s*none)[^{}]*)\}/g)) blocks.push(m[1].trim().replace(/\s+/g, ' '));
  const selectors = [...new Set(blocks)];
  const repeated = selectors.filter((s) => /\b(li|tr|td|row|cell|tile|item|chip|slot)\b|[-_.](row|cell|tile|item|chip|slot|list-item)\b/i.test(s));
  const status = selectors.length > maxGlass ? 'FAIL' : repeated.length ? 'WARN' : 'PASS';
  add('glass-budget', 'core', status,
    `${selectors.length} rule(s) use backdrop-filter (limit ${maxGlass}).${repeated.length ? ' Some selectors look like repeated surfaces (R10).' : ''}`,
    [...selectors.map((s) => `  ${s}`), ...repeated.map((s) => `  REPEATED? ${s}`)]);
}

// C3 reduced motion (R17)
add('reduced-motion', 'core', pass(/prefers-reduced-motion\s*:\s*reduce/.test(cssText)),
  /prefers-reduced-motion\s*:\s*reduce/.test(cssText) ? 'A prefers-reduced-motion block exists.' : 'No @media (prefers-reduced-motion: reduce) block (R17).');

// C4 tokens
{
  const missing = requiredTokens.filter((t) => !new RegExp(`${t.replace(/[-]/g, '\\-')}\\s*:`).test(cssText));
  add('tokens', 'core', pass(!missing.length), missing.length ? `Missing tokens: ${missing.join(', ')}. Keep the variable names (guide 14.1).` : `All ${requiredTokens.length} required tokens are declared.`);
}

// C5 registered properties
add('registered-glow', 'core', pass(/@property\s+--glow-pulse/.test(cssText)),
  /@property\s+--glow-pulse/.test(cssText) ? '@property --glow-pulse is registered.' : '@property --glow-pulse is missing: the ignition cannot ease (guide 9.3).');

// C6 identity ramp (S3, R1, R2, R6)
{
  const miss = [];
  if (!/oklch\(/.test(cssText)) miss.push('CSS never uses oklch()');
  if (!/var\(\s*--rank/.test(cssText)) miss.push('CSS never reads var(--rank)');
  if (!anyIn(/['"`]?--rank['"`]?\s*[:,)]|setProperty\(\s*['"]--rank/)) miss.push('no markup or script publishes --rank on items');
  add('identity-ramp', 'core', pass(!miss.length), miss.length ? `Content identity is not wired (S3): ${miss.join('; ')}.` : 'The rank is published and read by the ramp.', miss.map((m) => `  ${m}`));
}

// C7 view tiers (S5, R19-R22)
{
  const miss = [];
  if (!/\[data-luma/.test(cssText)) miss.push('CSS has no [data-luma] tier');
  if (!/\[data-vibrance/.test(cssText)) miss.push('CSS has no [data-vibrance] tier');
  if (!anyIn(/data-luma|data-\$\{|setAttribute\(\s*`data-|dataset\.luma/)) miss.push('no code publishes the data-* settings on the root');
  if (!anyIn(/localStorage/) ) miss.push('settings are not persisted');
  if (!anyIn(/prefers-contrast|prefers-reduced-transparency/)) miss.push('no media hint chooses the first-visit brightness');
  if (!anyIn(/view-tier|data-tier|view-cluster/)) miss.push('no View panel UI is mounted');
  add('view-tiers', 'core', pass(!miss.length), miss.length ? `The mini/micro/nano settings are incomplete (S5): ${miss.join('; ')}.` : 'Settings contract, persistence, media hint and panel are present.', miss.map((m) => `  ${m}`));
}

// C8 territory (S6)
{
  const miss = [];
  if (!/@property\s+--(ta|territory)-?[a-z-]*/.test(cssText)) miss.push('no registered territory properties (@property --ta-top ...)');
  if (!anyIn(/--ta-top|--territory-/)) miss.push('no code publishes the corner ranks');
  add('territory', 'core', pass(!miss.length), miss.length ? `The ground is not lit by what is on screen (S6): ${miss.join('; ')}.` : 'Territory properties are registered and published.', miss.map((m) => `  ${m}`));
}

// C9 economy of light (S7), skippable with a reason
{
  const miss = [];
  if (!/--charge/.test(cssText)) miss.push('no --charge in CSS');
  if (!anyIn(/--remaining\s*[:'"]|['"]--remaining['"]/)) miss.push('no code publishes --remaining');
  if (skips.economy) add('economy', 'skippable', 'SKIP', `SKIPPED. Reason given: ${skips.economy}`);
  else add('economy', 'skippable', pass(!miss.length), miss.length ? `The economy of light is absent (S7): ${miss.join('; ')}. If the project has no open/closed items, skip with --skip economy="reason".` : 'Charge and remainder are wired.');
}

// C10 celebration (S8), skippable with a reason
{
  const ok = anyIn(/celebrat|rapture|finale|confetti/i) && anyIn(/\btier\b/i);
  if (skips.celebration) add('celebration', 'skippable', 'SKIP', `SKIPPED. Reason given: ${skips.celebration}`);
  else add('celebration', 'skippable', pass(ok), ok ? 'Tiered celebration is present.' : 'No tiered celebration (S8). If there is no finishing event, skip with --skip celebration="reason".');
}

// ---- E2E: Playwright, journeys, screenshots, CI (core, cannot be skipped)
function listFiles(dir, keep) {
  const found = [];
  try {
    for (const name of readdirSync(dir)) {
      if (name === 'node_modules' || name === '.git') continue;
      const p = join(dir, name);
      if (statSync(p).isDirectory()) found.push(...listFiles(p, keep)); else if (keep(p)) found.push(p);
    }
  } catch { /* directory missing: reported by the checks below */ }
  return found;
}
{
  const specs = listFiles(e2eDir, (p) => /\.spec\.(m?[jt]s|[jt]sx)$/.test(p));
  const specText = specs.map((f) => ({ file: f, text: stripComments(readFileSync(f, 'utf8'), '.js') }));
  const configs = [...listFiles(e2eDir, (p) => /playwright\.config\.(m?[jt]s)$/.test(p)), ...['playwright.config.ts', 'playwright.config.js', 'playwright.config.mjs'].filter((f) => { try { return statSync(f).isFile(); } catch { return false; } })];

  // E1 Playwright is the runner
  {
    const miss = [];
    if (!configs.length) miss.push(`no playwright.config.* under ${e2eDir} or at the root`);
    if (!specs.length) miss.push(`no *.spec.* files under ${e2eDir}`);
    let pkg = ''; try { pkg = readFileSync('package.json', 'utf8'); } catch { /* none */ }
    if (!/@playwright\/test/.test(pkg)) miss.push('@playwright/test is not in package.json');
    add('e2e-playwright', 'core', pass(!miss.length), miss.length ? `Playwright e2e is not set up: ${miss.join('; ')}. Install: npm i -D @playwright/test && npx playwright install chromium` : `Playwright config and ${specs.length} spec file(s) present.`, miss.map((m) => `  ${m}`));
  }

  // E2 every journey has a test, and every test tag has a journey
  {
    let rows = [];
    try { rows = [...readFileSync(journeysFile, 'utf8').matchAll(/^\|\s*(J\d+)\s*\|/gm)].map((m) => m[1]); } catch { /* reported below */ }
    const tagged = new Set(specText.flatMap((d) => [...d.text.matchAll(/\[(J\d+)\]/g)].map((m) => m[1])));
    const miss = [];
    if (!rows.length) miss.push(`${journeysFile} is missing or has no "| J1 |" rows`);
    for (const r of rows) if (!tagged.has(r)) miss.push(`${r} is in the inventory but no test is titled "[${r}] ..."`);
    for (const t of tagged) if (!rows.includes(t)) miss.push(`a test is tagged [${t}] but ${journeysFile} has no row for it`);
    add('e2e-journeys', 'core', pass(!miss.length), miss.length ? `Journey coverage is incomplete: ${miss.length} gap(s).` : `${rows.length} journeys, each with a test.`, miss.map((m) => `  ${m}`));
    globalThis.__journeyCount = rows.length;
  }

  // E3 screenshots asserted and baselines committed
  {
    const shots = specText.reduce((n, d) => n + (d.text.match(/toHaveScreenshot\(/g) ?? []).length, 0);
    const baselines = listFiles(e2eDir, (p) => /(__screenshots__|-snapshots)/.test(p) && p.endsWith('.png')).length;
    const need = globalThis.__journeyCount || 1;
    const miss = [];
    if (shots < need) miss.push(`${shots} toHaveScreenshot() call(s) for ${need} journeys: every journey needs at least one`);
    if (baselines < need) miss.push(`${baselines} committed baseline PNG(s) for ${need} journeys: generate and COMMIT them (guide 17.4)`);
    add('e2e-screenshots', 'core', pass(!miss.length), miss.length ? 'Screenshot coverage is incomplete.' : `${shots} screenshot assertions, ${baselines} committed baselines.`, miss.map((m) => `  ${m}`));
  }

  // E4 hygiene: skipped tests are debt, not green
  {
    const found = [];
    for (const d of specText) d.text.split('\n').forEach((l, i) => { if (/\b(test|it|describe)\.(skip|fixme|only)\s*\(|\btest\.slow\(\)|\.skip\(\s*\)/.test(l)) found.push(`${d.file}:${i + 1}  ${l.trim().slice(0, 100)}`); });
    add('e2e-no-skips', 'core', pass(!found.length), found.length ? `${found.length} skipped/fixme/only test(s). A skipped test is unfinished work, not a pass.` : 'No skipped, fixme or only tests.', found);
  }

  // E5 the Playwright 1.55 trap: top-level `reducedMotion` is silently ignored
  {
    // Comments are stripped first, and the structure is required (not just the word), so an
    // explanatory comment cannot satisfy the check.
    const cfgText = configs.map((f) => ({ f, t: stripComments(readFileSync(f, 'utf8'), '.js') }));
    const bad = cfgText.filter(({ t }) => /reducedMotion/.test(t) && !/contextOptions\s*:\s*\{[^}]*reducedMotion/.test(t)).map(({ f }) => f);
    const has = cfgText.some(({ t }) => /reducedMotion/.test(t)) || specText.some((d) => /emulateMedia\([^)]*reducedMotion/.test(d.text));
    const miss = [];
    if (bad.length) miss.push(`reducedMotion set outside contextOptions in ${bad.join(', ')}: Playwright ignores it silently`);
    if (!has) miss.push('no reduced-motion test (set contextOptions.reducedMotion or call page.emulateMedia)');
    add('e2e-reduced-motion', 'core', pass(!miss.length), miss.length ? `Reduced motion is not really tested: ${miss.join('; ')}.` : 'Reduced motion is emulated through contextOptions or emulateMedia.', miss.map((m) => `  ${m}`));
  }

  // E6 CI runs it and keeps the evidence
  {
    const wf = [...listFiles(workflowsDir, (p) => /\.ya?ml$/.test(p)), ...['.gitlab-ci.yml', '.circleci/config.yml'].filter((f) => { try { return statSync(f).isFile(); } catch { return false; } })];
    const text = wf.map((f) => readFileSync(f, 'utf8')).join('\n');
    const miss = [];
    if (!wf.length) miss.push(`no CI workflow found under ${workflowsDir}`);
    else {
      if (!/playwright\s+test/.test(text)) miss.push('no CI step runs `playwright test`');
      if (!/playwright\s+install/.test(text)) miss.push('no CI step installs the browser (`playwright install`)');
      if (!/upload-artifact|artifacts:/.test(text)) miss.push('CI does not upload the report and screenshot diffs');
    }
    add('e2e-ci', 'core', pass(!miss.length), miss.length ? `CI does not run the e2e suite: ${miss.join('; ')}.` : 'CI installs the browser, runs playwright test and uploads the report.', miss.map((m) => `  ${m}`));
  }
}

// Standard checks (WARN, or FAIL under --strict)
{
  const hexLines = [];
  for (const d of docs) {
    const text = d.isStyle ? d.code : (d.code.match(/<style[\s\S]*?<\/style>/g) ?? []).join('\n');
    text.split('\n').forEach((line, i) => { if (/#[0-9a-fA-F]{3,8}\b/.test(line) && !/^\s*--/.test(line)) hexLines.push(`${d.file}:${i + 1}`); });
  }
  add('hex-literals', 'standard', hexLines.length > maxHex ? 'WARN' : 'PASS', `${hexLines.length} hex colour literal(s) outside token declarations (limit ${maxHex}). Colours come from the ramp (R6).`, hexLines.length > maxHex ? hexLines.slice(0, 15).map((l) => `  ${l}`) : []);
  const important = (cssText.match(/!important/g) ?? []).length;
  add('important', 'standard', important > maxImportant ? 'WARN' : 'PASS', `${important} use(s) of !important (limit ${maxImportant}).`);
  const emoji = [];
  for (const d of docs.filter((x) => ['.vue', '.jsx', '.tsx', '.html', '.svelte', '.astro'].includes(x.ext))) {
    d.raw.split('\n').forEach((line, i) => { if (/\p{Extended_Pictographic}/u.test(line)) emoji.push(`${d.file}:${i + 1}  ${line.trim().slice(0, 90)}`); });
  }
  add('emoji', 'standard', emoji.length ? 'WARN' : 'PASS', emoji.length ? `${emoji.length} line(s) with emoji in markup. Anti-slop list (guide 18).` : 'No emoji in markup.', emoji.slice(0, 15).map((l) => `  ${l}`));
  const layout = cssText.split('\n').filter((l) => /transition[^;]*\b(width|height|top|left|right|bottom|margin|padding)\b|transition\s*:\s*all\b/.test(l));
  add('layout-motion', 'standard', layout.length ? 'WARN' : 'PASS', layout.length ? `${layout.length} transition(s) on layout properties or "all" (R15).` : 'No layout transitions.', layout.slice(0, 10).map((l) => `  ${l.trim().slice(0, 110)}`));
}

// ------------------------------------------------------------------- report
if (strict) for (const r of results) if (r.status === 'WARN') r.status = 'FAIL';
const mark = { PASS: 'PASS', FAIL: 'FAIL', WARN: 'WARN', SKIP: 'SKIP' };
console.log(`\nAfterglow static audit: ${docs.length} files under ${src}\n`);
for (const r of results) {
  console.log(`${mark[r.status].padEnd(4)}  ${r.id.padEnd(16)} [${r.level}]  ${r.summary}`);
  if (r.status !== 'PASS') for (const d of r.detail) console.log(`      ${d}`);
}
const failed = results.filter((r) => r.status === 'FAIL');
const skipped = results.filter((r) => r.status === 'SKIP');
const warned = results.filter((r) => r.status === 'WARN');
console.log(`\n${results.length - failed.length - skipped.length - warned.length} passed, ${failed.length} failed, ${warned.length} warnings, ${skipped.length} skipped.`);
if (skipped.length) console.log('SKIPS NEED THE USER\'S APPROVAL. Report them verbatim:\n' + skipped.map((s) => `  - ${s.id}: ${s.summary}`).join('\n'));
if (failed.length) console.log('\nNOT DONE. Fix every FAIL and run this again. Do not report completion while any check fails.');
if (opt('--json')) writeFileSync(opt('--json'), JSON.stringify({ src, results }, null, 2));
process.exit(failed.length ? 1 : 0);
