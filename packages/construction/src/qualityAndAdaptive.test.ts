import { describe, expect, it } from 'vitest';

import { adaptiveScore, blendScore, computeRetrievability, DEFAULT_WEIGHTS, effectiveSurprisal } from './adaptive';
import { loadLexicon } from './lexicon';
import { scoreFill } from './quality';

const DAY_MS = 86_400_000;

describe('FSRS retrievability', () => {
  it('decays with elapsed time and never goes below zero', () => {
    const state = { difficulty: 5, stability: 3, lastReviewAtMs: 0 };
    expect(computeRetrievability(state, DAY_MS)).toBeGreaterThan(computeRetrievability(state, 10 * DAY_MS));
    expect(computeRetrievability(state, 1000 * DAY_MS)).toBeGreaterThanOrEqual(0);
  });

  it('starts near one for fresh reviews', () => {
    const state = { difficulty: 5, stability: 10, lastReviewAtMs: 0 };
    expect(computeRetrievability(state, 1000)).toBeGreaterThan(0.99);
  });
});

describe('effective surprisal', () => {
  it('decays linearly with crossing letters placed', () => {
    expect(effectiveSurprisal(6, 6, 0)).toBe(6);
    expect(effectiveSurprisal(6, 6, 3)).toBeCloseTo(3);
    expect(effectiveSurprisal(6, 6, 6)).toBe(0);
  });
});

describe('adaptive score', () => {
  const profile = {
    theta: 0.5,
    nowMs: 3 * DAY_MS,
    memory: {
      // Last seen 30 days ago with 1-day stability: retrievability far below
      // the 0.88 target, so the word is dramatically overdue for review.
      CAT: { difficulty: 4, stability: 1, lastReviewAtMs: -27 * DAY_MS }
    }
  };

  it('prefers a word due for review over a fresh word', () => {
    const branching = () => 3;
    const due = adaptiveScore({ lemma: 'CAT', baseSurprisal: 4 }, 0, profile, branching, DEFAULT_WEIGHTS);
    // Fresh/unencountered word gets the 0.25 exploration term; the due word's
    // SRS urgency term is 0.88 - retrievability. For the due word to win,
    // its retrievability must be low (it is: 0.5 days elapsed / 2 day stability).
    const fresh = adaptiveScore({ lemma: 'DOG', baseSurprisal: 4 }, 0, profile, branching, DEFAULT_WEIGHTS);
    expect(due).toBeGreaterThan(fresh);
  });

  it('penalizes words seen within the last hours (fatigue)', () => {
    const branching = () => 3;
    const tiredProfile = { theta: 0.5, nowMs: 3 * DAY_MS, memory: { CAT: { difficulty: 4, stability: 900, lastReviewAtMs: 3 * DAY_MS - 3_600_000 } } };
    const tired = adaptiveScore({ lemma: 'CAT', baseSurprisal: 4 }, 0, tiredProfile, branching, DEFAULT_WEIGHTS);
    const rested = adaptiveScore({ lemma: 'DOG', baseSurprisal: 4 }, 0, tiredProfile, branching, DEFAULT_WEIGHTS);
    expect(tired).toBeLessThan(rested);
  });
});

describe('blendScore', () => {
  it('keeps the base score at zero adaptive weight and honors the weight', () => {
    expect(blendScore(0.8, 0.2, 0)).toBeCloseTo(0.8);
    expect(blendScore(0.8, 0.2, 0.5)).toBeCloseTo(0.5);
  });
});

describe('fill quality scoring', () => {
  it('rewards staple-heavy, balanced fills over glue-heavy ones', () => {
    const staple = scoreFill({
      assignments: [
        { word: 'PETALS', score: 0.9, crossings: 3 },
        { word: 'ORATES', score: 0.85, crossings: 3 },
        { word: 'SNARLS', score: 0.8, crossings: 2 },
        { word: 'TRENDY', score: 0.85, crossings: 2 }
      ],
      whiteCellCount: 60,
      crossingCellCount: 30
    });
    const glue = scoreFill({
      assignments: [
        { word: 'OLE', score: 0.3, crossings: 3 },
        { word: 'ELEVEN', score: 0.35, crossings: 3 },
        { word: 'ANA', score: 0.2, crossings: 2 },
        { word: 'ETTE', score: 0.25, crossings: 2 }
      ],
      whiteCellCount: 60,
      crossingCellCount: 30
    });
    expect(staple.score).toBeGreaterThan(glue.score);
    expect(staple.score).toBeGreaterThan(0);
    expect(staple.score).toBeLessThanOrEqual(1);
  });
});

describe('lexicon loader', () => {
  it('loads a sorted word list with provenance and resolves surfaces', () => {
    const lexicon = loadLexicon('ACE\nACTOR\nADO\nZEPHYR\n');
    expect(lexicon.wordCount).toBe(4);
    expect(lexicon.provenance.license).toBe('Public domain');
    const candidate = lexicon.resolve(' actor ');
    expect(candidate?.word).toBe('ACTOR');
    expect(candidate?.lexemeId).toBe('web2:ACTOR');
    expect(lexicon.resolve('TO')).toBeUndefined();
    expect(lexicon.wordsOfLength(3)).toEqual(['ACE', 'ADO']);
    expect(lexicon.contains('ZEPHYR')).toBe(true);
  });
});
