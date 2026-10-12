// How much a check deserves to be celebrated, and what the celebration is made of.
// Pure arithmetic: the DOM work lives in useRapture.js and the ink in celebration.css.
// (The wrong letters a check finds come from the check itself, check_all.)

/**
 * How big the board-wide moment after a check is (the words' own fireworks
 * scale with the combo instead, combo.js): 0 nothing · 1 and 2 the words alone
 * · 3 a note · 4 a board-wide wash · 5 a clean sweep, with confetti. One clue
 * is progress, not an occasion; a big batch with no wrong letters in it is the
 * thing worth marking.
 */
export function celebrationTier({ solved, mistakes = 0 }) {
  if (!(solved > 0)) return 0;
  if (solved === 1) return 1;
  let tier = solved >= 10 ? 4 : solved >= 5 ? 3 : solved >= 2 ? 2 : 1;
  if (mistakes === 0 && solved >= 4) tier += 1;
  return Math.min(5, tier);
}

/** A small deterministic generator so the same celebration is the same shape. */
function seeded(seed) {
  let state = (seed >>> 0) || 1;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 4294967296;
  };
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
