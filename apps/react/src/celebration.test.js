import { describe, expect, it } from 'vitest';
import { celebrationTier, confettiSpecs, countMistakes, finaleMessage, raptureNote, sparkSpecs } from './celebration';
import { coilPath, springEnds, springSegments, springTension } from './springGeometry';

const entry = (answer, extra = {}) => ({
  direction: 'across',
  start_x: 0,
  start_y: 0,
  characters: [...answer].map((letters) => ({ letters })),
  ...extra,
});

describe('countMistakes', () => {
  it('counts typed wrong letters once and ignores blanks', () => {
    const across = entry('CAT');
    const down = entry('CUP', { direction: 'down' });
    const grid = [['C', 'A', ''], ['X', null, null], ['P', null, null]];
    expect(countMistakes([across, down], grid)).toBe(1);
    expect(countMistakes([across], [['c', 'a', 't']])).toBe(0);
  });
});

describe('celebrationTier', () => {
  it('celebrates nothing for nothing and little for one clue', () => {
    expect(celebrationTier({ solved: 0 })).toBe(0);
    expect(celebrationTier({ solved: 1, mistakes: 0 })).toBe(1);
  });

  it('grows with the number of clues solved at once', () => {
    const tiers = [2, 5, 10].map((solved) => celebrationTier({ solved, mistakes: 3 }));
    expect(tiers).toEqual([2, 3, 4]);
  });

  it('rewards a big clean check one step further, and a dirty one not at all', () => {
    expect(celebrationTier({ solved: 12, mistakes: 0 })).toBe(5);
    expect(celebrationTier({ solved: 12, mistakes: 2 })).toBe(4);
    expect(celebrationTier({ solved: 2, mistakes: 0 })).toBe(2);
  });
});

describe('sparkSpecs', () => {
  it('is deterministic and shares a budget across a big batch', () => {
    expect(sparkSpecs({ tier: 4, solved: 3, seed: 5 })).toEqual(sparkSpecs({ tier: 4, solved: 3, seed: 5 }));
    expect(sparkSpecs({ tier: 1, solved: 1 })).toEqual([]);
    const perClue = sparkSpecs({ tier: 5, solved: 60, seed: 1 }).length;
    expect(perClue * 60).toBeLessThanOrEqual(160);
    expect(sparkSpecs({ tier: 5, solved: 2, seed: 1 }).every((spark) => spark.dy < 0)).toBe(true);
  });
});

describe('copy', () => {
  it('is honest about mistakes', () => {
    expect(raptureNote({ solved: 12, mistakes: 0 })).toEqual({ title: '12 clues', detail: 'No mistakes' });
    expect(raptureNote({ solved: 1, mistakes: 1 })).toEqual({ title: '1 clue', detail: '1 letter to fix' });
  });

  it('grades the finish by how it was reached', () => {
    expect(finaleMessage({ score: 100, checks: 1, reveals: 0 }).grade).toBe('flawless');
    expect(finaleMessage({ score: 80, checks: 3, reveals: 0 }).grade).toBe('strong');
    expect(finaleMessage({ score: 60, checks: 4, reveals: 2 }).grade).toBe('steady');
    expect(finaleMessage({ score: 30, checks: 6, reveals: 9 }).grade).toBe('finished');
  });

  it('spreads confetti across the whole ramp', () => {
    const pieces = confettiSpecs(10, 3);
    expect(pieces[0].ramp).toBe(0);
    expect(pieces.at(-1).ramp).toBe(1);
  });
});

describe('springTension', () => {
  it('winds adjacent numbers loosely and pulls distant ones taut', () => {
    const relaxed = springTension(1);
    const stretched = springTension(40);
    expect(relaxed.taut).toBe(0);
    expect(stretched.taut).toBe(1);
    expect(stretched.coils).toBeLessThan(relaxed.coils);
    expect(stretched.radius).toBeLessThan(relaxed.radius);
    expect(springTension(4).taut).toBeGreaterThan(0);
    expect(springTension(4).taut).toBeLessThan(1);
  });
});

describe('springs', () => {
  const chip = (x, y) => ({ x, y, hw: 21, hh: 16 });

  it('leaves each chip at its edge', () => {
    const { from, to } = springEnds(chip(0, 0), chip(62, 50));
    expect(Math.abs(from.x) <= 21 && Math.abs(from.y) <= 16).toBe(true);
    expect(Math.abs(to.x - 62) <= 21 && Math.abs(to.y - 50) <= 16).toBe(true);
  });

  it('draws a coil whose ends sit on the axis and refuses a degenerate one', () => {
    const d = coilPath({ x: 0, y: 0 }, { x: 40, y: 30 }, springTension(1));
    expect(d.startsWith('M0 0L')).toBe(true);
    expect(d.endsWith('40 30')).toBe(true);
    expect(coilPath({ x: 0, y: 0 }, { x: 1, y: 1 }, springTension(1))).toBe('');
  });

  it('measures a segment as the ramp distance between its numbers', () => {
    const ramp = new Map([[1, 0], [2, 0.25], [3, 0.5], [4, 0.75], [5, 1]]);
    const chips = [chip(0, 0), chip(62, 50), chip(0, 100)];
    const segments = springSegments({ chips, numbers: [1, 2, 5], ramp, states: ['', 'active', ''], lane: 'across' });
    expect(segments.map((segment) => segment.steps)).toEqual([1, 3]);
    expect(segments[1].taut).toBeGreaterThan(segments[0].taut);
    expect(segments.map((segment) => segment.state)).toEqual(['active', 'active']);
    expect(segments[0].key).toBe('across-1-2');
  });
});
