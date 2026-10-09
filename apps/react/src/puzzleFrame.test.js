import { describe, expect, it } from 'vitest';
import { moveManifestIntoFrame, trimPuzzleFrame } from './puzzleFrame';

const boxes = (answer) => [...answer].map((letters) => ({ letters }));
// CAT across row 0, CAD down column 0, DOG across row 2: a 3x3 frame.
const entries = (dx = 0, dy = 0) => [
  { clue_number: 1, direction: 'across', start_x: dx, start_y: dy, characters: boxes('CAT') },
  { clue_number: 1, direction: 'down', start_x: dx, start_y: dy, characters: boxes('CAD') },
  { clue_number: 3, direction: 'across', start_x: dx, start_y: dy + 2, characters: boxes('DOG') },
];

describe('puzzle frame', () => {
  it('leaves a grid with no padding exactly as it is', () => {
    const list = entries();
    const frame = trimPuzzleFrame({ entries: list, width: 3, height: 3 });
    expect(frame.trimmed).toBe(false);
    expect(frame.entries).toBe(list);
    expect([frame.width, frame.height, frame.dx, frame.dy]).toEqual([3, 3, 0, 0]);
  });

  it('cuts a black column on the left and shifts every word with it', () => {
    const frame = trimPuzzleFrame({ entries: entries(1, 0), width: 4, height: 4 });
    expect(frame.trimmed).toBe(true);
    expect([frame.width, frame.height, frame.dx, frame.dy]).toEqual([3, 3, 1, 0]);
    expect(frame.entries.map((entry) => [entry.start_x, entry.start_y])).toEqual([[0, 0], [0, 0], [0, 2]]);
  });

  it('cuts trailing rows and columns, and padding on every side at once', () => {
    expect(trimPuzzleFrame({ entries: entries(), width: 5, height: 3 })).toMatchObject({ width: 3, height: 3, dx: 0, dy: 0, trimmed: true });
    expect(trimPuzzleFrame({ entries: entries(2, 1), width: 6, height: 6 })).toMatchObject({ width: 3, height: 3, dx: 2, dy: 1, trimmed: true });
  });

  it('never mutates the entries it was given', () => {
    const list = entries(1, 1);
    trimPuzzleFrame({ entries: list, width: 5, height: 5 });
    expect(list[0]).toMatchObject({ start_x: 1, start_y: 1 });
  });

  it('keeps quiet about an empty or malformed puzzle', () => {
    expect(trimPuzzleFrame({ entries: [], width: 3, height: 3 }).trimmed).toBe(false);
    expect(trimPuzzleFrame({ entries: undefined }).trimmed).toBe(false);
  });
});

describe('manifest in the trimmed frame', () => {
  const cell = (row, column, block = false) => ({ id: `c-${row}-${column}`, row, column, block });
  it('moves open squares, drops black padding and keeps every id', () => {
    const manifest = { schemaVersion: 1, width: 4, height: 3, cells: [cell(0, 0, true), cell(0, 1), cell(0, 2), cell(0, 3, true)], entries: [] };
    const moved = moveManifestIntoFrame(manifest, { dx: 1, dy: 0, width: 3, height: 3 });
    expect(moved.width).toBe(3);
    expect(moved.cells).toEqual([
      { id: 'c-0-1', row: 0, column: 0, block: false },
      { id: 'c-0-2', row: 0, column: 1, block: false },
      { id: 'c-0-3', row: 0, column: 2, block: true },
    ]);
  });

  it('refuses to cut through an open square', () => {
    const manifest = { cells: [cell(0, 0)], entries: [] };
    expect(moveManifestIntoFrame(manifest, { dx: 1, dy: 0, width: 3, height: 3 })).toBeNull();
    expect(moveManifestIntoFrame(null, { dx: 1, dy: 0, width: 3, height: 3 })).toBeNull();
  });
});
