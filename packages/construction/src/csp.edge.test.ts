import { describe, expect, it } from 'vitest';

import { solveFill, solveFillAsync, type FillCandidate, type FillRequest } from './csp';

const candidate = (word: string, score = 1): FillCandidate => ({
  word,
  score,
  lexemeId: `edge:${word}`,
  sourceIds: ['edge-fixture']
});

const underfilledRequest = (): FillRequest => ({
  slots: Array.from({ length: 5 }, (_, index) => ({ id: `slot-${index}`, length: 3 })),
  intersections: [],
  candidates: ['AAA', 'AAB', 'AAC', 'AAD'].map((word) => candidate(word))
});

describe('CSP edge contracts', () => {
  it('allows a valid theme lock to provide a candidate outside the lexicon bag', () => {
    const result = solveFill({
      slots: [{ id: 'theme', length: 3 }, { id: 'crossing', length: 3 }],
      intersections: [{ slotId: 'theme', position: 0, otherSlotId: 'crossing', otherPosition: 0 }],
      candidates: [candidate('COT', 2)],
      lockedWords: { theme: 'cat' }
    });

    expect(result.status).toBe('solved');
    if (result.status !== 'solved' || !result.solution) return;
    expect(result.solution.assignments.theme?.word).toBe('cat');
    expect(result.solution.assignments.crossing?.word).toBe('COT');
  });

  it.each([
    { name: 'unknown slot', lockedWords: { missing: 'CAT' } as Record<string, string> },
    { name: 'invalid characters', lockedWords: { theme: 'CA1' } as Record<string, string> },
    { name: 'wrong length', lockedWords: { theme: 'CATS' } as Record<string, string> }
  ])('rejects an invalid theme lock: $name', ({ lockedWords }) => {
    const result = solveFill({
      slots: [{ id: 'theme', length: 3 }],
      intersections: [],
      candidates: [candidate('CAT')],
      lockedWords
    });

    expect(result.status).toBe('failed');
    expect(result.failure?.code).toBe('invalid-request');
    expect(result.failure?.nodes).toBe(0);
  });

  it('keeps async progress coherent while yielding through a deep search', async () => {
    const progress: Array<{ nodes: number; assigned: number; openSlots: number }> = [];
    const result = await solveFillAsync(underfilledRequest(), {
      onProgress: (event) => progress.push({
        nodes: event.nodes,
        assigned: event.assigned,
        openSlots: event.openSlots
      })
    });

    expect(result.status).toBe('failed');
    expect(result.failure?.code).toBe('unsatisfiable');
    expect(progress.length).toBeGreaterThan(32);
    expect(progress.every((event) => event.assigned + event.openSlots === 5)).toBe(true);
    expect(progress.every((event, index) => index === 0 || event.nodes > progress[index - 1]!.nodes)).toBe(true);
  });

  it('reports an async resource limit without publishing a partial solution', async () => {
    const progress: number[] = [];
    const result = await solveFillAsync({
      ...underfilledRequest(),
      maxNodes: 8
    }, {
      onProgress: (event) => progress.push(event.nodes)
    });

    expect(result).toEqual({
      status: 'failed',
      failure: {
        code: 'resource-limit',
        message: 'Fill search reached its node budget',
        nodes: 9
      }
    });
    expect(progress.at(-1)).toBe(8);
  });
});