// The frame a puzzle is drawn in: the bounding box of the squares its words
// use. The upstream feed reports every grid as square, so a rectangular puzzle
// arrives padded with whole rows or columns of black squares, on any side; the
// server now trims them, and this does the same for puzzles stored before it
// did (the offline cache keeps what it was given). Pure: no DOM, no state.

const cellsOf = (entry) => {
  const length = Array.isArray(entry?.characters) ? entry.characters.length : 0;
  return { length, across: entry?.direction === 'across' };
};

/**
 * The used frame of a puzzle and its entries moved into it.
 * @returns {{ entries: any[], width: number, height: number, dx: number, dy: number, trimmed: boolean }}
 *   `dx`/`dy` are how far every square moved left/up. When nothing is padded
 *   the input entries come back as they are (same array, same objects).
 */
export function trimPuzzleFrame({ entries, width, height }) {
  const list = Array.isArray(entries) ? entries : [];
  let top = Infinity;
  let left = Infinity;
  let bottom = -Infinity;
  let right = -Infinity;
  for (const entry of list) {
    const { length, across } = cellsOf(entry);
    if (!length || !Number.isInteger(entry.start_x) || !Number.isInteger(entry.start_y)) continue;
    const lastX = entry.start_x + (across ? length - 1 : 0);
    const lastY = entry.start_y + (across ? 0 : length - 1);
    left = Math.min(left, entry.start_x);
    top = Math.min(top, entry.start_y);
    right = Math.max(right, lastX);
    bottom = Math.max(bottom, lastY);
  }
  const unchanged = { entries, width, height, dx: 0, dy: 0, trimmed: false };
  if (!Number.isFinite(top)) return unchanged;
  const usedWidth = right - left + 1;
  const usedHeight = bottom - top + 1;
  const reportedWidth = Number.isInteger(width) && width > 0 ? width : usedWidth;
  const reportedHeight = Number.isInteger(height) && height > 0 ? height : usedHeight;
  if (left === 0 && top === 0 && usedWidth === reportedWidth && usedHeight === reportedHeight) return unchanged;
  return {
    entries: list.map((entry) => (
      Number.isInteger(entry?.start_x) && Number.isInteger(entry?.start_y)
        ? { ...entry, start_x: entry.start_x - left, start_y: entry.start_y - top }
        : entry
    )),
    width: usedWidth,
    height: usedHeight,
    dx: left,
    dy: top,
    trimmed: true,
  };
}

/**
 * A replay manifest moved into the same frame: its squares keep their ids and
 * only their coordinates change, and squares outside the frame (padding, all
 * black) are dropped. A manifest whose geometry does not fit the cut (an open
 * square outside it) is returned as null rather than mis-mapped, and anything
 * that is not a cell-list manifest passes through untouched.
 */
export function moveManifestIntoFrame(manifest, { dx, dy, width, height }) {
  if (!manifest || !Array.isArray(manifest.cells)) return manifest ?? null;
  const cells = [];
  for (const cell of manifest.cells) {
    const row = cell?.row - dy;
    const column = cell?.column - dx;
    const inside = row >= 0 && column >= 0 && row < height && column < width;
    if (!inside) {
      if (cell?.block !== true) return null;
      continue;
    }
    cells.push({ ...cell, row, column });
  }
  return { ...manifest, width, height, cells };
}
