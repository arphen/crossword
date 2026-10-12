// Points and the combo: what a clean run of solved words is worth. Pure
// arithmetic, so the rules can be read and tested on their own; the behaviour
// (behavior/desktop.js) keeps the state and the view plays the beats back.
//
// Every word a check solves for the first time is one more link in the combo
// and is worth its length times the combo's multiplier. The combo carries
// across checks for as long as the board stays clean; one wrong letter (or a
// reveal) breaks it, and each wrong letter costs a little. Within a check the
// words land first and the break last, so a run can still climb before it
// shatters. The original score (100, less penalties) is unchanged and still
// drives the board's light; points are the reward layer on top.

/** Combo tiers: the link a tier starts at and what each word in it is worth. */
export const COMBO_TIERS = [
  { from: 0, multiplier: 1 },
  { from: 3, multiplier: 1.5 },
  { from: 5, multiplier: 2 },
  { from: 8, multiplier: 3 },
  { from: 12, multiplier: 4 },
  { from: 18, multiplier: 5 },
];

/** Points cost per wrong letter in a check. */
export const MISTAKE_COST = 15;

/** Which tier a combo of `links` words sits in (0 for no combo). */
export function comboTier(links) {
  let tier = 0;
  COMBO_TIERS.forEach((step, index) => {
    if (links >= step.from) tier = index;
  });
  return tier;
}

export function comboMultiplier(links) {
  return COMBO_TIERS[comboTier(links)].multiplier;
}

/** How hot the run is, 0 (no combo) to 1 (top tier), eased so the first links
 *  already show; the board's light and the fireworks read it. */
export function comboHeat(links) {
  const top = COMBO_TIERS.at(-1).from;
  return Math.round(Math.sqrt(Math.min(1, Math.max(0, links) / top)) * 1000) / 1000;
}

/** A word's base value: longer answers are worth more. */
export function wordValue(length) {
  return 40 + 10 * Math.max(0, Math.round(length || 0));
}

export function newComboState() {
  return { points: 0, combo: 0, best: 0, awarded: [] };
}

/**
 * Apply one check. `gained` are the words this check solved, in the order they
 * are played back ({ key, length }); `wrong` is how many wrong letters the
 * check found. Returns the next state and the beats to play: one per gained
 * word, then a break when the check had wrong letters.
 * A word that was already rewarded once (solved, unsolved by an edit, solved
 * again) still gets its beat but earns nothing and does not extend the combo.
 */
export function scoreCheck(state, { gained = [], wrong = 0 } = {}) {
  const current = state || newComboState();
  const awarded = new Set(current.awarded);
  let { points, combo, best } = current;
  const beats = [];
  for (const word of gained) {
    if (awarded.has(word.key)) {
      beats.push({ kind: 'word', key: word.key, repeat: true, combo, multiplier: comboMultiplier(combo), tier: comboTier(combo), tierUp: false, points: 0, total: points });
      continue;
    }
    awarded.add(word.key);
    const before = comboTier(combo);
    combo += 1;
    best = Math.max(best, combo);
    const multiplier = comboMultiplier(combo);
    const earned = Math.round(wordValue(word.length) * multiplier);
    points += earned;
    beats.push({ kind: 'word', key: word.key, repeat: false, combo, multiplier, tier: comboTier(combo), tierUp: comboTier(combo) > before, points: earned, total: points });
  }
  if (wrong > 0) {
    const penalty = Math.min(points, wrong * MISTAKE_COST);
    points -= penalty;
    beats.push({ kind: 'break', reason: 'mistake', lost: combo, wrong, penalty, total: points });
    combo = 0;
  }
  return { state: { points, combo, best, awarded: [...awarded] }, beats };
}

/** A reveal ends the run without costing points. */
export function breakCombo(state, reason = 'reveal') {
  const current = state || newComboState();
  return {
    state: { ...current, combo: 0 },
    beat: { kind: 'break', reason, lost: current.combo, wrong: 0, penalty: 0, total: current.points },
  };
}

/** Revealing the whole puzzle means it was not solved: the points go to zero
 *  and every word counts as already paid, so no later check can earn any. */
export function forfeitCombo(state, keys = []) {
  const current = state || newComboState();
  return {
    state: { points: 0, combo: 0, best: current.best, awarded: [...new Set([...current.awarded, ...keys])] },
    beat: { kind: 'break', reason: 'reveal-all', lost: current.combo, wrong: 0, penalty: current.points, total: 0 },
  };
}
