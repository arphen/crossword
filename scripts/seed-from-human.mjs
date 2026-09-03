#!/usr/bin/env node
/**
 * Fill the proven human mask (createRealPuzzle's topology) with the full
 * web2 lexicon, then generate and judge structural variants of it. This
 * seeds the template bank from a grid that is known to be NYT-fillable.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';

const { deriveTopology } = await import('../packages/construction/src/topology.ts');
const { loadLexicon } = await import('../packages/construction/src/lexicon.ts');
const { solveFill } = await import('../packages/construction/src/csp.ts');

const SIZE = 15;
const idx = (r, c) => r * SIZE + c;
const isBlock = (mask, r, c) => mask[idx(r, c)] === '#';

// The proven human mask from packages/domain/src/puzzle.ts (realPuzzleMask)
const HUMAN = [
  '....#....#.....',
  '....#....#.....',
  '....#....#.....',
  '...........#...',
  '####...#...#...',
  '......#......##',
  '.....#....#....',
  '.....#...#.....',
  '....#....#.....',
  '##......#......',
  '...#...#...####',
  '...#...........',
  '.....#....#....',
  '.....#....#....',
  '.....#....#....'
];

const text = readFileSync(path.resolve('packages/construction/data/fill-lexicon-v1.txt'), 'utf8');
const lexicon = loadLexicon(text);
const candidates = text.split('\n').filter(Boolean).map((word) => lexicon.resolve(word)).filter(Boolean);

function rowsOf(mask) {
  const out = [];
  for (let r = 0; r < SIZE; r += 1) out.push(mask.slice(r * SIZE, r * SIZE + SIZE).join(''));
  return out;
}

function judge(name, rows, budget = 150_000) {
  const derived = deriveTopology(rows, { templateId: name });
  if (!derived.ok) {
    console.log(`${name}: invalid topology (${derived.violations.map((v) => v.code).join(',')})`);
    return null;
  }
  const t = derived.topology;
  const started = Date.now();
  const result = solveFill({ slots: t.slots, intersections: t.intersections, candidates, seed: 7, maxNodes: budget, qualityThreshold: 0.5 });
  const elapsed = Date.now() - started;
  if (result.status === 'solved') {
    const words = Object.values(result.solution.assignments).map((c) => c.word);
    const avgLen = (words.reduce((x, y) => x + y.length, 0) / words.length).toFixed(2);
    console.log(`${name}: SOLVED ${elapsed}ms nodes=${result.solution.nodes} score=${result.solution.score.toFixed(2)} avgLen=${avgLen}`);
    return { name, rows, topology: t, elapsed, nodes: result.solution.nodes };
  }
  console.log(`${name}: FAILED (${result.failure?.code}) ${elapsed}ms nodes=${result.failure?.nodes}`);
  return null;
}

console.log('=== proven human mask ===');
judge('human-15x15', HUMAN, 200_000);

// Structural variants: perturb the human mask with symmetric block moves.
// Legal move: add a 2-3 tall symmetric stack at a new column, or remove an
// existing interior block pair. Revalidate each variant before judging.
function lrSym(mask) {
  for (let r = 0; r < SIZE; r += 1) for (let c = 0; c < SIZE; c += 1) if (mask[idx(r, c)] !== mask[idx(r, SIZE - 1 - c)]) return false;
  return true;
}
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
function minRunOk(mask) {
  for (let i = 0; i < SIZE; i += 1) {
    if (runsOfMask(mask, i, true).some(([, l]) => l < 3)) return false;
    if (runsOfMask(mask, i, false).some(([, l]) => l < 3)) return false;
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
function allChecked(mask) {
  for (let r = 0; r < SIZE; r += 1) {
    for (let c = 0; c < SIZE; c += 1) {
      if (isBlock(mask, r, c)) continue;
      const inA = runsOfMask(mask, r, true).some(([s, l]) => c >= s && c < s + l && l >= 2);
      const inD = runsOfMask(mask, c, false).some(([s, l]) => r >= s && r < s + l && l >= 2);
      if (!inA || !inD) return false;
    }
  }
  return true;
}
function maxRun(mask) {
  let m = 0;
  for (let i = 0; i < SIZE; i += 1) {
    for (const [, l] of runsOfMask(mask, i, true)) if (l > m) m = l;
    for (const [, l] of runsOfMask(mask, i, false)) if (l > m) m = l;
  }
  return m;
}
function quickValid(mask) {
  return lrSym(mask) && minRunOk(mask) && connected(mask) && allChecked(mask) && maxRun(mask) <= 11;
}

/** Add a 2-tall symmetric stack at (row,col) quadrant position. */
function addStack(mask, row, col, height) {
  const m = mask.slice();
  for (let h = 0; h < height; h += 1) {
    const r = row + h;
    if (r >= SIZE) return null;
    if (isBlock(m, r, col)) return null;
    m[idx(r, col)] = '#';
    m[idx(r, SIZE - 1 - col)] = '#';
  }
  return quickValid(m) ? m : null;
}

/** Remove a symmetric single block (both sides), keeping corners intact. */
function removeBlock(mask, row, col) {
  if (row < 1 || row >= SIZE - 1) return null;
  const mc = SIZE - 1 - col;
  if (!isBlock(mask, row, col) || !isBlock(mask, row, mc)) return null;
  const m = mask.slice();
  m[idx(row, col)] = '.';
  m[idx(row, mc)] = '.';
  return quickValid(m) ? m : null;
}

// Random stack-planting variants of the human mask: 1-3 symmetric moves
// (add a stack / remove a block) per variant, then fill-judge each.
console.log(`=== generating stack variants of the human mask ===`);

function rngFactory(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rng = rngFactory(991337);
const tried = new Set();
const queue = [];
for (let attempt = 0; attempt < 6000 && queue.length < 60; attempt += 1) {
  let m = HUMAN.join('').split('');
  const moves = 1 + Math.floor(rng() * 3);
  for (let i = 0; i < moves; i += 1) {
    const row = Math.floor(rng() * 6);
    const col = 1 + Math.floor(rng() * 6);
    const height = 2 + Math.floor(rng() * 2);
    const next = rng() < 0.7 ? addStack(m, row, col, height) : removeBlock(m, row, col);
    if (next) m = next;
  }
  const key = m.join('');
  if (tried.has(key)) continue;
  tried.add(key);
  queue.push(m);
}

let solved = 0;
for (const [index, m] of queue.entries()) {
  const rows = rowsOf(m);
  const ok = judge(`human-v${index}`, rows, 50_000);
  if (ok) {
    solved += 1;
    console.log(`    MASK ${rows.join('|')}`);
    if (solved >= 8) break;
  }
}
console.log(`\n${solved} variant templates solved`);
