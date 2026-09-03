#!/usr/bin/env node
/**
 * Template crafter v2: starts from seed masks, splits every run longer than
 * MAX_SLOT with symmetric blocks, cascades short-run repairs, validates, then
 * lets the full web2 lexicon fill judge each survivor. Survivors become the
 * curated bank.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';

const { deriveTopology, validateTopologyMask } = await import('../packages/construction/src/topology.ts');
const { loadLexicon } = await import('../packages/construction/src/lexicon.ts');
const { solveFill } = await import('../packages/construction/src/csp.ts');

const SIZE = 15;
const idx = (r, c) => r * SIZE + c;
const isBlock = (mask, r, c) => mask[idx(r, c)] === '#';
const MAX_SLOT = 10;

const text = readFileSync(path.resolve('packages/construction/data/fill-lexicon-v1.txt'), 'utf8');
const lexicon = loadLexicon(text);
const candidates = text.split('\n').filter(Boolean).map((word) => lexicon.resolve(word)).filter(Boolean);

function runsOfMask(mask, line, isAcross) {
  const runs = [];
  let start = -1;
  for (let i = 0; i <= SIZE; i += 1) {
    const white = i < SIZE && !isBlock(mask, isAcross ? line : i, isAcross ? i : line);
    if (white && start < 0) start = i;
    if (!white && start >= 0) { runs.push([start, i - start]); start = -1; }
  }
  return runs;
}

function acrossRuns(mask, r) { return runsOfMask(mask, r, true); }
function downRuns(mask, c) { return runsOfMask(mask, c, false); }

function lrSym(mask) {
  for (let r = 0; r < SIZE; r += 1) for (let c = 0; c < SIZE; c += 1) if (mask[idx(r, c)] !== mask[idx(r, SIZE - 1 - c)]) return false;
  return true;
}
function tbSym(mask) {
  for (let r = 0; r < SIZE; r += 1) for (let c = 0; c < SIZE; c += 1) if (mask[idx(r, c)] !== mask[idx(SIZE - 1 - r, c)]) return false;
  return true;
}
function minRunOk(mask) {
  for (let i = 0; i < SIZE; i += 1) {
    if (acrossRuns(mask, i).some(([, l]) => l < 3)) return false;
    if (downRuns(mask, i).some(([, l]) => l < 3)) return false;
  }
  return true;
}
function allChecked(mask) {
  for (let r = 0; r < SIZE; r += 1) {
    for (let c = 0; c < SIZE; c += 1) {
      if (isBlock(mask, r, c)) continue;
      const inA = acrossRuns(mask, r).some(([s, l]) => c >= s && c < s + l && l >= 2);
      const inD = downRuns(mask, c).some(([s, l]) => r >= s && r < s + l && l >= 2);
      if (!inA || !inD) return false;
    }
  }
  return true;
}
function connected(mask) {
  const flat = mask.join('');
  const start = flat.indexOf('.');
  if (start < 0) return false;
  const seen = new Set([start]);
  const queue = [start];
  while (queue.length > 0) {
    const cur = queue.pop();
    const r = Math.floor(cur / SIZE), c = cur % SIZE;
    for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nr = r + dr, nc = c + dc;
      if (nr < 0 || nc < 0 || nr >= SIZE || nc >= SIZE || isBlock(mask, nr, nc)) continue;
      const n = idx(nr, nc);
      if (!seen.has(n)) { seen.add(n); queue.push(n); }
    }
  }
  return seen.size === mask.filter((v) => v === '.').length;
}

function splitRun(mask, dir, line, start, length, position) {
  const [r, c] = dir === 'a' ? [line, position] : [position, line];
  if (isBlock(mask, r, c)) return false;
  mask[idx(r, c)] = '#';
  mask[idx(SIZE - 1 - r, SIZE - 1 - c)] = '#';
  return true;
}

function fixShort(mask) {
  for (let r = 0; r < SIZE; r += 1) {
    for (const [s, l] of acrossRuns(mask, r)) {
      if (l >= 3 || l === 0) continue;
      const targets = s === 0 ? [s + l] : [s - 1, s + l];
      for (const c of targets) {
        if (c < 0 || c >= SIZE || isBlock(mask, r, c)) continue;
        mask[idx(r, c)] = '#'; mask[idx(r, SIZE - 1 - c)] = '#';
        mask[idx(SIZE - 1 - r, c)] = '#'; mask[idx(SIZE - 1 - r, SIZE - 1 - c)] = '#';
        return true;
      }
    }
  }
  for (let c = 0; c < SIZE; c += 1) {
    for (const [s, l] of downRuns(mask, c)) {
      if (l >= 3 || l === 0) continue;
      const targets = s === 0 ? [s + l] : [s - 1, s + l];
      for (const r of targets) {
        if (r < 0 || r >= SIZE || isBlock(mask, r, c)) continue;
        mask[idx(r, c)] = '#'; mask[idx(SIZE - 1 - r, c)] = '#';
        return true;
      }
    }
  }
  return false;
}

function findLongRun(mask) {
  let best;
  for (let r = 0; r < SIZE; r += 1) {
    for (const [s, l] of acrossRuns(mask, r)) if (l > MAX_SLOT && (!best || l > best.length)) best = { dir: 'a', line: r, start: s, length: l };
  }
  for (let c = 0; c < SIZE; c += 1) {
    for (const [s, l] of downRuns(mask, c)) if (l > MAX_SLOT && (!best || l > best.length)) best = { dir: 'd', line: c, start: s, length: l };
  }
  return best;
}

function stableRepair(mask) {
  for (let pass = 0; pass < 40; pass += 1) if (!fixShort(mask)) return true;
  return false;
}

/** DFS over split positions for each long run; returns a valid mask or null. */
function dfsSplits(mask, depth) {
  if (depth > 14) return null;
  if (!stableRepair(mask)) return null;
  const long = findLongRun(mask);
  if (!long) {
    return validateTopologyMask(rowsOf(mask)).length === 0 ? mask : null;
  }
  const positions = [];
  for (let i = long.start + 3; i < long.start + long.length - 2; i += 1) positions.push(i);
  positions.sort((a, b) => Math.abs(a - (long.start + long.length / 2)) - Math.abs(b - (long.start + long.length / 2)));
  for (const position of positions) {
    const trial = mask.slice();
    if (!splitRun(trial, long.dir, long.line, long.start, long.length, position)) continue;
    const solved = dfsSplits(trial, depth + 1);
    if (solved) return solved;
  }
  return null;
}

function rowsOf(mask) {
  const out = [];
  for (let r = 0; r < SIZE; r += 1) out.push(mask.slice(r * SIZE, r * SIZE + SIZE).join(''));
  return out;
}

const SEEDS = [
  ['wide-open-26', [
    '...............', '...............', '...............', '....#######....',
    '.......#.......', '...............', '...............', '#####.....#####',
    '...............', '...............', '.......#.......', '....#######....',
    '...............', '...............', '...............'
  ]],
  ['double-stack-30', [
    '...............', '...............', '...............', '...#.......#...',
    '#####.....#####', '......###......', '...............', '...............',
    '...............', '......###......', '#####.....#####', '...#.......#...',
    '...............', '...............', '...............'
  ]],
  ['side-towers-31', [
    '.......#.......', '.......#.......', '...............', '####.......####',
    '...............', '....#.....#....', '...............', '##....###....##',
    '...............', '....#.....#....', '...............', '####.......####',
    '...............', '.......#.......', '.......#.......'
  ]],
  ['corner-notches-31', [
    '##...........##', '...............', '...............', '...............',
    '.....#...#.....', '####.......####', '...............', '......###......',
    '...............', '####.......####', '.....#...#.....', '...............',
    '...............', '...............', '##...........##'
  ]]
];

const seen = new Set();
const results = [];
for (const [name, rows] of SEEDS) {
  for (const variant of [0]) {
    const mask = dfsSplits(rows.join('').split(''), 0);
    if (!mask) continue;
    const key = mask.join('');
    if (seen.has(key)) continue;
    seen.add(key);
    const violations = validateTopologyMask(rowsOf(mask));
    if (violations.length > 0) {
      if (process.env.CRAFT_DEBUG) {
        console.log(`${name}-v${variant} invalid: ${violations.map((v) => v.code).join(',')}`);
        for (const row of rowsOf(mask)) console.log(row);
      }
      continue;
    }
    const derived = deriveTopology(rowsOf(mask), { templateId: `${name}-v${variant}` });
    if (!derived.ok) continue;
    results.push({ name, variant, mask: rowsOf(mask), topology: derived.topology });
  }
}

console.log(`crafted ${results.length} valid templates`);
for (const { name, variant, mask, topology } of results) {
  const histogram = {};
  for (const s of topology.slots) histogram[s.length] = (histogram[s.length] ?? 0) + 1;
  const downs = topology.slots.filter((s) => s.id.startsWith('D'));
  const maxDown = Math.max(...downs.map((s) => s.length));
  console.log(`\n=== ${name}-v${variant}: entries=${topology.entries.length} crossings=${topology.intersections.length} maxDown=${maxDown} lengths=${JSON.stringify(histogram)}`);
  for (const row of mask) console.log(row);

  const started = Date.now();
  const result = solveFill({ slots: topology.slots, intersections: topology.intersections, candidates, seed: 7, maxNodes: 120_000 });
  const elapsed = Date.now() - started;
  if (result.status === 'solved') {
    const words = Object.values(result.solution.assignments).map((c) => c.word);
    const avgLen = (words.reduce((x, y) => x + y.length, 0) / words.length).toFixed(2);
    console.log(`  SOLVED ${elapsed}ms nodes=${result.solution.nodes} score=${result.solution.score.toFixed(1)} avgLen=${avgLen}`);
    console.log(`  ${words.slice(0, 16).join(' ')}`);
  } else {
    console.log(`  FAILED (${result.failure?.code}) ${elapsed}ms nodes=${result.failure?.nodes}`);
  }
}
