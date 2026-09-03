#!/usr/bin/env node
/**
 * Fill-judge sampled real NYT masks per weekday with the web2 lexicon, and
 * emit the measured template bank. Output: /tmp/nyt_topo/filled.json
 *
 * Sampling: stride across each day's unique valid masks, biased toward the
 * later (modern-style) half. Each candidate is filled with the full lab
 * lexicon; survivors are ranked by fill nodes and quality.
 */
import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'node:fs';
import path from 'node:path';

const { deriveTopology } = await import('../packages/construction/src/topology.ts');
const { loadLexicon } = await import('../packages/construction/src/lexicon.ts');
const { solveFill } = await import('../packages/construction/src/csp.ts');

const MASKS = '/tmp/nyt_topo/masks';
const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const SIZE_BY_DAY = { Monday: 15, Tuesday: 15, Wednesday: 15, Thursday: 15, Friday: 15, Saturday: 15, Sunday: 21 };
const SAMPLES_PER_DAY = Number(process.env.SAMPLES ?? 40);
const NODE_BUDGET = Number(process.env.NODES ?? 60_000);
const THRESHOLD = Number(process.env.THRESH ?? 0.5);

const text = readFileSync(path.resolve('packages/construction/data/fill-lexicon-v1.txt'), 'utf8');
const lexicon = loadLexicon(text);
const candidates = text.split('\n').filter(Boolean).map((word) => lexicon.resolve(word)).filter(Boolean);
console.log(`lexicon candidates: ${candidates.length}`);
console.log(`gate: THRESHOLD=${THRESHOLD} NODE_BUDGET=${NODE_BUDGET} SAMPLES_PER_DAY=${SAMPLES_PER_DAY}`);

function maskToRows(mask, size) {
  const rows = [];
  for (let r = 0; r < size; r += 1) rows.push(mask.slice(r * size, r * size + size));
  return rows;
}

function sampleFiles(dir, count) {
  const files = readdirSync(dir).sort();
  // bias toward the last third (modern style) with a stride
  const start = Math.floor(files.length * 0.55);
  const pool = files.slice(start);
  const stride = Math.max(1, Math.floor(pool.length / count));
  const out = [];
  for (let i = 0; i < pool.length && out.length < count; i += stride) out.push(pool[i]);
  return out;
}

mkdirSync('/tmp/nyt_topo/filled', { recursive: true });
const report = {};

for (const day of DAYS) {
  const files = sampleFiles(path.join(MASKS, day), SAMPLES_PER_DAY);
  const survivors = [];
  let failed = 0;
  let invalid = 0;
  const startedAll = Date.now();
  for (const [index, file] of files.entries()) {
    const mask = readFileSync(path.join(MASKS, day, file), 'utf8').trim();
    const derived = deriveTopology(maskToRows(mask, SIZE_BY_DAY[day] ?? 15), { templateId: `${day}-${file}` });
    if (!derived.ok) { invalid += 1; continue; }
    const t = derived.topology;
    const started = Date.now();
    const result = solveFill({
      slots: t.slots,
      intersections: t.intersections,
      candidates,
      seed: 7,
      maxNodes: NODE_BUDGET
    });
    const elapsed = Date.now() - started;
    if (result.status === 'solved') {
      const words = Object.values(result.solution.assignments).map((c) => c.word);
      const avgLen = words.reduce((x, y) => x + y.length, 0) / words.length;
      // Editorial gate: staple-heavy fills only. The raw score sum is not the
      // editorial score; recompute it here from the base scores.
      const scoreSum = words.reduce((sum, word) => sum + (lexicon.resolve(word)?.score ?? 0), 0) / Math.max(1, words.length);
      if (scoreSum < THRESHOLD) {
        failed += 1;
        continue;
      }
      survivors.push({
        id: `${day.toLowerCase()}-${file.replace('.txt', '')}`,
        mask,
        elapsedMs: elapsed,
        nodes: result.solution.nodes,
        score: Number(result.solution.score.toFixed(2)),
        editorialScore: Number(scoreSum.toFixed(3)),
        avgLen: Number(avgLen.toFixed(2)),
        entries: t.entries.length,
        crossings: t.intersections.length
      });
    } else {
      failed += 1;
    }
    if ((index + 1) % 6 === 0) {
      console.log(`${day}: ${index + 1}/${files.length} judged, ${survivors.length} solved, ${((Date.now() - startedAll) / 1000).toFixed(0)}s elapsed`);
    }
  }
  survivors.sort((a, b) => a.nodes - b.nodes);
  report[day] = { sampled: files.length, solved: survivors.length, failed, invalid, survivors: survivors.slice(0, 8) };
  const gatePassed = survivors.length >= Math.ceil(files.length * 0.5);
  report[day].gate = gatePassed ? 'pass' : 'fail';
  console.log(`${day}: ${survivors.length}/${files.length} solved (failed ${failed}, invalid ${invalid}) gate=${report[day].gate}`);
  writeFileSync('/tmp/nyt_topo/filled.json', JSON.stringify(report, null, 2));
  if (!gatePassed) process.exitCode = 1;
}
writeFileSync('/tmp/nyt_topo/filled.json', JSON.stringify(report, null, 2));
console.log('DONE');
