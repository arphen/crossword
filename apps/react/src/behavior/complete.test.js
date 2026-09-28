// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { createOptions } from './desktop';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function completeMethod() {
  return createOptions({
    axios: {},
    socket: {},
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    requestAnimationFrame,
    cancelAnimationFrame,
  }).methods.markCurrentPuzzleAsComplete;
}

it('does not finish a personal journal when the completion confirmation is cancelled', async () => {
  vi.stubGlobal('confirm', vi.fn(() => false));
  const saved = vi.fn();
  const load = vi.fn();
  const journalFinish = vi.fn();
  const app = {
    currentPuzzleMetadata: { date: '260926' },
    getPuzzleId: vi.fn(() => '260926'),
    getCurrentDay: vi.fn(() => 'saturday'),
    markPuzzleSolved: saved,
    loadCrossword: load,
  };

  const result = await completeMethod().call(app, journalFinish);

  expect(result).toBe(false);
  expect(saved).not.toHaveBeenCalled();
  expect(journalFinish).not.toHaveBeenCalled();
  expect(load).not.toHaveBeenCalled();
});

it('finishes the journal after confirmation and before switching to another puzzle', async () => {
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('alert', vi.fn());
  const order = [];
  const app = {
    currentPuzzleMetadata: { date: '260926' },
    getPuzzleId: vi.fn(() => '260926'),
    getCurrentDay: vi.fn(() => 'saturday'),
    markPuzzleSolved: vi.fn(async () => order.push('saved')),
    loadCrossword: vi.fn(() => order.push('next-puzzle')),
  };

  const result = await completeMethod().call(app, async () => order.push('journal-finished'));

  expect(result).toBe(true);
  expect(order).toEqual(['saved', 'journal-finished', 'next-puzzle']);
});
