// How much a check deserves to be celebrated, and what the celebration is made of.
// Pure arithmetic: the DOM work lives in useRapture.js and the ink in celebration.css.

/** Letters on the board that were typed and are wrong. Blanks are not mistakes. */
export function countMistakes(entries, grid) {
  const wrong = new Set();
  (entries || []).forEach((entry) => {
    (entry.characters || []).forEach((character, index) => {
      const row = entry.start_y + (entry.direction === 'down' ? index : 0);
      const column = entry.start_x + (entry.direction === 'across' ? index : 0);
      const value = String(grid?.[row]?.[column] ?? '').toLowerCase();
      if (value !== '' && value !== String(character.letters).toLowerCase()) {
        wrong.add(`${row},${column}`);
      }
    });
  });
  return wrong.size;
}

/**
 * 0 nothing · 1 a quiet green lift · 2 a few sparks · 3 sparks and a note ·
 * 4 a board-wide wash · 5 a clean sweep. One clue is progress, not an occasion;
 * a big batch with no wrong letters in it is the thing worth marking.
 */
export function celebrationTier({ solved, mistakes = 0 }) {
  if (!(solved > 0)) return 0;
  if (solved === 1) return 1;
  let tier = solved >= 10 ? 4 : solved >= 5 ? 3 : solved >= 2 ? 2 : 1;
  if (mistakes === 0 && solved >= 4) tier += 1;
  return Math.min(5, tier);
}

const SPARKS_PER_CLUE = [0, 0, 3, 6, 9, 13];
const SPARK_BUDGET = 160;

/** A small deterministic generator so the same celebration is the same shape. */
function seeded(seed) {
  let state = (seed >>> 0) || 1;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

/**
 * Sparks for one departing clue. They leave the number chip and drift upward and
 * outward, with a spread that widens with the tier; the budget is shared across
 * every clue in the check so a hundred-clue sweep stays cheap.
 */
export function sparkSpecs({ tier, solved, seed = 1 }) {
  const wanted = SPARKS_PER_CLUE[tier] || 0;
  const count = Math.min(wanted, Math.floor(SPARK_BUDGET / Math.max(1, solved)));
  const random = seeded(seed);
  const reach = 26 + tier * 8;
  return Array.from({ length: count }, (_, index) => ({
    dx: Math.round((random() - 0.5) * 2 * reach),
    dy: -Math.round(24 + random() * (30 + tier * 14)),
    size: 2 + Math.round(random() * (tier >= 4 ? 3 : 2)),
    delay: Math.round(random() * 240),
    duration: Math.round(760 + random() * 520),
    tone: index % 3,
  }));
}

/** The note that goes with a big enough check. Honest about what is still wrong. */
export function raptureNote({ solved, mistakes }) {
  const clues = `${solved} ${solved === 1 ? 'clue' : 'clues'}`;
  if (mistakes === 0) return { title: clues, detail: 'No mistakes' };
  const slips = `${mistakes} ${mistakes === 1 ? 'letter' : 'letters'} to fix`;
  return { title: clues, detail: slips };
}

/** What the finish says, from how it was reached. */
export function finaleMessage({ score, checks, reveals }) {
  if (reveals === 0 && checks <= 1 && score >= 90) {
    return { grade: 'flawless', title: 'Flawless', line: 'Solved with no help and no slips.' };
  }
  if (reveals === 0 && score >= 70) {
    return { grade: 'strong', title: 'Solved', line: 'Clean work, start to finish.' };
  }
  if (reveals <= 2) {
    return { grade: 'steady', title: 'Solved', line: 'A real solve, with a few detours.' };
  }
  return { grade: 'finished', title: 'Finished', line: 'That one fought back, and you got it anyway.' };
}

/** Confetti for the finish: the number ramp itself, so the colours the reader has
 *  been learning are the ones that fall. */
export function confettiSpecs(count = 72, seed = 7) {
  const random = seeded(seed);
  return Array.from({ length: count }, (_, index) => ({
    left: Math.round(random() * 1000) / 10,
    ramp: Math.round((index / Math.max(1, count - 1)) * 1000) / 1000,
    delay: Math.round(random() * 900),
    duration: Math.round(1900 + random() * 1500),
    drift: Math.round((random() - 0.5) * 160),
    spin: Math.round((random() - 0.5) * 720),
    width: 5 + Math.round(random() * 4),
    height: 8 + Math.round(random() * 6),
  }));
}
