import { describe, expect, it } from 'vitest';
import {
  balancedRuns,
  cellCues,
  clueRampStyle,
  createClueRamp,
  entryStartingAt,
  gridShape,
  groupRuns,
  groupSizes,
  spotlightCues,
  wordsThroughSquares,
} from './boardCues';

const entry = (answer) => ({
  clue_number: 1,
  direction: 'across',
  characters: [...answer].map((letters) => ({ letters })),
});

describe('letter-track runs', () => {
  it('balances a long answer without leaving a one-box orphan', () => {
    expect(balancedRuns(0)).toEqual([]);
    expect(balancedRuns(3)).toEqual([3]);
    expect(balancedRuns(7)).toEqual([4, 3]);
    expect(balancedRuns(11)).toEqual([4, 4, 3]);
    expect(balancedRuns(13)).toEqual([5, 4, 4]);
  });

  it('groups a multi-word answer by its words, gap square included', () => {
    expect(groupSizes(entry('MISERLY'))).toEqual([4, 3]);
    expect(groupSizes(entry('ICE CREAM'))).toEqual([4, 5]);
    expect(groupSizes(entry('ICE CREAM'), 'five')).toEqual([5, 4]);
    expect(groupSizes(entry('ICE CREAM'), 'none')).toEqual([9]);
  });

  it('covers every square of the track whatever the answer looks like', () => {
    const answers = ['A', 'AX', 'MISERLY', 'ICE CREAM', 'ICE CREAM CONE', 'UP UP'];
    const modes = ['auto', 'five', 'none'];
    answers.forEach((answer) => {
      modes.forEach((mode) => {
        const cells = [...answer].length;
        const total = groupRuns(entry(answer), mode).reduce(
          (sum, run) => sum + run.size,
          0,
        );
        expect([answer, mode, total]).toEqual([answer, mode, cells]);
      });
    });
  });

  it('marks the gap between words and never the end of the track', () => {
    expect(groupRuns(entry('ICE CREAM'))).toEqual([
      { size: 4, wordEnd: true },
      { size: 5, wordEnd: false },
    ]);
    expect(groupRuns(entry('MISERLY')).map((run) => run.wordEnd)).toEqual([
      false,
      false,
    ]);
    expect(
      groupRuns(entry('ICE CREAM'), 'five').map((run) => run.wordEnd),
    ).toEqual([false, false]);
    expect(groupRuns(entry(''))).toEqual([]);
  });
});

describe('number colour ramp', () => {
  it('gives one ramp value per number, spread across the whole arc', () => {
    const ramp = createClueRamp([
      { clue_number: 7 },
      { clue_number: 3 },
      { clue_number: 7 },
    ]);
    expect(clueRampStyle(ramp, 3)).toEqual({ '--clue-ramp': '0' });
    expect(clueRampStyle(ramp, 7)).toEqual({ '--clue-ramp': '1' });

    const six = createClueRamp(
      [1, 2, 3, 4, 5, 6].map((clue_number) => ({ clue_number })),
    );
    // Rank rather than value: three of six is two fifths along, not a half.
    expect(clueRampStyle(six, 3)).toEqual({ '--clue-ramp': '0.4' });
    expect(clueRampStyle(six, 6)).toEqual({ '--clue-ramp': '1' });
  });

  it('says nothing about a number the board does not use', () => {
    const ramp = createClueRamp([{ clue_number: 1 }]);
    expect(clueRampStyle(ramp, 42)).toEqual({});
    expect(clueRampStyle(null, 1)).toEqual({});
  });

  it('finds the word opening at one square in one direction', () => {
    const entries = [
      { clue_number: 1, direction: 'across', start_x: 0, start_y: 0 },
      { clue_number: 1, direction: 'down', start_x: 0, start_y: 0 },
      { clue_number: 2, direction: 'across', start_x: 0, start_y: 4 },
    ];
    expect(entryStartingAt(entries, 0, 0, 'across')).toBe(entries[0]);
    expect(entryStartingAt(entries, 0, 0, 'down')).toBe(entries[1]);
    expect(entryStartingAt(entries, 4, 0, 'down')).toBeUndefined();
    expect(entryStartingAt(entries, 4, 0, 'up')).toBeUndefined();
    expect(entryStartingAt(null, 0, 0, 'across')).toBeUndefined();
  });
});

describe('board cues', () => {
  // Black squares are null, an unfilled square is the empty string - the shape the
  // desktop grid is built in.
  const grid = [
    ['A', 'B', 'C'],
    [null, 'D', null],
    ['', 'E', ''],
  ];

  it('opens a slot on the edge of a black square that touches a white one', () => {
    expect(cellCues(grid, 1, 0).style).toEqual({
      '--open-n': '1',
      '--open-e': '1',
      '--open-s': '1',
      '--open-w': '0',
    });
  });

  it('names the square that opens a word and not the ones inside it', () => {
    expect(cellCues(grid, 0, 0).dataStart).toBe('across');
    expect(cellCues(grid, 0, 1).dataStart).toBe('down');
    expect(cellCues(grid, 0, 2).dataStart).toBeUndefined();
    expect(cellCues(grid, 1, 1).dataStart).toBeUndefined();
  });

  it('keeps quiet off the edge of the grid', () => {
    expect(cellCues([], 0, 0)).toEqual({});
    expect(cellCues(grid, 9, 9)).toEqual({});
  });

  it('measures each word through a square from its start', () => {
    const entries = [
      { clue_number: 1, direction: 'across', start_x: 0, start_y: 0 },
      { clue_number: 1, direction: 'down', start_x: 1, start_y: 0 },
      { clue_number: 2, direction: 'across', start_x: 0, start_y: 2 },
    ];
    // Row 0 runs ABC left to right, column 1 runs B-D-E top to bottom, and
    // row 2 runs its own three-wide answer: rank 1 sits at 0, rank 2 at 1.
    const ramp = createClueRamp(entries);
    expect(spotlightCues(grid, entries, ramp, 0, 2)).toEqual({
      style: { '--spot-arank': '0', '--spot-adist': '2' },
    });
    expect(spotlightCues(grid, entries, ramp, 1, 1)).toEqual({
      style: { '--spot-drank': '0', '--spot-ddist': '1' },
    });
    expect(spotlightCues(grid, entries, ramp, 2, 1)).toEqual({
      style: {
        '--spot-arank': '1',
        '--spot-adist': '1',
        '--spot-drank': '0',
        '--spot-ddist': '2',
      },
    });
    expect(spotlightCues(grid, entries, ramp, 0, 0)).toEqual({
      style: { '--spot-arank': '0', '--spot-adist': '0' },
    });
    // A black square, a word the entries do not name, and thin air stay dark.
    expect(spotlightCues(grid, entries, ramp, 1, 0)).toEqual({});
    expect(spotlightCues(grid, [], ramp, 0, 1)).toEqual({});
    expect(spotlightCues(grid, entries, ramp, 9, 9)).toEqual({});
  });
});

describe('words through a square', () => {
  const boxes = (answer) => [...answer].map((letters) => ({ letters }));
  const entries = [
    { clue_number: 1, direction: 'across', start_x: 0, start_y: 0, characters: boxes('ABC') },
    { clue_number: 1, direction: 'down', start_x: 0, start_y: 0, characters: boxes('ADE') },
    { clue_number: 2, direction: 'across', start_x: 0, start_y: 2, characters: boxes('EFG') },
  ];

  it('counts one word on a plain square and two where a pair cross', () => {
    const counts = wordsThroughSquares(entries);
    // The opening square belongs to both 1-Across and 1-Down.
    expect(counts.get('0,0')).toBe(2);
    expect(counts.get('0,2')).toBe(1);
    expect(counts.get('1,0')).toBe(1);
    // The foot of 1-Down is the first square of 2-Across.
    expect(counts.get('2,0')).toBe(2);
    expect(counts.get('2,2')).toBe(1);
    // Three words of three squares, sharing two squares: seven in all.
    expect(counts.size).toBe(7);
  });

  it('is empty for a puzzle with no words and ignores malformed entries', () => {
    expect(wordsThroughSquares([]).size).toBe(0);
    expect(wordsThroughSquares(undefined).size).toBe(0);
    expect(wordsThroughSquares([{ direction: 'across', start_x: 0, start_y: 0 }, null]).size).toBe(0);
  });
});

describe('the grid shape the board cues are keyed on', () => {
  it('tells two same-sized puzzles apart by their black squares', () => {
    const one = [['A', null], ['B', 'C']];
    const two = [['A', 'B'], [null, 'C']];
    expect(gridShape(one)).toBe('.#/..');
    expect(gridShape(two)).toBe('../#.');
    expect(gridShape(one)).not.toBe(gridShape(two));
  });

  it('reads letters and blanks alike as open, and nothing as black', () => {
    expect(gridShape([['', 'X', undefined]])).toBe('..#');
    expect(gridShape(null)).toBe('');
  });
});
