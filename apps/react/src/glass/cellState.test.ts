// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { CELL_FLOATS, CellBook, FLAG, NEVER, SLOT, readCellFacts, sweepPositions } from './cellState';

const at = (book: CellBook, index: number, slot: number) => book.data[index * CELL_FLOATS + slot];

describe('the cell book', () => {
  it('starts every square at rest', () => {
    const book = new CellBook();
    book.reset(3);
    expect(book.count).toBe(3);
    expect(at(book, 2, SLOT.wordPos)).toBe(-1);
    expect(at(book, 2, SLOT.select)).toBe(NEVER);
    expect(at(book, 2, SLOT.flags)).toBe(0);
  });

  it('places squares and grows to fit', () => {
    const book = new CellBook(1);
    book.reset(4);
    book.place(3, 10, 20, 30, 40);
    expect([...book.slice(3).slice(0, 4)]).toEqual([10, 20, 30, 40]);
  });

  it('stamps the moment each state begins, and only then', () => {
    const book = new CellBook();
    book.reset(1);
    expect(book.update(0, { flags: FLAG.LETTER, wordPos: -1 }, 1)).toBe(true);
    expect(book.update(0, { flags: FLAG.LETTER, wordPos: -1 }, 2)).toBe(false);
    book.update(0, { flags: FLAG.LETTER | FLAG.CURSOR | FLAG.WORD, wordPos: 0.5 }, 3);
    expect(at(book, 0, SLOT.select)).toBe(3);
    expect(at(book, 0, SLOT.wordPos)).toBe(0.5);
    // Still the cursor a moment later: the arrival keeps its first stamp.
    book.update(0, { flags: FLAG.LETTER | FLAG.CURSOR, wordPos: -1 }, 4);
    expect(at(book, 0, SLOT.select)).toBe(3);
    book.update(0, { flags: FLAG.LETTER | FLAG.CORRECT | FLAG.POP, wordPos: -1 }, 5, 0.25);
    expect([at(book, 0, SLOT.verdict), at(book, 0, SLOT.pop), at(book, 0, SLOT.popPos), at(book, 0, SLOT.state)]).toEqual([5, 5, 0.25, 5]);
  });

  it('records a key press without touching the state', () => {
    const book = new CellBook();
    book.reset(1);
    book.press(0, 7);
    expect(at(book, 0, SLOT.press)).toBe(7);
    expect(at(book, 0, SLOT.state)).toBe(NEVER);
  });
});

describe('sweep positions', () => {
  it('runs along a word in reading order', () => {
    expect(sweepPositions([{ row: 0, column: 2 }, { row: 0, column: 0 }, { row: 0, column: 1 }])).toEqual([1, 0, 0.5]);
    expect(sweepPositions([{ row: 3, column: 4 }])).toEqual([0]);
    expect(sweepPositions([])).toEqual([]);
  });
});

describe('reading a square from the board', () => {
  afterEach(() => document.body.replaceChildren());

  it('reads the same marks the CSS board is drawn from', () => {
    document.body.innerHTML = `
      <div class="grid-cell shaded circled has-letter" data-entry-index="2" data-solved="across" style="--entry-position: 50%">
        <span class="clue-index">4</span><input class="green" />
      </div>
      <div class="grid-cell black-cell" style="--open-e: 1; --open-s: 0" data-flare="e"></div>`;
    const [square, black] = [...document.querySelectorAll('.grid-cell')];
    const input = square.querySelector('input');
    const facts = readCellFacts(square, input);
    for (const flag of [FLAG.SHADED, FLAG.CIRCLED, FLAG.LETTER, FLAG.WORD, FLAG.CORRECT, FLAG.SOLVED, FLAG.START, FLAG.CURSOR]) {
      expect(facts.flags & flag).toBe(flag);
    }
    expect(facts.flags & FLAG.SETTLED).toBe(0);
    expect(facts.wordPos).toBe(0.5);
    const dark = readCellFacts(black, input);
    expect(dark.flags).toBe(FLAG.BLACK | FLAG.NOTCH_E | FLAG.FLARE);
    expect(dark.wordPos).toBe(-1);
  });
});
