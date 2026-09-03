#!/usr/bin/env node
/**
 * Build the versioned fill-lexicon artifact for original construction.
 *
 * Source: the system dictionary `/usr/share/dict/web2` (Webster's Second
 * International word list, 1934), which is in the public domain. The artifact
 * is a plain sorted word list; the scorer and staples live in
 * `packages/construction/src/lexicon.ts`.
 *
 * The build is deterministic: the same source produces a byte-identical
 * artifact, and both source and artifact digests are recorded in the emitted
 * manifest so the provenance ledger can pin them.
 */
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';

const SOURCE_PATH = '/usr/share/dict/web2';
const OUT_DIR = path.resolve('packages/construction/data');
const ARTIFACT_VERSION = 'fill-lexicon-v1';
const MIN_LENGTH = 3;
const MAX_LENGTH = 15;

function sha256(value) {
  return createHash('sha256').update(value).digest('hex');
}

const raw = await readFile(SOURCE_PATH, 'utf8');
const sourceDigest = sha256(raw);

const words = [...new Set(
  raw
    .split('\n')
    .map((line) => line.trim().toUpperCase())
    .filter((word) => /^[A-Z]+$/.test(word) && word.length >= MIN_LENGTH && word.length <= MAX_LENGTH)
)].sort();

if (words.length < 100_000) {
  throw new Error(`Source dictionary produced only ${words.length} words; refusing to emit a thin lexicon`);
}

const artifact = `${words.join('\n')}\n`;
const artifactDigest = sha256(artifact);

await mkdir(OUT_DIR, { recursive: true });
await writeFile(path.join(OUT_DIR, `${ARTIFACT_VERSION}.txt`), artifact, 'utf8');

const manifest = {
  id: ARTIFACT_VERSION,
  schemaVersion: 1,
  source: {
    path: SOURCE_PATH,
    title: "Webster's Second International word list (web2)",
    license: 'Public domain',
    licenseNote: 'Published 1934; distributed by macOS as /usr/share/dict/web2.',
    sha256: sourceDigest
  },
  transformation: [
    'trim lines',
    'uppercase',
    'keep /^[A-Z]+$/ only',
    `keep lengths ${MIN_LENGTH}-${MAX_LENGTH}`,
    'deduplicate',
    'sort ascending'
  ],
  minLength: MIN_LENGTH,
  maxLength: MAX_LENGTH,
  wordCount: words.length,
  artifact: {
    file: `packages/construction/data/${ARTIFACT_VERSION}.txt`,
    sha256: artifactDigest
  },
  emittedAt: new Date().toISOString(),
  status: 'laboratory — production use still requires the M2.1 owner source review'
};

await writeFile(path.join(OUT_DIR, `${ARTIFACT_VERSION}.json`), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

console.log(`${ARTIFACT_VERSION}: ${words.length} words`);
console.log(`source sha256  ${sourceDigest}`);
console.log(`artifact sha256 ${artifactDigest}`);
