#!/usr/bin/env node
/**
 * Build the crossword-frequency prior from the household's NYT answer corpus:
 * the top N most frequent answers (per the whole corpus), stored as
 * `word count` lines. The lexicon loader consumes this as a familiarity
 * prior; it never grants eligibility (web2 membership stays the gate).
 *
 * Output: packages/construction/data/freq-prior-v1.txt + manifest JSON.
 */
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

const FREQ = '/tmp/nyt_topo/answer_freq.json';
const OUT_DIR = path.resolve('packages/construction/data');
const VERSION = 'freq-prior-v1';
const TOP_N = 6000;
const MIN_LENGTH = 3;

const freq = JSON.parse(await readFile(FREQ, 'utf8'));
const lines = Object.entries(freq)
  .filter(([word]) => /^[A-Z]+$/.test(word) && word.length >= MIN_LENGTH)
  .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  .slice(0, TOP_N)
  .map(([word, count]) => `${word} ${count}`);

const artifact = `${lines.join('\n')}\n`;
const digest = createHash('sha256').update(artifact).digest('hex');
await mkdir(OUT_DIR, { recursive: true });
await writeFile(path.join(OUT_DIR, `${VERSION}.txt`), artifact, 'utf8');

const manifest = {
  id: VERSION,
  schemaVersion: 1,
  derivedFrom: 'Household-local NYT answer corpus (14,576 published grids), frequency of answer strings across puzzles',
  transformation: [
    'count answer strings across all puzzles',
    'keep /^[A-Z]+$/ with length >= 3',
    `keep the top ${TOP_N} by frequency`,
    'emit "WORD COUNT" lines, descending count'
  ],
  entryCount: lines.length,
  sha256: createHash('sha256').update(artifact).digest('hex'),
  emittedAt: new Date().toISOString(),
  status: 'laboratory — frequency prior only; never a clue/answer source. Private household use; excluded from public artifacts.'
};
await writeFile(path.join(OUT_DIR, `${VERSION}.json`), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
console.log(`${VERSION}: ${lines.length} entries, sha256 ${manifest.sha256.slice(0, 16)}...`);
