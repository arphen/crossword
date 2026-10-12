// What the glass layer knows about each square. The DOM stays the source of
// truth: the layer reads a square's classes and marks (the same ones the CSS
// board is drawn from) and packs them into twelve floats per square for the
// GPU. Animation is not computed here; each change of state is stamped with
// the moment it happened, and the shaders animate from the stamps, so the CPU
// does nothing per frame. Each square also carries the hues of the words
// through it (or, on a black square, of the words its notches open), worked
// out from the board's own colour tokens (tint.ts).

/** Floats per square in the cell buffer. */
export const CELL_FLOATS = 20;

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
  /** The Across word's tint (linear RGB) and the square's distance from that
   *  word's first square, or -1 for none. On a black square: the east gate
   *  tick's tint, and 0 when the tick is lit. */
  across: 12,
  /** The same for the Down word (on a black square: the south tick). */
  down: 16,
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
  /** The Across / Down word through the square is solved. */
  SOLVED_A: 65536,
  SOLVED_D: 131072,
} as const;

/** Never happened: far enough in the past that every animation has ended. */
export const NEVER = -1000;

export interface CellFacts {
  flags: number;
  wordPos: number;
}

/** The colour cues the CSS board publishes on a square (boardCues.js): the
 *  ranks of the words through it and how far along each it sits, or, on a
 *  black square, the ranks of the words its gate ticks open. */
export interface CellCues {
  acrossRank: number | null;
  acrossDistance: number | null;
  downRank: number | null;
  downDistance: number | null;
}

export function readCellCues(cell: Element): CellCues {
  const style = (cell as HTMLElement).style;
  const num = (name: string) => {
    const value = Number.parseFloat(style?.getPropertyValue(name) ?? '');
    return Number.isFinite(value) ? value : null;
  };
  if (cell.classList.contains('black-cell')) {
    return { acrossRank: num('--gate-across'), acrossDistance: null, downRank: num('--gate-down'), downDistance: null };
  }
  return {
    acrossRank: num('--spot-arank'),
    acrossDistance: num('--spot-adist'),
    downRank: num('--spot-drank'),
    downDistance: num('--spot-ddist'),
  };
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
  const solved = cell.getAttribute('data-solved');
  if (solved !== null) {
    flags |= FLAG.SOLVED;
    if (solved.includes('across')) flags |= FLAG.SOLVED_A;
    if (solved.includes('down')) flags |= FLAG.SOLVED_D;
  }
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
      this.data[base + SLOT.across + 3] = -1;
      this.data[base + SLOT.down + 3] = -1;
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

  /** Set the tint and distance of the square's word in one lane (`slot` is
   *  SLOT.across or SLOT.down); returns whether anything changed. */
  tint(index: number, slot: number, rgb: readonly number[] | null, distance: number): boolean {
    const base = index * CELL_FLOATS + slot;
    const d = this.data;
    const r = rgb ? rgb[0] : 0;
    const g = rgb ? rgb[1] : 0;
    const b = rgb ? rgb[2] : 0;
    const at = rgb ? distance : -1;
    if (d[base] === Math.fround(r) && d[base + 1] === Math.fround(g) && d[base + 2] === Math.fround(b) && d[base + 3] === at) return false;
    d[base] = r;
    d[base + 1] = g;
    d[base + 2] = b;
    d[base + 3] = at;
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
