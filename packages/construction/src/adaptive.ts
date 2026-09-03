/**
 * Adaptive (learner-profile) scoring for fill candidates.
 *
 * Implements the four-component pedagogical score from
 * docs/crossword research.md, adapted to the deterministic engine:
 *
 *   1. Spaced-repetition urgency (FSRS-style retrievability vs R* = 0.88)
 *   2. Zone-of-proximal-development surprisal alignment
 *      (effective surprisal decays with crossing letters already placed)
 *   3. Intersection affordance (branching factor of each letter position)
 *   4. Lexical recency / fatigue penalty
 *
 * Deterministic and local: the profile is household data, never a network
 * input. The score is a *preference multiplier* — eligibility stays the
 * lexicon's job.
 */

export type LearnerMemoryState = Readonly<{
  /** Inherent word difficulty, 1..10. */
  difficulty: number;
  /** Memory stability in days. */
  stability: number;
  /** Last exposure, epoch milliseconds. */
  lastReviewAtMs: number;
}>;

export type LearnerProfile = Readonly<{
  /** Ability estimate; 0 ~ novice, 1 ~ expert. Drives target surprisal. */
  theta: number;
  memory: Readonly<Record<string, LearnerMemoryState>>;
  /** Now, epoch milliseconds (injected for determinism). */
  nowMs: number;
}>;

export type WordCandidateStat = Readonly<{
  lemma: string;
  /** Base surprisal (information content), nats or bits. */
  baseSurprisal: number;
}>;

export type AdaptiveWeights = Readonly<{
  srs: number;
  zone: number;
  affordance: number;
  fatigue: number;
}>;

export const DEFAULT_WEIGHTS: AdaptiveWeights = { srs: 0.4, zone: 0.35, affordance: 0.15, fatigue: 0.1 };

const TARGET_RETENTION = 0.88;
/** FSRS-style decay constant from the research document. */
const DECAY_FACTOR = Math.pow(0.9, -1 / 0.5) - 1;

/** FSRS-style retrievability: decays with elapsed time over stability. */
export function computeRetrievability(state: LearnerMemoryState, nowMs: number): number {
  const deltaDays = Math.max(0, (nowMs - state.lastReviewAtMs) / 86_400_000);
  return Math.pow(1 + DECAY_FACTOR * (deltaDays / Math.max(0.1, state.stability)), -0.5);
}

/**
 * Effective surprisal decays linearly with the share of the word's letters
 * already fixed by crossings: recognition replaces recall.
 */
export function effectiveSurprisal(baseSurprisal: number, wordLength: number, filledCrossLetters: number): number {
  const decayRatio = 1 - filledCrossLetters / Math.max(1, wordLength);
  return baseSurprisal * Math.max(0, decayRatio);
}

/**
 * Pedagogical preference for one candidate in one slot context.
 * Higher is better; the fill engine consumes it as its value-ordering score.
 */
export function adaptiveScore(
  candidate: WordCandidateStat,
  filledCrossLetters: number,
  profile: LearnerProfile,
  /** Map (position, letter) -> branching factor for the slot. */
  letterBranching: (position: number, letter: string) => number,
  weights: AdaptiveWeights = DEFAULT_WEIGHTS
): number {
  const lemma = candidate.lemma.toUpperCase();
  const state = profile.memory[lemma];

  // 1. Spaced-repetition urgency: boost words near the retention floor.
  let srsTerm = 0.25; // exploration incentive for unencountered vocabulary
  let fatigueTerm = 0;
  if (state) {
    const retrievability = computeRetrievability(state, profile.nowMs);
    srsTerm = Math.max(0, TARGET_RETENTION - retrievability);
    const deltaHours = Math.max(0, (profile.nowMs - state.lastReviewAtMs) / 3_600_000);
    if (deltaHours < 24) fatigueTerm = 1 / Math.max(1, deltaHours);
  }

  // 2. ZPD surprisal alignment.
  const effective = effectiveSurprisal(candidate.baseSurprisal, lemma.length, filledCrossLetters);
  const targetSurprisal = 3 + 2 * profile.theta;
  const zoneTerm = -Math.abs(effective - targetSurprisal);

  // 3. Intersection affordance: log-branching of each letter position.
  let affordance = 0;
  for (let index = 0; index < lemma.length; index += 1) {
    affordance += Math.log(letterBranching(index, lemma[index]!) + 1);
  }
  affordance /= Math.max(1, lemma.length);

  return (
    weights.srs * srsTerm
    + weights.zone * zoneTerm
    + weights.affordance * affordance
    - weights.fatigue * fatigueTerm
  );
}

/**
 * Blend a base crossword-quality score (0..1) with a normalized adaptive
 * preference: `final = (1 - w) * base + w * adaptive01`.
 */
export function blendScore(baseScore: number, adaptive01: number, adaptWeight = 0.35): number {
  const w = Math.min(1, Math.max(0, adaptWeight));
  const base = Math.min(1, Math.max(0, baseScore));
  const adaptive = Math.min(1, Math.max(0, adaptive01));
  return (1 - w) * base + w * adaptive;
}
