// View-model cues for the desktop board and clue ladder. Everything here is
// presentation arithmetic: it reads the grid and the loaded entries and returns
// CSS-ready custom properties. No puzzle state is mutated.

/** Balanced runs of at most `size`, never leaving a one-box orphan: 11 becomes
 *  4/4/3 rather than 5/5/1, so the eye can count a run from either end. */
export function balancedRuns(length, size = 5) {
  const total = Math.max(0, Math.round(Number(length) || 0));
  if (total === 0) return [];
  const capacity = Math.max(1, Math.round(size));
  const groups = Math.ceil(total / capacity);
  const base = Math.floor(total / groups);
  const wider = total - base * groups;
  return Array.from(
    { length: groups },
    (_, index) => base + (index < wider ? 1 : 0),
  );
}

/** A declared separator is a character position the answer writes as a space:
 *  either a blank grid square or a rebus whose value contains one. */
export function isWordSeparator(character) {
  const value = character?.letters ?? character ?? '';
  return String(value).trim() === '';
}

/**
 * Group sizes for the letter track under a clue, in cells - the count the track is
 * rendered from, so a chunk always lines up with a square.
 * - `auto`   : break at the answer's own word gaps, then balance each word into
 *              runs of at most five; a gap square stays with the run before it.
 * - `five`   : the historical fixed run of five, kept as an explicit choice.
 * - `none`   : one continuous run.
 */
export function groupSizes(entry, mode = 'auto') {
  return groupRuns(entry, mode).map((run) => run.size);
}

/**
 * The runs with the word boundary marked, so the track can widen where the
 * answer has a real gap and stay tight inside a stretch of letters.
 */
export function groupRuns(entry, mode = 'auto') {
  const characters = Array.isArray(entry?.characters) ? entry.characters : [];
  const length = characters.length;
  if (length === 0) return [];
  if (mode === 'none') return [{ size: length, wordEnd: false }];
  if (mode !== 'auto') {
    const size = Number(mode);
    return balancedRuns(length, Number.isFinite(size) && size > 1 ? size : 5).map(
      (run) => ({ size: run, wordEnd: false }),
    );
  }
  // Words as cell spans: the letters of a word plus any gap square written after
  // it. A stretch with no letters of its own is not a word, and a track that is
  // not at least two words reads as one balanced stretch.
  const words = [];
  let letters = 0;
  let gaps = 0;
  characters.forEach((character) => {
    if (isWordSeparator(character)) {
      gaps += 1;
      return;
    }
    if (gaps > 0) {
      words.push({ letters, gaps });
      letters = 0;
      gaps = 0;
    }
    letters += 1;
  });
  words.push({ letters, gaps });
  if (words.length < 2 || words.some((word) => word.letters === 0)) {
    return balancedRuns(length, 5).map((size) => ({ size, wordEnd: false }));
  }
  const runs = [];
  words.forEach((word, wordIndex) => {
    const chunks = balancedRuns(word.letters, 5);
    chunks.forEach((size, chunkIndex) => {
      const last = chunkIndex === chunks.length - 1;
      runs.push({
        size: size + (last ? word.gaps : 0),
        // The final run is not a boundary: a trailing gap would push an
        // end-aligned track away from the edge it is supposed to sit on.
        wordEnd: last && wordIndex < words.length - 1,
      });
    });
  });
  return runs;
}

/**
 * Rank-based number→colour ramp. Crossword numbers address a *position*, shared
 * by the Across and Down clue at that square, so one rank per distinct number
 * gives the ladder anchor and the grid index the same colour: the reader learns
 * a hue once and finds the square in either place. Rank rather than value keeps
 * the ramp evenly spread for any puzzle size; a 70-number puzzle still reaches
 * both ends of the arc.
 */
export function createClueRamp(entries) {
  const numbers = [
    ...new Set(
      (entries || [])
        .map((entry) => entry?.clue_number)
        .filter((value) => Number.isFinite(value)),
    ),
  ].sort((a, b) => a - b);
  const span = numbers.length > 1 ? numbers.length - 1 : 1;
  return new Map(
    numbers.map((number, rank) => [
      number,
      Math.round((rank / span) * 1000) / 1000,
    ]),
  );
}

/** The ramp value travels as a unitless custom property so the palette (and the
 *  low-bloom tiers) stay in CSS, where theming belongs. A record of custom
 *  property names, which the stylesheets read back as `--clue-ramp`.
 * @returns {Record<string, string>}
 */
export function clueRampStyle(ramp, clueNumber) {
  const value = ramp?.get(clueNumber);
  return value === undefined ? {} : { '--clue-ramp': String(value) };
}

/** The entry opening at one square in one direction, if the puzzle has one: a
 *  gate tick on a black square names the word it opens, so the tick can wear
 *  that word's own hue rather than just its lane's colour. A length-one stub
 *  opens no word and finds no entry here, which is exactly when the tick keeps
 *  its quiet direction colour. */
export function entryStartingAt(entries, startY, startX, direction) {
  if (!Array.isArray(entries)) return undefined;
  return entries.find(
    (entry) =>
      entry?.direction === direction &&
      entry?.start_y === startY &&
      entry?.start_x === startX,
  );
}

const OPEN_SIDES = [
  ['north', 'n', -1, 0],
  ['east', 'e', 0, 1],
  ['south', 's', 1, 0],
  ['west', 'w', 0, -1],
];

const isOpen = (grid, row, column) => {
  const rows = grid?.length || 0;
  const columns = grid[0]?.length || 0;
  if (row < 0 || column < 0 || row >= rows || column >= columns) return false;
  return grid[row][column] !== null && grid[row][column] !== undefined;
};

/**
 * Board cues for one square, derived only from its neighbours:
 * - every black square that touches a white square opens a slot on that edge;
 *   the east and south edges are where a word *starts*, so CSS draws them as
 *   longer gate ticks, while the north and west edges are terminations.
 * - a white square that begins an Across or Down word is tagged so the ladder
 *   colour and the square agree about where a word may be entered.
 */
export function cellCues(grid, row, column) {
  if (!Array.isArray(grid) || !grid[row]) return {};
  const black = grid[row][column] === null;
  if (black) {
    const style = {};
    OPEN_SIDES.forEach(([, key, dy, dx]) => {
      style[`--open-${key}`] = isOpen(grid, row + dy, column + dx) ? '1' : '0';
    });
    return { style };
  }
  const across =
    !isOpen(grid, row, column - 1) && isOpen(grid, row, column + 1);
  const down = !isOpen(grid, row - 1, column) && isOpen(grid, row + 1, column);
  const starts = [across && 'across', down && 'down'].filter(Boolean);
  return {
    dataStart: starts.length ? starts.join(' ') : undefined,
    across,
    down,
  };
}
