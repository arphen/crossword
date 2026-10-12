// When each part of a check is played back. A check is computed in one go,
// but showing it in one frame is what made the board lurch: every verdict,
// row, spark and spring at once. The sequence spreads it over a short
// moment instead: the solved words pop one after another, in reading order
// and quickly enough that a big check is still a single flourish, then the
// letters that are right in unfinished words settle in, and any mistakes land
// last, as one blow. Pure timing: the hook (useRapture.js) carries it out.

/** Gap between two solved words: unhurried for a few, brisk for a sweep, so
 *  the whole run stays under about two seconds. */
export function wordStep(count) {
  if (!(count > 1)) return 0;
  return Math.round(Math.min(165, Math.max(34, 1700 / count)));
}

const LEAD_MS = 70;
const SETTLE_GAP_MS = 140;
const BREAK_GAP_MS = 220;
const RIPPLE_MS = 7;
const RIPPLE_SPAN_MS = 360;
const CRACK_STEP_MS = 38;
const CRACK_SPAN_MS = 420;
/** How long a popped row takes to rise and dissolve before the ladder closes. */
export const ASCEND_MS = 820;

const parseCell = (key) => key.split(',').map(Number);

/** One step of the sequence: a word popping, a ripple of settled letters, or
 *  the mistakes landing (whose cells carry their crack delay).
 * @typedef {{ at: number, type: 'word'|'cells'|'break', key?: string, index?: number,
 *   cells?: Array<[string, string, number?]> }} SequenceEvent */

/**
 * @param {object} input
 * @param {Array<{key: string, cells: string[]}>} input.words  solved words in
 *   play order, each with its squares as `row,column` keys
 * @param {Array<[string, 'green'|'red'|'blank']>} input.verdicts  every
 *   checked square and its verdict
 * @param {object | null} [input.breakBeat]  the combo break, if the check had
 *   wrong letters
 * @returns {{ events: SequenceEvent[], wordAt: Map<string, number>, releaseAt: number, end: number }}
 */
export function planSequence({ words = [], verdicts = [], breakBeat = null }) {
  /** @type {SequenceEvent[]} */
  const events = [];
  const wordAt = new Map();
  const step = wordStep(words.length);
  const painted = new Set();
  const verdictOf = new Map(verdicts);

  words.forEach((word, index) => {
    const at = LEAD_MS + index * step;
    wordAt.set(word.key, at);
    const cells = word.cells
      .filter((cell) => !painted.has(cell) && verdictOf.get(cell) === 'green')
      .map((cell) => /** @type {[string, string]} */ ([cell, 'green']));
    cells.forEach(([cell]) => painted.add(cell));
    events.push({ at, type: 'word', key: word.key, index, cells });
  });
  const lastWord = words.length ? LEAD_MS + (words.length - 1) * step : 0;

  // Right letters in words that are not finished yet: a quick ripple in
  // reading order once the words have had their moment.
  const settleStart = words.length ? lastWord + SETTLE_GAP_MS : LEAD_MS;
  const rest = verdicts
    .filter(([cell, verdict]) => verdict === 'green' && !painted.has(cell))
    .map(([cell]) => cell)
    .sort((a, b) => {
      const [ra, ca] = parseCell(a);
      const [rb, cb] = parseCell(b);
      return ra - rb || ca - cb;
    });
  const ripple = rest.length > 1 ? Math.min(RIPPLE_MS, RIPPLE_SPAN_MS / (rest.length - 1)) : 0;
  // Grouped per frame-ish slice so a long ripple is a handful of events.
  let settleEnd = settleStart;
  const slices = new Map();
  rest.forEach((cell, index) => {
    const at = Math.round(settleStart + index * ripple);
    const slice = Math.floor(at / 16) * 16;
    if (!slices.has(slice)) slices.set(slice, []);
    slices.get(slice).push(/** @type {[string, string]} */ ([cell, 'green']));
    settleEnd = Math.max(settleEnd, at);
  });
  slices.forEach((cells, at) => events.push({ at: Math.max(at, settleStart), type: 'cells', cells }));

  // Mistakes last, as one blow that cracks outward from the first of them.
  let breakEnd = 0;
  const wrong = verdicts.filter(([, verdict]) => verdict === 'red').map(([cell]) => cell);
  if (wrong.length || breakBeat) {
    const breakAt = (rest.length ? settleEnd : words.length ? lastWord : 0) + (words.length || rest.length ? BREAK_GAP_MS : LEAD_MS);
    const [r0, c0] = wrong.length ? parseCell(wrong[0]) : [0, 0];
    const cells = wrong.map((cell) => {
      const [r, c] = parseCell(cell);
      const delay = Math.min(CRACK_SPAN_MS, Math.max(Math.abs(r - r0), Math.abs(c - c0)) * CRACK_STEP_MS);
      return /** @type {[string, string, number]} */ ([cell, 'red', delay]);
    });
    events.push({ at: breakAt, type: 'break', cells });
    breakEnd = breakAt + CRACK_SPAN_MS + 500;
  }

  events.sort((a, b) => a.at - b.at);
  const releaseAt = words.length ? lastWord + ASCEND_MS + 60 : 0;
  const end = Math.max(releaseAt, settleEnd + 200, breakEnd);
  return { events, wordAt, releaseAt, end };
}
