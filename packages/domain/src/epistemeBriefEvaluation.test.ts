import { describe, expect, it } from 'vitest';
import {
  canonicalEvaluationJson,
  createEpistemeBriefEvaluationFixture,
  evaluateEpistemeBriefFixture,
  EPISTEME_BRIEF_EVALUATION_FIXTURE_VERSION,
  EPISTEME_BRIEF_EVALUATION_VERSION
} from './epistemeBriefEvaluation';

describe('episteme brief evaluation fixture', () => {
  it('compares explicit seek and avoid profiles while reporting bounded retrieval metrics', () => {
    const fixture = createEpistemeBriefEvaluationFixture();
    const report = evaluateEpistemeBriefFixture(fixture);
    const seek = report.profiles.find((item) => item.label === 'seek-sound');
    const avoid = report.profiles.find((item) => item.label === 'avoid-sound');

    expect(report.evaluationVersion).toBe(EPISTEME_BRIEF_EVALUATION_VERSION);
    expect(report.fixtureVersion).toBe(EPISTEME_BRIEF_EVALUATION_FIXTURE_VERSION);
    expect(seek?.metrics).toMatchObject({
      selectedCount: 8,
      duplicateCandidateCount: 0,
      duplicateAnswerCount: 0,
      answerDiversityRatio: 1,
      broadFloorRequested: 3,
      broadFloorSatisfied: true,
      laneCounts: { 'explicit-preference': 2, broad: 6 }
    });
    expect(avoid?.metrics).toMatchObject({
      selectedCount: 8,
      duplicateCandidateCount: 0,
      duplicateAnswerCount: 0,
      answerDiversityRatio: 1,
      hardExclusionCount: 2,
      laneCounts: { 'explicit-preference': 0, broad: 6, exploration: 2 }
    });
    expect(seek?.metrics.uniqueConceptCount).toBe(7);
    expect(avoid?.metrics.uniqueConceptCount).toBe(8);
    expect(report.comparison).toMatchObject({
      selectedCandidateOverlapCount: 6,
      selectedCandidateUnionCount: 10,
      selectionDivergence: 0.4,
      hardExclusionDifferenceCount: 1
    });
  });

  it('is deterministic and exposes canonical bytes for a digest-bound host report', () => {
    const first = evaluateEpistemeBriefFixture(createEpistemeBriefEvaluationFixture());
    const second = evaluateEpistemeBriefFixture(createEpistemeBriefEvaluationFixture());
    expect(canonicalEvaluationJson(first)).toBe(canonicalEvaluationJson(second));
    expect(canonicalEvaluationJson(first)).not.toContain('player-quality');
    expect(first.limitations).toEqual(expect.arrayContaining([
      expect.stringContaining('not player preference accuracy')
    ]));
  });
});
