import {
  applyEpistemeUpdate,
  createEpistemeProfile,
  stableEpistemeStringify
} from './episteme';
import type {
  EpistemeProfileV1,
  EpistemeUpdateCommandV1,
  ExplicitPreferenceEvidenceV1
} from './episteme';
import {
  compileEpistemeBrief,
  EPISTEME_BRIEF_BROAD_FLOOR,
  EPISTEME_BRIEF_VERSION
} from './epistemeBrief';
import type {
  EligibleLexiconCandidateV1,
  EpistemeBriefLaneV1,
  EpistemeBriefOptionsV1,
  EpistemeBriefV1
} from './epistemeBrief';

/** Bump when the evaluation fixture or reported metrics change. */
export const EPISTEME_BRIEF_EVALUATION_VERSION = 'episteme-brief-evaluation-v1' as const;
export const EPISTEME_BRIEF_EVALUATION_FIXTURE_VERSION = 'seek-avoid-synthetic-pack-v1' as const;

export const EPISTEME_BRIEF_LANES: readonly EpistemeBriefLaneV1[] = [
  'explicit-preference',
  'inferred-preference',
  'confirmed-knowledge',
  'provisional-association',
  'broad',
  'exploration'
];

export type EpistemeBriefEvaluationMetricsV1 = Readonly<{
  selectedCount: number;
  uniqueCandidateCount: number;
  duplicateCandidateCount: number;
  uniqueAnswerCount: number;
  duplicateAnswerCount: number;
  answerDiversityRatio: number;
  uniqueConceptCount: number;
  uniqueSourceCount: number;
  hardExclusionCount: number;
  laneCounts: Readonly<Record<EpistemeBriefLaneV1, number>>;
  broadFloorRequested: number;
  broadFloorMet: number;
  broadFloorSatisfied: boolean;
  broadContentShare: number;
}>;

export type EpistemeBriefEvaluationProfileV1 = Readonly<{
  profileId: string;
  label: string;
  brief: EpistemeBriefV1;
  metrics: EpistemeBriefEvaluationMetricsV1;
}>;

export type EpistemeBriefEvaluationComparisonV1 = Readonly<{
  selectedCandidateOverlapCount: number;
  selectedAnswerOverlapCount: number;
  selectedCandidateUnionCount: number;
  selectionDivergence: number;
  hardExclusionDifferenceCount: number;
}>;

export type EpistemeBriefEvaluationFixtureV1 = Readonly<{
  fixtureVersion: typeof EPISTEME_BRIEF_EVALUATION_FIXTURE_VERSION;
  asOf: string;
  options: EpistemeBriefOptionsV1;
  candidates: readonly EligibleLexiconCandidateV1[];
  profiles: readonly Readonly<{ label: string; profile: EpistemeProfileV1 }>[];
}>;

export type EpistemeBriefEvaluationDraftV1 = Readonly<{
  evaluationVersion: typeof EPISTEME_BRIEF_EVALUATION_VERSION;
  fixtureVersion: typeof EPISTEME_BRIEF_EVALUATION_FIXTURE_VERSION;
  compilerVersion: typeof EPISTEME_BRIEF_VERSION;
  asOf: string;
  mode: string;
  language: string;
  selectionLimit: number;
  broadFloorFraction: number;
  profiles: readonly EpistemeBriefEvaluationProfileV1[];
  comparison: EpistemeBriefEvaluationComparisonV1;
  limitations: readonly string[];
}>;

function unique(values: readonly string[]): string[] {
  return [...new Set(values)].sort();
}

function ratio(numerator: number, denominator: number): number {
  return denominator === 0 ? 0 : Number((numerator / denominator).toFixed(6));
}

function laneCounts(brief: EpistemeBriefV1): Record<EpistemeBriefLaneV1, number> {
  return Object.fromEntries(EPISTEME_BRIEF_LANES.map((lane) => [lane, brief.lanes[lane].length])) as Record<
    EpistemeBriefLaneV1,
    number
  >;
}

/** Summarize compiler output without interpreting it as a player-quality measure. */
export function summarizeEpistemeBrief(
  brief: EpistemeBriefV1
): EpistemeBriefEvaluationMetricsV1 {
  const candidateIds = brief.selected.map((item) => item.candidate.candidateId);
  const answers = brief.selected.map((item) => item.candidate.answer.toLocaleUpperCase('en-US'));
  const concepts = brief.selected.flatMap((item) => item.candidate.conceptIds);
  const sources = brief.selected.flatMap((item) => item.sourceIds);
  const uniqueCandidates = unique(candidateIds);
  const uniqueAnswers = unique(answers);
  const broadCount = brief.selected.filter((item) => item.selectedLane === 'broad').length;
  return {
    selectedCount: brief.selected.length,
    uniqueCandidateCount: uniqueCandidates.length,
    duplicateCandidateCount: candidateIds.length - uniqueCandidates.length,
    uniqueAnswerCount: uniqueAnswers.length,
    duplicateAnswerCount: answers.length - uniqueAnswers.length,
    answerDiversityRatio: ratio(uniqueAnswers.length, answers.length),
    uniqueConceptCount: unique(concepts).length,
    uniqueSourceCount: unique(sources).length,
    hardExclusionCount: brief.selectionLog.filter((item) => item.decision === 'hard-exclusion').length,
    laneCounts: laneCounts(brief),
    broadFloorRequested: brief.broadFloorRequested,
    broadFloorMet: brief.broadFloorMet,
    broadFloorSatisfied: brief.broadFloorMet >= brief.broadFloorRequested,
    broadContentShare: ratio(broadCount, brief.selected.length)
  };
}

function setDifferenceCount(left: readonly string[], right: readonly string[]): number {
  const rightSet = new Set(right);
  return left.filter((item) => !rightSet.has(item)).length;
}

function compareBriefs(
  left: EpistemeBriefV1,
  right: EpistemeBriefV1
): EpistemeBriefEvaluationComparisonV1 {
  const leftCandidates = left.selected.map((item) => item.candidate.candidateId);
  const rightCandidates = right.selected.map((item) => item.candidate.candidateId);
  const leftAnswers = left.selected.map((item) => item.candidate.answer.toLocaleUpperCase('en-US'));
  const rightAnswers = right.selected.map((item) => item.candidate.answer.toLocaleUpperCase('en-US'));
  const candidateIntersection = unique(leftCandidates).filter((item) => new Set(rightCandidates).has(item));
  const answerIntersection = unique(leftAnswers).filter((item) => new Set(rightAnswers).has(item));
  const unionCount = unique([...leftCandidates, ...rightCandidates]).length;
  return {
    selectedCandidateOverlapCount: candidateIntersection.length,
    selectedAnswerOverlapCount: answerIntersection.length,
    selectedCandidateUnionCount: unionCount,
    selectionDivergence: Number((1 - ratio(candidateIntersection.length, unionCount)).toFixed(6)),
    hardExclusionDifferenceCount: setDifferenceCount(
      left.hardExclusions.map((item) => item.conceptId),
      right.hardExclusions.map((item) => item.conceptId)
    ) + setDifferenceCount(
      right.hardExclusions.map((item) => item.conceptId),
      left.hardExclusions.map((item) => item.conceptId)
    )
  };
}

/** Build the comparison payload that a host can digest and persist as an artifact. */
export function evaluateEpistemeBriefFixture(
  fixture: EpistemeBriefEvaluationFixtureV1
): EpistemeBriefEvaluationDraftV1 {
  if (fixture.profiles.length !== 2) throw new Error('The bounded seek/avoid fixture requires two profiles');
  const profiles = fixture.profiles.map(({ label, profile }) => {
    const brief = compileEpistemeBrief(profile, fixture.candidates, fixture.options);
    return {
      profileId: profile.profileId,
      label,
      brief,
      metrics: summarizeEpistemeBrief(brief)
    };
  });
  const [first, second] = profiles;
  if (!first || !second) throw new Error('The bounded seek/avoid fixture requires two profiles');
  return {
    evaluationVersion: EPISTEME_BRIEF_EVALUATION_VERSION,
    fixtureVersion: fixture.fixtureVersion,
    compilerVersion: EPISTEME_BRIEF_VERSION,
    asOf: fixture.asOf,
    mode: fixture.options.mode,
    language: fixture.options.language,
    selectionLimit: fixture.options.selectionLimit ?? 30,
    broadFloorFraction: EPISTEME_BRIEF_BROAD_FLOOR,
    profiles,
    comparison: compareBriefs(first.brief, second.brief),
    limitations: [
      'Synthetic admitted candidates exercise compiler behavior; they do not establish source truth or semantic quality.',
      'Selection divergence and lane counts describe deterministic retrieval output, not player preference accuracy, enjoyment, or solve probability.',
      'The broad-content floor is a compiler invariant for this fixture, not evidence that a generated puzzle is balanced or fun.'
    ]
  };
}

function explicitPreference(
  evidenceId: string,
  conceptId: string,
  action: 'seek' | 'exclude'
): ExplicitPreferenceEvidenceV1 {
  return {
    evidenceId,
    recordedAt: '2026-09-27T00:00:00.000Z',
    type: 'explicit-preference',
    concept: { conceptId, label: conceptId, language: 'en' },
    kind: 'taste',
    action,
    scope: { mode: 'play', language: 'en' },
    supersedesEvidenceIds: [],
    userText: `${action === 'seek' ? 'Seek' : 'Exclude'} ${conceptId}`
  };
}

function fixtureProfile(profileId: string, action: 'seek' | 'exclude'): EpistemeProfileV1 {
  const profile = createEpistemeProfile(profileId, '2026-09-27T00:00:00.000Z');
  const evidence = explicitPreference(`${profileId}-sound-control`, 'sound', action);
  const command: EpistemeUpdateCommandV1 = {
    updateId: `${profileId}-initial-control`,
    profileId,
    baseRevision: profile.revision,
    recordedAt: '2026-09-27T00:00:01.000Z',
    evidence: [evidence],
    evidenceActions: []
  };
  return applyEpistemeUpdate(profile, command).profile;
}

function candidate(
  candidateId: string,
  pool: EligibleLexiconCandidateV1['pool'],
  conceptIds: readonly string[] = []
): EligibleLexiconCandidateV1 {
  return {
    candidateId,
    answer: candidateId.replaceAll('-', '').toUpperCase(),
    language: 'en',
    conceptIds,
    knowledgeTaskIds: [],
    associationIds: [],
    pool,
    eligibility: {
      status: 'eligible',
      packId: 'synthetic-brief-evaluation-pack',
      packVersion: 'v1',
      sourceIds: ['synthetic-brief-evaluation-source']
    }
  };
}

/** Small, deterministic fixture used by the report script and domain tests. */
export function createEpistemeBriefEvaluationFixture(): EpistemeBriefEvaluationFixtureV1 {
  const candidates: EligibleLexiconCandidateV1[] = [
    candidate('broad-atlas', 'broad', ['geography']),
    candidate('broad-candle', 'broad', ['objects']),
    candidate('broad-river', 'broad', ['nature']),
    candidate('broad-window', 'broad', ['architecture']),
    candidate('broad-thread', 'broad', ['craft']),
    candidate('broad-orbit', 'broad', ['space']),
    candidate('sound-echo', 'exploration', ['sound']),
    candidate('sound-resonance', 'exploration', ['sound']),
    candidate('path-garden', 'exploration', ['gardens']),
    candidate('path-stone', 'exploration', ['stone']),
    candidate('path-weather', 'exploration', ['weather']),
    candidate('path-archive', 'exploration', ['archives'])
  ];
  const options: EpistemeBriefOptionsV1 = {
    asOf: '2026-09-27T00:00:02.000Z',
    mode: 'play',
    language: 'en',
    selectionLimit: 8
  };
  return {
    fixtureVersion: EPISTEME_BRIEF_EVALUATION_FIXTURE_VERSION,
    asOf: options.asOf,
    options,
    candidates,
    profiles: [
      { label: 'seek-sound', profile: fixtureProfile('evaluation-seek-sound', 'seek') },
      { label: 'avoid-sound', profile: fixtureProfile('evaluation-avoid-sound', 'exclude') }
    ]
  };
}

/** Stable bytes for the host-side SHA-256 report envelope. */
export function canonicalEvaluationJson(value: unknown): string {
  return stableEpistemeStringify(value);
}
