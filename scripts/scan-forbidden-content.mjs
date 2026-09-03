#!/usr/bin/env node
// Forbidden-content scanner skeleton (docs/plans/04 §Content and legal
// release gate; backlog PR 3).
//
// Scope: the DEPLOYABLE graph only — apps/, packages/, and apps/web/dist/
// when present. src/crossword (the private Flask continuity bridge) is
// explicitly EXEMPT: it is a local-only surface, never a release artifact.
// Patterns and exemptions live in scripts/forbidden-content.json so the
// list grows without code edits. Exit 1 on any non-exempt hit.

import { readFileSync, readdirSync, statSync, existsSync, writeFileSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = fileURLToPath(new URL('.', import.meta.url));
const repoRoot = resolve(scriptDir, '..');
const configPath = join(repoRoot, 'scripts', 'forbidden-content.json');

const args = process.argv.slice(2);
const reportIndex = args.indexOf('--report');
const reportPath = reportIndex >= 0 ? args[reportIndex + 1] : undefined;

const config = JSON.parse(readFileSync(configPath, 'utf8'));
const patterns = config.patterns.map((pattern) => ({
  ...pattern,
  matcher: new RegExp(pattern.regex, pattern.flags ?? '')
}));

const roots = ['apps', 'packages'];
if (existsSync(join(repoRoot, 'apps', 'web', 'dist'))) roots.push(join('apps', 'web', 'dist'));

const SKIP_DIRS = new Set(['node_modules', '.git', '.vite', '.npm-cache', '__pycache__', '.pytest_cache', 'coverage', 'test-results', 'playwright-report']);
const MAX_BYTES = 12 * 1024 * 1024;

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stats = statSync(full);
    if (stats.isDirectory()) {
      if (!SKIP_DIRS.has(entry)) yield* walk(full);
    } else if (stats.isFile() && stats.size <= MAX_BYTES) {
      yield full;
    }
  }
}

function isExempt(relativePath, patternId) {
  return (config.exemptions ?? []).some((exemption) => {
    const applies = relativePath === exemption.path || relativePath.startsWith(`${exemption.path}/`);
    return applies && (exemption.patterns ?? []).includes(patternId);
  });
}

const hits = [];
let scanned = 0;

for (const rootDir of roots) {
  const absoluteRoot = join(repoRoot, rootDir);
  if (!existsSync(absoluteRoot)) continue;
  for (const filePath of walk(absoluteRoot)) {
    const buffer = readFileSync(filePath);
    if (buffer.includes(0)) continue; // binary
    const text = buffer.toString('utf8');
    scanned += 1;
    const relativePath = relative(repoRoot, filePath);
    const lines = text.split(/\r?\n/);
    for (const pattern of patterns) {
      lines.forEach((line, index) => {
        if (!pattern.matcher.test(line)) return;
        hits.push({
          file: relativePath,
          line: index + 1,
          patternId: pattern.id,
          excerpt: line.trim().slice(0, 160),
          exempt: isExempt(relativePath, pattern.id)
        });
      });
    }
  }
}

const violations = hits.filter((hit) => !hit.exempt);
const exemptHits = hits.filter((hit) => hit.exempt);

for (const hit of violations) {
  console.log(`VIOLATION ${hit.file}:${hit.line} [${hit.patternId}] ${hit.excerpt}`);
}
for (const hit of exemptHits) {
  console.log(`exempt    ${hit.file}:${hit.line} [${hit.patternId}] ${hit.excerpt}`);
}
console.log(`scanned ${scanned} files under ${roots.join(', ')}: ${violations.length} violation(s), ${exemptHits.length} exempt hit(s)`);

if (reportPath) {
  writeFileSync(reportPath, JSON.stringify({
    generatedAt: new Date().toISOString(),
    roots,
    scannedFiles: scanned,
    violations,
    exemptHits,
    clean: violations.length === 0
  }, null, 2));
}

process.exit(violations.length === 0 ? 0 : 1);
