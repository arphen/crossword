#!/usr/bin/env node
/**
 * Fill performance gate (review P1: reconciles the deleted
 * fillFeasibility.test.ts as a classified performance lane, not a unit test).
 *
 * Fills the calibration template (human-15x15) and two archive-measured
 * masks with the full lab lexicon under a node budget; exits non-zero if any
 * template fails or exceeds its time budget. Evidence replaces intuition.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';

const { deriveTopology } = await import('../packages/construction/src/topology.ts');
const { solveFill } = await import('../packages/construction/src/csp.ts');
const { loadLexicon } = await import('../packages/construction/src/lexicon.ts');

const HUMAN = [
  '....#....#.....', '....#....#.....', '....#....#.....', '...........#...',
  '####...#...#...', '......#......##', '.....#....#....', '.....#...#.....',
  '....#....#.....', '##......#......', '...#...#...####', '...#...........',
  '.....#....#....', '.....#....#....', '.....#....#....'
];

const CASES = [
  { id: 'human-15x15', rows: HUMAN, maxNodes: 30_000, timeBudgetMs: 15_000 },
  { id: 'monday-00805', maskFile: '/tmp/nyt_topo/masks/Monday/00805.txt', maxNodes: 20_000, timeBudgetMs: 20_000, optional: true },
  { id: 'monday-01254', maskFile: '/tmp/nyt_topo/masks/Monday/01254.txt', maxNodes: 20_000, timeBudgetMs: 20_000, optional: true }
];

const text = readFileSync(path.resolve('packages/construction/data/fill-lexicon-v1.txt'), 'utf8');
const lexicon = loadLexicon(text);
const candidates = text.split('\n').filter(Boolean).map((word) => lexicon.resolve(word)).filter(Boolean);

let failures = 0;
for (const entry of CASES) {
  let mask;
  if (entry.rows) mask = entry.rows.join('');
  else {
    try {
      mask = readFileSync(entry.maskFile, 'utf8').trim();
    } catch {
      console.log(`${entry.id}: SKIP (archive mask unavailable — run scripts/extract-nyt-topology.py first)`);
      continue;
    }
  }
  const rows = [];
  for (let r = 0; r < 15; r += 1) rows.push(mask.slice(r * 15, r * 15 + 15));
  const derived = deriveTopology(rows, { templateId: entry.id });
  if (!derived.ok) {
    console.log(`${entry.id}: FAIL (invalid topology: ${derived.violations.map((v) => v.code).join(',')})`);
    failures += 1;
    continue;
  }
  const started = Date.now();
  const result = solveFill({
    slots: derived.topology.slots,
    intersections: derived.topology.intersections,
    candidates,
    seed: 7,
    maxNodes: entry.maxNodes
  });
  const elapsed = Date.now() - started;
  if (result.status !== 'solved') {
    console.log(`${entry.id}: FAIL (${result.failure?.code}, nodes=${result.failure?.nodes}, ${elapsed}ms)`);
    failures += 1;
    continue;
  }
  const slow = elapsed > entry.timeBudgetMs;
  console.log(`${entry.id}: solved ${elapsed}ms nodes=${result.solution.nodes} score=${result.solution.score.toFixed(1)}${slow ? ` — OVER BUDGET (${entry.timeBudgetMs}ms)` : ''}`);
  if (slow) failures += 1;
}

if (failures > 0) {
  console.log(`fill perf gate: ${failures} failure(s)`);
  process.exit(1);
}
console.log('fill perf gate: pass');
