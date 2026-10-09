import { describe, expect, it } from 'vitest';
import {
  breakCombo,
  comboHeat,
  comboMultiplier,
  comboTier,
  MISTAKE_COST,
  newComboState,
  scoreCheck,
  wordValue,
} from './combo';

const words = (...lengths) => lengths.map((length, index) => ({ key: `across-${index + 1}`, length }));

describe('combo tiers', () => {
  it('climbs from x1 to x5 as the run grows', () => {
    expect([0, 1, 2, 3, 4, 5, 7, 8, 11, 12, 17, 18, 40].map(comboMultiplier)).toEqual([1, 1, 1, 1.5, 1.5, 2, 2, 3, 3, 4, 4, 5, 5]);
    expect(comboTier(0)).toBe(0);
    expect(comboTier(18)).toBe(5);
  });

  it('heats from nothing to full at the top tier', () => {
    expect(comboHeat(0)).toBe(0);
    expect(comboHeat(18)).toBe(1);
    expect(comboHeat(40)).toBe(1);
    expect(comboHeat(4)).toBeGreaterThan(0.4);
  });

  it('values a longer word more', () => {
    expect(wordValue(3)).toBe(70);
    expect(wordValue(15)).toBeGreaterThan(wordValue(5));
  });
});

describe('scoring a check', () => {
  it('pays each new word at the multiplier its link reaches', () => {
    const { state, beats } = scoreCheck(newComboState(), { gained: words(3, 3, 3), wrong: 0 });
    // Links 1 and 2 are x1, link 3 is the first x1.5.
    expect(beats.map((beat) => beat.points)).toEqual([70, 70, 105]);
    expect(beats.map((beat) => beat.combo)).toEqual([1, 2, 3]);
    expect(beats.map((beat) => beat.tierUp)).toEqual([false, false, true]);
    expect(state).toMatchObject({ points: 245, combo: 3, best: 3 });
  });

  it('carries the combo across clean checks', () => {
    const first = scoreCheck(newComboState(), { gained: words(4, 4), wrong: 0 });
    const second = scoreCheck(first.state, { gained: [{ key: 'down-9', length: 4 }], wrong: 0 });
    expect(second.beats[0]).toMatchObject({ combo: 3, multiplier: 1.5, points: 120 });
  });

  it('lets the words land before a mistake breaks the run', () => {
    const start = scoreCheck(newComboState(), { gained: words(5, 5, 5, 5), wrong: 0 }).state;
    const { state, beats } = scoreCheck(start, { gained: [{ key: 'down-2', length: 5 }], wrong: 2 });
    expect(beats.map((beat) => beat.kind)).toEqual(['word', 'break']);
    expect(beats[0]).toMatchObject({ combo: 5, multiplier: 2 });
    expect(beats[1]).toMatchObject({ lost: 5, wrong: 2, penalty: 2 * MISTAKE_COST });
    expect(state.combo).toBe(0);
    expect(state.best).toBe(5);
    expect(state.points).toBe(beats[1].total);
  });

  it('never takes points below zero', () => {
    const { state, beats } = scoreCheck(newComboState(), { gained: [], wrong: 9 });
    expect(state.points).toBe(0);
    expect(beats).toEqual([{ kind: 'break', reason: 'mistake', lost: 0, wrong: 9, penalty: 0, total: 0 }]);
  });

  it('pays a word only the first time it is solved', () => {
    const first = scoreCheck(newComboState(), { gained: words(3), wrong: 0 });
    const again = scoreCheck(first.state, { gained: words(3), wrong: 0 });
    expect(again.beats[0]).toMatchObject({ repeat: true, points: 0, combo: 1 });
    expect(again.state.points).toBe(first.state.points);
    expect(again.state.combo).toBe(1);
  });

  it('does not mutate the state it was given', () => {
    const start = newComboState();
    scoreCheck(start, { gained: words(3), wrong: 1 });
    expect(start).toEqual(newComboState());
  });
});

describe('a reveal', () => {
  it('ends the run and keeps the points', () => {
    const run = scoreCheck(newComboState(), { gained: words(3, 3, 3), wrong: 0 }).state;
    const { state, beat } = breakCombo(run);
    expect(state).toMatchObject({ combo: 0, points: run.points, best: 3 });
    expect(beat).toMatchObject({ kind: 'break', reason: 'reveal', lost: 3, penalty: 0 });
  });
});
