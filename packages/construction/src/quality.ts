/**
 * Deterministic fill-quality scoring.
 *
 * Components mirror the editorial soft objectives in docs/plans/02: crossing
 * fairness, answer-length band, staple (non-glue) share, vocabulary spread,
 * and long-answer interest. All inputs come from the accepted fill; nothing
 * here is a hard gate — the recipe's qualityThreshold consumes the score.
 */

export type QualityInputs = Readonly<{
  /** Slots with their assigned words and staple scores (0..1 each). */
  assignments: readonly {
    word: string;
    score: number;
    crossings: number;
  }[];
  /** Total white cells in the grid. */
  whiteCellCount: number;
  /** Total crossing cells (each counted once). */
  crossingCellCount: number;
}>;

export type QualityComponents = Readonly<{
  /** 0..1; how evenly crossings distribute across slots. */
  crossingFairness: number;
  /** 0..1; peak near a 4.8-5.2 average answer length. */
  lengthBand: number;
  /** 0..1; share of words scoring above the glue line. */
  stapleQuality: number;
  /** 0..1; share of slots at least 7 letters long. */
  longAnswerShare: number;
  /** 0..1; fraction of white cells that are checked. */
  checkedShare: number;
}>;

export type QualityScore = Readonly<{
  score: number;
  components: QualityComponents;
}>;

const GLUE_LINE = 0.45;

export function scoreFill(inputs: QualityInputs): QualityScore {
  const { assignments, whiteCellCount, crossingCellCount } = inputs;
  if (assignments.length === 0 || whiteCellCount === 0) {
    return { score: 0, components: emptyComponents() };
  }

  const crossingCounts = assignments.map((assignment) => assignment.crossings);
  const maxCrossings = Math.max(1, ...crossingCounts);
  const mean = crossingCounts.reduce((sum, value) => sum + value, 0) / crossingCounts.length;
  const variance = crossingCounts.reduce((sum, value) => sum + (value - mean) ** 2, 0) / crossingCounts.length;
  const crossingFairness = Math.max(0, 1 - Math.sqrt(variance) / Math.max(1, mean + 1));

  const averageLength = assignments.reduce((sum, a) => sum + a.word.length, 0) / assignments.length;
  const lengthDistance = Math.abs(averageLength - 5);
  const lengthScore = Math.max(0, 1 - lengthDistance / 2.2);
  const lengthBandBonus = averageLength >= 4.4 && averageLength <= 5.8 ? 0.08 : 0;

  const glueShare = assignments.filter((assignment) => assignment.score < GLUE_LINE).length / assignments.length;
  const stapleScore = 1 - glueShare;

  const longShare = assignments.filter((assignment) => assignment.word.length >= 7).length / assignments.length;
  const longScore = longShare >= 0.08 && longShare <= 0.4 ? 1 : Math.max(0, 1 - Math.abs(longShare - 0.24) * 2.5);

  const checkedShare = Math.min(1, crossingCellCount / Math.max(1, whiteCellCount));

  const components: QualityComponents = {
    crossingFairness,
    lengthBand: lengthScore + lengthBandBonus > 1 ? 1 : lengthScore + lengthBandBonus,
    stapleQuality: stapleScore,
    longAnswerShare: longScore,
    checkedShare
  };

  const score =
    0.28 * components.stapleQuality +
    0.24 * components.lengthBand +
    0.2 * components.crossingFairness +
    0.16 * components.longAnswerShare +
    0.12 * components.checkedShare;

  return { score, components };
}

function emptyComponents(): QualityComponents {
  return {
    crossingFairness: 0,
    lengthBand: 0,
    stapleQuality: 0,
    longAnswerShare: 0,
    checkedShare: 0
  };
}
