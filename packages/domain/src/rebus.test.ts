import { describe, expect, it } from 'vitest';
import { createFixturePuzzle, indexPuzzle } from './puzzle';
import { createSession, enterRebus, selectCell } from './session';

describe('enterRebus', () => {
  it('stores a multi-letter rebus token on the selected cell and advances', () => {
    const puzzle = createFixturePuzzle();
    const index = indexPuzzle(puzzle);
    let session = selectCell(createSession(puzzle, index), index, 'cell-0-0' as never, 'across');
    session = enterRebus(session, puzzle, index, 'an');
    expect(session.entered['cell-0-0' as never]).toBe('AN');
    expect(session.selection.cellId).toBe('cell-0-1' as never);
  });

  it('rejects tokens beyond ten letters or with non-letters', () => {
    const puzzle = createFixturePuzzle();
    const index = indexPuzzle(puzzle);
    let session = selectCell(createSession(puzzle, index), index, 'cell-0-0' as never, 'across');
    const before = session;
    session = enterRebus(session, puzzle, index, 'WAYTOOLONGWORD');
    expect(session).toBe(before);
    session = enterRebus(session, puzzle, index, 'A1B');
    expect(session).toBe(before);
  });

  it('does nothing while paused', () => {
    const puzzle = createFixturePuzzle();
    const index = indexPuzzle(puzzle);
    const paused = { ...selectCell(createSession(puzzle, index), index, 'cell-0-0' as never, 'across'), paused: true };
    expect(enterRebus(paused, puzzle, index, 'AN')).toBe(paused);
  });
});
