#!/usr/bin/env node
/**
 * Fill feasibility measurement: fill curated 15x15 templates with the full
 * web2 lexicon and report timing/nodes/score. Run directly with node
 * (type stripping): node scripts/measure-fill.mjs [templateId ...]
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';

const { deriveTopology } = await import('../packages/construction/src/topology.ts');
const { curatedTemplateBank } = await import('../packages/construction/src/templateBank.ts');
const { loadLexicon } = await import('../packages/construction/src/lexicon.ts');
const { solveFill } = await import('../packages/construction/src/csp.ts');

const text = readFileSync(path.resolve('packages/construction/data/fill-lexicon-v1.txt'), 'utf8');
const lexicon = loadLexicon(text);
const words = text.split('\n').filter(Boolean);
console.log(`lexicon: ${words.length} words`);

const candidates = words.map((word) => lexicon.resolve(word)).filter(Boolean);
console.log(`candidates: ${candidates.length}`);

const wanted = process.argv.slice(2);
const templates = curatedTemplateBank().filter((t) => wanted.length === 0 || wanted.includes(t.id));

for (const template of templates) {
  const derived = deriveTopology(template.mask, { templateId: template.id });
  if (!derived.ok) {
    console.log(`${template.id}: INVALID TOPOLOGY ${derived.violations.map((v) => v.code).join(',')}`);
    continue;
  }
  const t = derived.topology;
  const lengths = t.slots.map((s) => s.length);
  const histogram = {};
  for (const len of lengths) histogram[len] = (histogram[len] ?? 0) + 1;
  console.log(`\n=== ${template.id}: ${t.entries.length} entries, ${t.intersections.length} crossings, lengths ${JSON.stringify(histogram)}`);

  const started = Date.now();
  let lastNodes = 0;
  const result = solveFill({
    slots: t.slots,
    intersections: t.intersections,
    candidates,
    seed: 7,
    maxNodes: 200_000
  }, {
    onProgress: (progress) => {
      if (progress.nodes - lastNodes >= 20_000) {
        lastNodes = progress.nodes;
        console.log(`  ...${progress.nodes} nodes, ${progress.assigned}/${t.slots.length} assigned, best ${progress.bestScore.toFixed(1)}, ${((Date.now() - started) / 1000).toFixed(1)}s`);
      }
    }
  });
  const elapsed = Date.now() - started;
  if (result.status === 'solved') {
    const words = Object.values(result.solution.assignments).map((c) => c.word);
    const avgLen = (words.reduce((a, w) => a + w.length, 0) / words.length).toFixed(2);
    console.log(`  SOLVED in ${elapsed}ms, nodes=${result.solution.nodes}, score=${result.solution.score.toFixed(1)}, avgLen=${avgLen}`);
    console.log(`  sample: ${words.slice(0, 12).join(' ')}`);
  } else {
    console.log(`  FAILED (${result.failure?.code}) in ${elapsed}ms, nodes=${result.failure?.nodes}: ${result.failure?.message}`);
  }
}
