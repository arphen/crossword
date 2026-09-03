import { describe, expect, it } from 'vitest';

import { applyLearnerPreferences } from './constructPuzzle';

const DAY_MS = 86_400_000;

const candidate = (word: string, score: number) => ({
  word,
  score,
  lexemeId: `lex:${word}`,
  sourceIds: ['fixture']
});

describe('applyLearnerPreferences', () => {
  it('returns candidates unchanged in order when no profile is given', () => {
    const input = [candidate('CAT', 0.5), candidate('DOG', 0.7)];
    const result = applyLearnerPreferences(input, undefined);
    expect(result.map((c) => c.word)).toEqual(['CAT', 'DOG']);
    expect(result[0]!.score).toBe(0.5);
  });

  it('lifts a due-for-review word over an equal-staple word', () => {
    const profile = {
      theta: 0.5,
      nowMs: 30 * DAY_MS,
      memory: {
        // Both words have identical base scores; CAT is dramatically overdue.
        CAT: { difficulty: 4, stability: 1, lastReviewAtMs: -27 * DAY_MS }
      }
    };
    const input = [candidate('CAT', 0.5), candidate('DOG', 0.5)];
    const result = applyLearnerPreferences(input, profile);
    expect(result[0]!.word).toBe('CAT');
    expect(result[0]!.score).toBeGreaterThan(result[1]!.score);
  });

  it('penalizes a word seen within the fatigue window', () => {
    const profile = {
      theta: 0.5,
      nowMs: 30 * DAY_MS,
      memory: {
        // Seen an hour ago with huge stability: retrievable, fatiguing.
        CAT: { difficulty: 4, stability: 900, lastReviewAtMs: 30 * DAY_MS - 3_600_000 }
      }
    };
    const input = [candidate('CAT', 0.5), candidate('DOG', 0.5)];
    const result = applyLearnerPreferences(input, profile);
    // The function re-scores without reordering; the fatigued word must
    // score strictly below its equal-staple twin.
    const cat = result.find((c) => c.word === 'CAT')!;
    const dog = result.find((c) => c.word === 'DOG')!;
    expect(cat.score).toBeLessThan(dog.score);
  });

  it('keeps scores inside 0..1 and preserves determinism', () => {
    const profile = {
      theta: 0.9,
      nowMs: 5 * DAY_MS,
      memory: { CAT: { difficulty: 2, stability: 3, lastReviewAtMs: DAY_MS } }
    };
    const input = [candidate('CAT', 0.9), candidate('XYLOPHONE', 0.05)];
    const first = applyLearnerPreferences(input, profile);
    const second = applyLearnerPreferences(input, profile);
    expect(first).toEqual(second);
    for (const entry of first) {
      expect(entry.score).toBeGreaterThanOrEqual(0);
      expect(entry.score).toBeLessThanOrEqual(1);
    }
  });
});
