import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import {
  sealPuzzleDocumentV2,
  validatePuzzleDocumentV2,
  type PuzzleDocumentV2,
} from './puzzleV2.js';

const fixtureUrl = new URL('../../../tests/fixtures/personalized-review-v2.json', import.meta.url);

it('accepts the deterministic synthetic review candidate emitted by the Python host builder', async () => {
  const puzzle: unknown = JSON.parse(readFileSync(fixtureUrl, 'utf8'));

  expect(puzzle).toMatchObject({
    schemaVersion: 2,
    quality: { verdict: 'review' },
  });
  expect(await validatePuzzleDocumentV2(puzzle)).toEqual({ valid: true, issues: [] });

  const smallFloatDraft = structuredClone(puzzle) as Omit<PuzzleDocumentV2, 'integrity'>;
  const mutableCrossing = (smallFloatDraft as unknown as {
    crossingSupport: {
      version: string;
      edges: { score: number }[];
      minimumScore: number;
      meanScore: number;
    };
  }).crossingSupport;
  mutableCrossing.version = 'simulated-support-estimate-v1';
  for (const edge of mutableCrossing.edges) edge.score = 1e-7;
  mutableCrossing.minimumScore = 1e-7;
  mutableCrossing.meanScore = 1e-7;

  const resealedSmallFloat = await sealPuzzleDocumentV2(smallFloatDraft);
  expect(resealedSmallFloat.integrity.value).toBe(
    'sha256:5aa01bc48f330747694dce978c837199087a8dc8cb9fbb159e01355a142db583',
  );
  expect(await validatePuzzleDocumentV2(resealedSmallFloat)).toEqual({ valid: true, issues: [] });
});
