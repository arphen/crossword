import * as fc from 'fast-check';
import { describe, expect, it } from 'vitest';

import { solveFill, type FillCandidate } from './csp';

const WORDS = [
  'AAA', 'AAB', 'AAC', 'ABA', 'ABB', 'ABC', 'ACA', 'ACB', 'ACC',
  'BAA', 'BAB', 'BAC', 'BBA', 'BBB', 'BBC', 'BCA', 'BCB', 'BCC',
  'CAA', 'CAB', 'CAC', 'CBA', 'CBB', 'CBC', 'CCA', 'CCB', 'CCC'
] as const;

const candidateSpecs = fc.uniqueArray(
  fc.record({
    word: fc.constantFrom(...WORDS),
    score: fc.integer({ min: -20, max: 20 })
  }),
  { minLength: 1, maxLength: 8, selector: (spec) => spec.word }
);

type CrossingCase = {
  candidates: readonly FillCandidate[];
  leftPosition: number;
  rightPosition: number;
};

const crossingCases = fc.record({
  candidates: candidateSpecs.map((specs) => specs.map((spec) => ({
    word: spec.word,
    score: spec.score,
    lexemeId: `generated:${spec.word}`,
    sourceIds: ['generated']
  }))),
  leftPosition: fc.integer({ min: 0, max: 2 }),
  rightPosition: fc.integer({ min: 0, max: 2 })
}) satisfies fc.Arbitrary<CrossingCase>;

function bestCrossingScore(
  candidates: readonly FillCandidate[],
  leftPosition: number,
  rightPosition: number
): number | undefined {
  let best: number | undefined;
  for (const left of candidates) {
    for (const right of candidates) {
      if (left.word === right.word || left.word[leftPosition] !== right.word[rightPosition]) continue;
      const score = left.score + right.score;
      best = best === undefined ? score : Math.max(best, score);
    }
  }
  return best;
}

function solveCrossing(testCase: CrossingCase, candidates: readonly FillCandidate[] = testCase.candidates) {
  return solveFill({
    slots: [
      { id: 'left', length: 3 },
      { id: 'right', length: 3 }
    ],
    intersections: [{
      slotId: 'left',
      position: testCase.leftPosition,
      otherSlotId: 'right',
      otherPosition: testCase.rightPosition
    }],
    candidates,
    seed: 17
  });
}

describe('generated CSP invariants', () => {
  it('matches a brute-force oracle for small crossing candidate bags', () => {
    fc.assert(fc.property(crossingCases, (testCase) => {
      const expectedScore = bestCrossingScore(
        testCase.candidates,
        testCase.leftPosition,
        testCase.rightPosition
      );
      const result = solveCrossing(testCase);

      if (expectedScore === undefined) {
        expect(result.status).toBe('failed');
        expect(result.failure?.code).toBe('unsatisfiable');
        return;
      }

      expect(result.status).toBe('solved');
      if (result.status !== 'solved') return;
      const left = result.solution?.assignments.left;
      const right = result.solution?.assignments.right;
      expect(left).toBeDefined();
      expect(right).toBeDefined();
      if (!left || !right || !result.solution) return;
      expect(left.word).not.toBe(right.word);
      expect(left.word[testCase.leftPosition]).toBe(right.word[testCase.rightPosition]);
      expect(result.solution.score).toBe(expectedScore);
    }), { numRuns: 180 });
  });

  it('does not depend on the input order of candidates', () => {
    fc.assert(fc.property(crossingCases, (testCase) => {
      expect(solveCrossing(testCase)).toEqual(
        solveCrossing(testCase, [...testCase.candidates].reverse())
      );
    }), { numRuns: 120 });
  });
});