// The answer boxes in the clue lanes, for the glass layer. Each box mirrors a
// board square (data-cell="row,col"), so the light on it is the light on its
// square: the clue's hue entering at the first box and stepping down the
// answer as the board's spill does, the lit word's flow, and the square's own
// events (a typed letter, a verdict, a solve) stamped once in the cell buffer
// and read by both. Like the board, the boxes are read from the DOM only when
// they move.

import { laneTint, type GlassTokens } from './tint';

/** Floats per box in the box buffer. */
export const BOX_FLOATS = 12;

/** Slots within one box's floats. */
export const BOX = {
  /** Viewport rect: x, y, width, height (CSS px). */
  rect: 0,
  /** The clue's tint in its lane (linear RGB), and the box's place in the answer. */
  tint: 4,
  place: 7,
  /** The board square it mirrors (cell index, or -1), its lane (0 Across, 1
   *  Down), its flags (BOX_FLAG), the answer's length. */
  cell: 8,
  lane: 9,
  flags: 10,
  length: 11,
} as const;

export const BOX_FLAG = {
  CURSOR: 1,
  LIT: 2,
  WRONG: 4,
  RIGHT: 8,
  CROSSING: 16,
  SHADED: 32,
  /** The clue has a rank (Number colours on), so its tint is its own hue. */
  RANKED: 64,
} as const;

export interface BoxBook {
  data: Float32Array;
  count: number;
}

export function emptyBoxes(): BoxBook {
  return { data: new Float32Array(BOX_FLOATS * 64), count: 0 };
}

/**
 * Read every answer box in the lanes into `book`. `cellOf` maps "row,col" to
 * a cell index. Allocates only when the buffer has to grow (a new puzzle).
 */
export function readBoxes(root: ParentNode, tokens: GlassTokens, cellOf: (key: string) => number, book: BoxBook): BoxBook {
  const boxes = root.querySelectorAll<HTMLElement>('#across .state, #down .state');
  if (book.data.length < boxes.length * BOX_FLOATS) book.data = new Float32Array(Math.ceil(boxes.length * 1.5) * BOX_FLOATS);
  const d = book.data;
  let count = 0;
  let row: Element | null = null;
  let place = 0;
  let length = 0;
  let tint: readonly number[] = tokens.orange;
  let ranked = false;
  let lane = 0;
  for (const box of boxes) {
    const item = box.closest('li');
    if (item !== row) {
      row = item;
      place = 0;
      length = item ? item.querySelectorAll('.state').length : 1;
      lane = item?.closest('#down') ? 1 : 0;
      const rank = Number.parseFloat((item as HTMLElement | null)?.style.getPropertyValue('--clue-ramp') ?? '');
      ranked = tokens.ramp && Number.isFinite(rank);
      tint = ranked ? laneTint(tokens, lane ? 'down' : 'across', rank) : lane ? tokens.blue : tokens.orange;
    }
    const rect = box.getBoundingClientRect();
    const classes = box.classList;
    let flags = 0;
    if (classes.contains('cursor-cell')) flags |= BOX_FLAG.CURSOR;
    if (box.hasAttribute('data-entry-index')) flags |= BOX_FLAG.LIT;
    if (classes.contains('red')) flags |= BOX_FLAG.WRONG;
    if (classes.contains('green')) flags |= BOX_FLAG.RIGHT;
    if (classes.contains('intersection-cell-across') || classes.contains('intersection-cell-down')) flags |= BOX_FLAG.CROSSING;
    if (classes.contains('shaded')) flags |= BOX_FLAG.SHADED;
    if (ranked) flags |= BOX_FLAG.RANKED;
    const base = count * BOX_FLOATS;
    d[base] = rect.left;
    d[base + 1] = rect.top;
    d[base + 2] = rect.width;
    d[base + 3] = rect.height;
    d[base + 4] = tint[0];
    d[base + 5] = tint[1];
    d[base + 6] = tint[2];
    d[base + 7] = place;
    d[base + 8] = cellOf(box.getAttribute('data-cell') ?? '');
    d[base + 9] = lane;
    d[base + 10] = flags;
    d[base + 11] = length;
    place += 1;
    count += 1;
  }
  book.count = count;
  return book;
}
