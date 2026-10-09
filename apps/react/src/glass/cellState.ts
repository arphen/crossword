// What the glass layer knows about each square. The DOM stays the source of
// truth: the layer reads a square's classes and marks (the same ones the CSS
// board is drawn from) and packs them into twelve floats per square for the
// GPU. Animation is not computed here; each change of state is stamped with
// the moment it happened, and the shaders animate from the stamps, so the CPU
// does nothing per frame.

/** Floats per square in the cell buffer. */
export const CELL_FLOATS = 12;

/** Slots within one square's floats. */
export const SLOT = {
  x: 0,
  y: 1,
  width: 2,
  height: 3,
  flags: 4,
  /** Position along the active word, 0..1, or -1 outside it. */
  wordPos: 5,
  /** When the cursor arrived. */
  select: 6,
  /** When a letter was last typed or erased. */
  press: 7,
  /** When the check's verdict landed. */
  verdict: 8,
  /** When the square's word popped (solved in a check). */
  pop: 9,
  /** Position along the popped word, 0..1, for the sweep. */
  popPos: 10,
  /** When anything about the square last changed. */
  state: 11,
} as const;

export const FLAG = {
  BLACK: 1,
  SHADED: 2,
  CIRCLED: 4,
  REBUS: 8,
  LETTER: 16,
  CURSOR: 32,
  WORD: 64,
  CORRECT: 128,
  WRONG: 256,
  SOLVED: 512,
  SETTLED: 1024,
  NOTCH_E: 2048,
  NOTCH_S: 4096,
  FLARE: 8192,
  START: 16384,
  POP: 32768,
} as const;

/** Never happened: far enough in the past that every animation has ended. */
export const NEVER = -1000;

export interface CellFacts {
  flags: number;
  wordPos: number;
}

/** The facts the CSS board shows for one square element. */
export function readCellFacts(cell: Element, activeElement: Element | null): CellFacts {
  const classes = cell.classList;
  const style = (cell as HTMLElement).style;
  const input = cell.querySelector('input');
  let flags = 0;
  if (classes.contains('black-cell')) flags |= FLAG.BLACK;
  if (classes.contains('shaded')) flags |= FLAG.SHADED;
  if (classes.contains('circled')) flags |= FLAG.CIRCLED;
  if (classes.contains('rebus')) flags |= FLAG.REBUS;
  if (classes.contains('has-letter')) flags |= FLAG.LETTER;
  if (activeElement && cell.contains(activeElement)) flags |= FLAG.CURSOR;
  const inWord = cell.hasAttribute('data-entry-index');
  if (inWord) flags |= FLAG.WORD;
  if (input?.classList.contains('green')) flags |= FLAG.CORRECT;
  if (input?.classList.contains('red')) flags |= FLAG.WRONG;
  if (cell.hasAttribute('data-solved')) flags |= FLAG.SOLVED;
  if (cell.hasAttribute('data-solved-all')) flags |= FLAG.SETTLED;
  if (style?.getPropertyValue('--open-e').trim() === '1') flags |= FLAG.NOTCH_E;
  if (style?.getPropertyValue('--open-s').trim() === '1') flags |= FLAG.NOTCH_S;
  if (cell.hasAttribute('data-flare')) flags |= FLAG.FLARE;
  if (cell.querySelector('.clue-index')) flags |= FLAG.START;
  if (cell.hasAttribute('data-pop')) flags |= FLAG.POP;
  const position = Number.parseFloat(style?.getPropertyValue('--entry-position') || '');
  return { flags, wordPos: inWord ? (Number.isFinite(position) ? position / 100 : 0) : -1 };
}

/**
 * The cell buffer and the bookkeeping that turns changes of state into
 * stamps. `update` returns whether anything the shaders read has changed, so
 * the caller uploads only the squares that did.
 */
export class CellBook {
  data: Float32Array;
  count = 0;

  constructor(capacity = 0) {
    this.data = new Float32Array(Math.max(1, capacity) * CELL_FLOATS);
  }

  /** Start over with `count` squares at rest (layout comes from `place`). */
  reset(count: number): void {
    if (this.data.length < count * CELL_FLOATS) this.data = new Float32Array(count * CELL_FLOATS);
    this.count = count;
    for (let index = 0; index < count; index += 1) {
      const base = index * CELL_FLOATS;
      this.data.fill(0, base, base + CELL_FLOATS);
      this.data[base + SLOT.wordPos] = -1;
      for (const slot of [SLOT.select, SLOT.press, SLOT.verdict, SLOT.pop, SLOT.state]) this.data[base + slot] = NEVER;
    }
  }

  /** Where a square is, in the canvas's CSS pixels. */
  place(index: number, x: number, y: number, width: number, height: number): void {
    const base = index * CELL_FLOATS;
    this.data[base + SLOT.x] = x;
    this.data[base + SLOT.y] = y;
    this.data[base + SLOT.width] = width;
    this.data[base + SLOT.height] = height;
  }

  flags(index: number): number {
    return this.data[index * CELL_FLOATS + SLOT.flags];
  }

  /** Apply a square's facts at time `now` (seconds); stamps what began. */
  update(index: number, facts: CellFacts, now: number, popPos = 0): boolean {
    const base = index * CELL_FLOATS;
    const before = this.data[base + SLOT.flags];
    const began = facts.flags & ~before;
    const changed = facts.flags !== before || this.data[base + SLOT.wordPos] !== facts.wordPos;
    if (!changed) return false;
    if (began & FLAG.CURSOR) this.data[base + SLOT.select] = now;
    if (began & (FLAG.CORRECT | FLAG.WRONG)) this.data[base + SLOT.verdict] = now;
    if (began & FLAG.POP) {
      this.data[base + SLOT.pop] = now;
      this.data[base + SLOT.popPos] = popPos;
    }
    this.data[base + SLOT.flags] = facts.flags;
    this.data[base + SLOT.wordPos] = facts.wordPos;
    this.data[base + SLOT.state] = now;
    return true;
  }

  /** A letter was typed or erased in the square. */
  press(index: number, now: number): void {
    this.data[index * CELL_FLOATS + SLOT.press] = now;
  }

  /** The floats of one square, for a partial upload. */
  slice(index: number): Float32Array {
    return this.data.subarray(index * CELL_FLOATS, (index + 1) * CELL_FLOATS);
  }
}

/** Positions along a word for squares that popped together: their order in
 *  reading order (row, then column), spread from 0 to 1. */
export function sweepPositions(cells: Array<{ row: number; column: number }>): number[] {
  if (cells.length <= 1) return cells.map(() => 0);
  const order = cells
    .map((cell, index) => ({ ...cell, index }))
    .sort((a, b) => a.row - b.row || a.column - b.column);
  const positions = new Array<number>(cells.length).fill(0);
  order.forEach((cell, rank) => {
    positions[cell.index] = rank / (cells.length - 1);
  });
  return positions;
}
