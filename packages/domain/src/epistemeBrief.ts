import {
  projectEpistemeProfile,
  stableEpistemeStringify
} from './episteme';
import type {
  EpistemeProfileV1,
  EpistemeProjectionV1,
  KnowledgeEstimateV1,
  PreferenceScopeV1,
  ProfileAssociationV1,
  ProfileClaimV1
} from './episteme';

/** Bump when brief scoring, lane rules, or allocation changes. */
export const EPISTEME_BRIEF_VERSION = 'episteme-brief-v1' as const;

export const EPISTEME_BRIEF_LIMIT_DEFAULT = 30;
export const EPISTEME_BRIEF_LIMIT_MAX = 100;
export const EPISTEME_BRIEF_CANDIDATE_MAX = 5_000;
export const EPISTEME_BRIEF_BROAD_FLOOR = 0.3;

const CANDIDATE_ID_MAX = 200;
const CANDIDATE_TEXT_MAX = 500;
const LINK_MAX = 32;
const SOURCE_MAX = 8;
// Requiring distinct retrievals and a conservative lower bound avoids treating a single lucky solve as known.
const CONFIRMED_KNOWLEDGE_MIN_SESSIONS = 3;
const CONFIRMED_KNOWLEDGE_MIN_SUCCESS = 1;
const CONFIRMED_KNOWLEDGE_MIN_MEAN = 0.7;
const EXPLICIT_PREFERENCE_SCORE_CAP = 1.5;
const INFERRED_PREFERENCE_SCORE_FACTOR = 0.4;
const INFERRED_PREFERENCE_SCORE_CAP = 0.3;
const CONFIRMED_KNOWLEDGE_SCORE = 0.15;
const ASSOCIATION_SCORE_CAP = 0.05;
const UNTESTED_ASSOCIATION_SCORE = 0;
const BROAD_POOL_SCORE = 0.2;
const EXPLORATION_POOL_SCORE = 0.1;

/**
 * A resolver/admission boundary must construct this contract only after it has
 * admitted a sourced lexicon record. This type is not itself proof that an
 * arbitrary caller's `eligible` assertion is true; no pack or source is bundled
 * with this compiler.
 */
export type EligibleLexiconCandidateV1 = Readonly<{
  candidateId: string;
  answer: string;
  language: string;
  conceptIds: readonly string[];
  knowledgeTaskIds: readonly string[];
  associationIds: readonly string[];
  /** `broad` is ordinary world material; `exploration` is an admitted discovery candidate. */
  pool: 'broad' | 'exploration';
  eligibility: Readonly<{
    status: 'eligible';
    packId: string;
    packVersion: string;
    sourceIds: readonly string[];
  }>;
}>;

export type EpistemeBriefLaneV1 =
  | 'explicit-preference'
  | 'inferred-preference'
  | 'confirmed-knowledge'
  | 'provisional-association'
  | 'broad'
  | 'exploration';

export type EpistemeBriefOptionsV1 = Readonly<{
  asOf: string;
  mode: string;
  language: string;
  selectionLimit?: number;
}>;

export type EpistemeBriefHardExclusionV1 = Readonly<{
  conceptId: string;
  scope: PreferenceScopeV1;
  evidenceIds: readonly string[];
}>;

export type EpistemeBriefScoreComponentsV1 = Readonly<{
  /** Deterministic ranking weights, not probabilities or calibrated measurements. */
  explicitPreference: number;
  inferredPreference: number;
  confirmedKnowledge: number;
  provisionalAssociation: number;
  poolDiversity: number;
  total: number;
}>;

export type EpistemeBriefDecisionV1 = Readonly<{
  candidateId: string;
  selected: boolean;
  selectedRank: number | null;
  selectedLane: EpistemeBriefLaneV1 | null;
  matchedLanes: readonly EpistemeBriefLaneV1[];
  score: number | null;
  scoreComponents: EpistemeBriefScoreComponentsV1 | null;
  decision: 'selected-broad-floor' | 'selected-ranked' | 'hard-exclusion' | 'language-mismatch' | 'ranked-out';
  reason: string;
  sourceIds: readonly string[];
  evidenceIds: readonly string[];
  hardExcludedConceptIds: readonly string[];
}>;

export type EpistemeBriefSelectionV1 = Readonly<{
  candidate: EligibleLexiconCandidateV1;
  rank: number;
  selectedLane: EpistemeBriefLaneV1;
  matchedLanes: readonly EpistemeBriefLaneV1[];
  score: number;
  scoreComponents: EpistemeBriefScoreComponentsV1;
  sourceIds: readonly string[];
  evidenceIds: readonly string[];
}>;

export type EpistemeBriefV1 = Readonly<{
  briefVersion: typeof EPISTEME_BRIEF_VERSION;
  asOf: string;
  profileId: string;
  profileRevision: number;
  mode: string;
  language: string;
  selectionLimit: number;
  broadFloorRequested: number;
  broadFloorMet: number;
  hardExclusions: readonly EpistemeBriefHardExclusionV1[];
  lanes: Readonly<Record<EpistemeBriefLaneV1, readonly string[]>>;
  selected: readonly EpistemeBriefSelectionV1[];
  /** One deterministic record per input candidate, including hard-filtered candidates. */
  selectionLog: readonly EpistemeBriefDecisionV1[];
}>;

type HardExclusion = EpistemeBriefHardExclusionV1;

type ScoredCandidate = Readonly<{
  candidate: EligibleLexiconCandidateV1;
  scoreComponents: EpistemeBriefScoreComponentsV1;
  matchedLanes: readonly EpistemeBriefLaneV1[];
  selectedLane: EpistemeBriefLaneV1;
  sourceIds: readonly string[];
  evidenceIds: readonly string[];
}>;

type BriefIndexes = Readonly<{
  claimsByConcept: ReadonlyMap<string, readonly ProfileClaimV1[]>;
  knowledgeByTask: ReadonlyMap<string, readonly KnowledgeEstimateV1[]>;
  associationsById: ReadonlyMap<string, ProfileAssociationV1>;
  associationEvidenceIdsById: ReadonlyMap<string, readonly string[]>;
  conceptEvidenceIdsById: ReadonlyMap<string, readonly string[]>;
  hardExclusionsByConcept: ReadonlyMap<string, readonly HardExclusion[]>;
}>;

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function validText(value: unknown, maximum: number): value is string {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= maximum;
}

function validIdList(value: unknown, maximum: number, required = false): value is readonly string[] {
  return Array.isArray(value) && value.length <= maximum && (!required || value.length > 0) &&
    value.every((item) => validText(item, CANDIDATE_ID_MAX)) && new Set(value).size === value.length;
}

function validateCandidate(value: unknown): asserts value is EligibleLexiconCandidateV1 {
  assert(isRecord(value), 'Brief candidate must be an object');
  assert(validText(value.candidateId, CANDIDATE_ID_MAX), 'Brief candidate ID is invalid');
  assert(validText(value.answer, CANDIDATE_TEXT_MAX), `Candidate ${value.candidateId} has invalid answer text`);
  assert(validText(value.language, 63), `Candidate ${value.candidateId} has invalid language`);
  assert(value.pool === 'broad' || value.pool === 'exploration', `Candidate ${value.candidateId} has an unknown pool`);
  assert(validIdList(value.conceptIds, LINK_MAX), `Candidate ${value.candidateId} has invalid concept links`);
  assert(validIdList(value.knowledgeTaskIds, LINK_MAX), `Candidate ${value.candidateId} has invalid knowledge-task links`);
  assert(validIdList(value.associationIds, LINK_MAX), `Candidate ${value.candidateId} has invalid association links`);
  assert(isRecord(value.eligibility) && value.eligibility.status === 'eligible',
    `Candidate ${value.candidateId} lacks an eligible admission assertion`);
  assert(validText(value.eligibility.packId, CANDIDATE_ID_MAX) && validText(value.eligibility.packVersion, CANDIDATE_ID_MAX),
    `Candidate ${value.candidateId} lacks its admitted pack identity`);
  assert(validIdList(value.eligibility.sourceIds, SOURCE_MAX, true),
    `Candidate ${value.candidateId} lacks valid source links`);
}

function unique(values: readonly string[]): string[] {
  return [...new Set(values)].sort(compareText);
}

function compareText(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function scopeApplies(scope: PreferenceScopeV1, mode: string, language: string): boolean {
  return (scope.mode === undefined || scope.mode === mode) &&
    (scope.language === undefined || scope.language.toLowerCase() === language.toLowerCase());
}

function activeEvidence(profile: EpistemeProfileV1): EpistemeProfileV1['evidence'] {
  const active = new Map<string, boolean>();
  for (const action of [...profile.evidenceActions].sort((left, right) =>
    Date.parse(left.recordedAt) - Date.parse(right.recordedAt) || compareText(left.actionId, right.actionId))) {
    active.set(action.targetEvidenceId, action.action === 'restore');
  }
  return profile.evidence.filter((item) => active.get(item.evidenceId) !== false);
}

function collectHardExclusions(
  projection: EpistemeProjectionV1,
  mode: string,
  language: string
): EpistemeBriefHardExclusionV1[] {
  const byKey = new Map<string, { conceptId: string; scope: PreferenceScopeV1; evidenceIds: string[] }>();
  const add = (conceptId: string, scope: PreferenceScopeV1, evidenceIds: readonly string[]) => {
    const key = stableEpistemeStringify([conceptId, scope]);
    const prior = byKey.get(key) ?? { conceptId, scope, evidenceIds: [] };
    prior.evidenceIds.push(...evidenceIds);
    byKey.set(key, prior);
  };
  for (const policy of projection.policies) {
    if (policy.mode === 'exclude' && scopeApplies(policy.scope, mode, language)) {
      add(policy.conceptId, policy.scope, policy.evidenceIds);
    }
  }
  // Keep an explicit avoid hard even if an imported/older projection omitted its policy row.
  for (const claim of projection.claims) {
    if (claim.authority === 'explicit' && claim.lockedByUser && claim.stance === 'avoid' &&
      scopeApplies(claim.scope, mode, language)) {
      add(claim.concept.conceptId, claim.scope, claim.evidenceIds);
    }
  }
  return [...byKey.values()].map((item) => ({
    conceptId: item.conceptId,
    scope: item.scope,
    evidenceIds: unique(item.evidenceIds)
  })).sort((left, right) => compareText(left.conceptId, right.conceptId) ||
    compareText(stableEpistemeStringify(left.scope), stableEpistemeStringify(right.scope)));
}

function appendIndex<T>(index: Map<string, T[]>, key: string, value: T): void {
  const prior = index.get(key) ?? [];
  prior.push(value);
  index.set(key, prior);
}

function buildBriefIndexes(
  projection: EpistemeProjectionV1,
  evidence: EpistemeProfileV1['evidence'],
  hardExclusions: readonly HardExclusion[],
  mode: string,
  language: string
): BriefIndexes {
  const claimsByConcept = new Map<string, ProfileClaimV1[]>();
  for (const claim of projection.claims) {
    if (scopeApplies(claim.scope, mode, language)) appendIndex(claimsByConcept, claim.concept.conceptId, claim);
  }
  const knowledgeByTask = new Map<string, KnowledgeEstimateV1[]>();
  for (const estimate of projection.knowledge) {
    if (estimate.task.language.toLowerCase() === language.toLowerCase()) appendIndex(knowledgeByTask, estimate.task.taskId, estimate);
  }
  const associationsById = new Map(projection.associations.map((item) => [item.associationId, item] as const));
  const associationEvidenceIdsById = new Map<string, string[]>();
  const conceptEvidenceIdsById = new Map<string, string[]>();
  for (const item of evidence) {
    if (item.type === 'association-proposal' || item.type === 'association-response') {
      appendIndex(associationEvidenceIdsById, item.associationId, item.evidenceId);
    }
    if (item.type === 'explicit-preference') {
      appendIndex(conceptEvidenceIdsById, item.concept.conceptId, item.evidenceId);
    } else if (item.type === 'preference-signal' && item.response !== 'pass') {
      for (const mapping of item.mappings[item.response] ?? []) {
        appendIndex(conceptEvidenceIdsById, mapping.concept.conceptId, item.evidenceId);
      }
    }
  }
  const hardExclusionsByConcept = new Map<string, HardExclusion[]>();
  for (const item of hardExclusions) appendIndex(hardExclusionsByConcept, item.conceptId, item);
  return {
    claimsByConcept,
    knowledgeByTask,
    associationsById,
    associationEvidenceIdsById: new Map([...associationEvidenceIdsById].map(([key, ids]) => [key, unique(ids)])),
    conceptEvidenceIdsById: new Map([...conceptEvidenceIdsById].map(([key, ids]) => [key, unique(ids)])),
    hardExclusionsByConcept
  };
}

function confirmedKnowledge(
  knowledgeByTask: ReadonlyMap<string, readonly KnowledgeEstimateV1[]>,
  candidate: EligibleLexiconCandidateV1
): KnowledgeEstimateV1[] {
  return candidate.knowledgeTaskIds.flatMap((id) => knowledgeByTask.get(id) ?? []).filter((item) =>
    item.independent.evidenceCount >= CONFIRMED_KNOWLEDGE_MIN_SESSIONS &&
    !item.independent.insufficientEvidence &&
    item.independent.successWeight >= CONFIRMED_KNOWLEDGE_MIN_SUCCESS &&
    item.independent.mean >= CONFIRMED_KNOWLEDGE_MIN_MEAN);
}

function matchedAssociations(
  associationsById: ReadonlyMap<string, ProfileAssociationV1>,
  candidate: EligibleLexiconCandidateV1
): ProfileAssociationV1[] {
  return candidate.associationIds.flatMap((id) => {
    const item = associationsById.get(id);
    return item && item.language.toLowerCase() === candidate.language.toLowerCase() &&
      !item.calibrationProvenance?.expired && !item.modelProvenance?.expired && item.response !== 'rejected' && item.response !== 'passed'
      ? [item]
      : [];
  });
}

function laneFor(matched: readonly EpistemeBriefLaneV1[], pool: EligibleLexiconCandidateV1['pool']): EpistemeBriefLaneV1 {
  const priority: readonly EpistemeBriefLaneV1[] = [
    'explicit-preference',
    'inferred-preference',
    'confirmed-knowledge',
    'provisional-association'
  ];
  return priority.find((lane) => matched.includes(lane)) ?? (pool === 'broad' ? 'broad' : 'exploration');
}

function sortScored(left: ScoredCandidate, right: ScoredCandidate): number {
  return right.scoreComponents.total - left.scoreComponents.total || compareText(left.candidate.candidateId, right.candidate.candidateId);
}

function scoreCandidate(indexes: BriefIndexes, candidate: EligibleLexiconCandidateV1): ScoredCandidate {
  const associations = matchedAssociations(indexes.associationsById, candidate);
  const associationParentConceptIds = new Set(associations.flatMap((item) => item.parentConceptIds));
  const conceptIds = new Set([
    ...candidate.conceptIds,
    ...associations.flatMap((item) => item.parentConceptIds)
  ]);
  const claims = [...conceptIds].flatMap((id) => indexes.claimsByConcept.get(id) ?? []);
  const explicitMatches = claims.filter((claim) => claim.authority === 'explicit' && claim.stance === 'seek');
  const inferredMatches = claims.filter((claim) => claim.authority === 'inferred');
  const knowledgeMatches = confirmedKnowledge(indexes.knowledgeByTask, candidate);
  const explicitPreference = Math.min(EXPLICIT_PREFERENCE_SCORE_CAP,
    explicitMatches.reduce((sum, item) => sum + Math.max(0, item.strength), 0));
  const inferredPreference = Math.max(-INFERRED_PREFERENCE_SCORE_CAP, Math.min(INFERRED_PREFERENCE_SCORE_CAP,
    inferredMatches.reduce((sum, item) => sum + item.signedScore * INFERRED_PREFERENCE_SCORE_FACTOR, 0)));
  const confirmedKnowledgeScore = knowledgeMatches.length > 0 ? CONFIRMED_KNOWLEDGE_SCORE : 0;
  // Unendorsed associations remain in a distinct lane but contribute no preference weight.
  const provisionalAssociation = associations.length > 0
    ? Math.min(ASSOCIATION_SCORE_CAP, associations.reduce((maximum, item) => Math.max(maximum, item.response === 'kept'
      ? item.explorationWeight
      : UNTESTED_ASSOCIATION_SCORE), 0))
    : 0;
  const poolDiversity = candidate.pool === 'broad' ? BROAD_POOL_SCORE : EXPLORATION_POOL_SCORE;
  const total = explicitPreference + inferredPreference + confirmedKnowledgeScore + provisionalAssociation + poolDiversity;
  const matchedLanes: EpistemeBriefLaneV1[] = [];
  if (explicitMatches.length > 0) matchedLanes.push('explicit-preference');
  if (inferredMatches.some((item) => item.signedScore !== 0)) matchedLanes.push('inferred-preference');
  if (knowledgeMatches.length > 0) matchedLanes.push('confirmed-knowledge');
  if (associations.length > 0) matchedLanes.push('provisional-association');
  matchedLanes.push(candidate.pool);
  const evidenceIds = unique([
    ...explicitMatches.flatMap((item) => [...item.evidenceIds, ...item.counterEvidenceIds]),
    ...inferredMatches.flatMap((item) => [...item.evidenceIds, ...item.counterEvidenceIds]),
    ...knowledgeMatches.flatMap((item) => [
      ...item.supportEvidenceIds,
      ...item.failureEvidenceIds
    ]),
    ...associations.flatMap((item) => [...item.supportEvidenceIds, ...item.counterEvidenceIds]),
    ...associations.flatMap((item) => indexes.associationEvidenceIdsById.get(item.associationId) ?? []),
    ...[...associationParentConceptIds].flatMap((id) => indexes.conceptEvidenceIdsById.get(id) ?? [])
  ]);
  const scoreComponents: EpistemeBriefScoreComponentsV1 = {
    explicitPreference,
    inferredPreference,
    confirmedKnowledge: confirmedKnowledgeScore,
    provisionalAssociation,
    poolDiversity,
    total
  };
  return {
    candidate,
    scoreComponents,
    matchedLanes,
    selectedLane: laneFor(matchedLanes, candidate.pool),
    sourceIds: unique(candidate.eligibility.sourceIds),
    evidenceIds
  };
}

function emptyLanes(): Record<EpistemeBriefLaneV1, string[]> {
  return {
    'explicit-preference': [],
    'inferred-preference': [],
    'confirmed-knowledge': [],
    'provisional-association': [],
    broad: [],
    exploration: []
  };
}

/**
 * Compile a bounded, deterministic generation brief from a profile and an
 * externally admitted candidate pool. This ranks candidates; it does not
 * verify the source pack, invent content, or replace grid/clue eligibility.
 */
export function compileEpistemeBrief(
  profile: EpistemeProfileV1,
  candidates: readonly EligibleLexiconCandidateV1[],
  options: EpistemeBriefOptionsV1
): EpistemeBriefV1 {
  assert(candidates.length <= EPISTEME_BRIEF_CANDIDATE_MAX, 'Brief candidate pool exceeds the bounded limit');
  assert(validText(options.mode, 80), 'Brief mode is invalid');
  assert(validText(options.language, 63), 'Brief language is invalid');
  const selectionLimit = options.selectionLimit ?? EPISTEME_BRIEF_LIMIT_DEFAULT;
  assert(Number.isSafeInteger(selectionLimit) && selectionLimit >= 1 && selectionLimit <= EPISTEME_BRIEF_LIMIT_MAX,
    'Brief selection limit is outside the supported range');
  const seenCandidateIds = new Set<string>();
  for (const candidate of candidates) {
    validateCandidate(candidate);
    assert(!seenCandidateIds.has(candidate.candidateId), `Duplicate brief candidate ID ${candidate.candidateId}`);
    seenCandidateIds.add(candidate.candidateId);
  }

  const projectedProfile = projectEpistemeProfile(profile, options.asOf);
  const projection = projectedProfile.projection;
  const evidence = activeEvidence(profile);
  const hardExclusions = collectHardExclusions(projection, options.mode, options.language);
  const scored: ScoredCandidate[] = [];
  const preliminaryLog: Array<Omit<EpistemeBriefDecisionV1, 'selectedRank' | 'selectedLane' | 'selected'>> = [];
  const indexes = buildBriefIndexes(projection, evidence, hardExclusions, options.mode, options.language);

  for (const candidate of [...candidates].sort((left, right) => compareText(left.candidateId, right.candidateId))) {
    const sourceIds = unique(candidate.eligibility.sourceIds);
    if (candidate.language.toLowerCase() !== options.language.toLowerCase()) {
      preliminaryLog.push({
        candidateId: candidate.candidateId,
        matchedLanes: [],
        score: null,
        scoreComponents: null,
        decision: 'language-mismatch',
        reason: `Candidate language ${candidate.language} does not match requested language ${options.language}`,
        sourceIds,
        evidenceIds: [],
        hardExcludedConceptIds: []
      });
      continue;
    }
    const provisional = scoreCandidate(indexes, candidate);
    const linkedAssociations = candidate.associationIds.flatMap((id) => {
      const item = indexes.associationsById.get(id);
      return item ? [item] : [];
    });
    const candidateConcepts = new Set([
      ...candidate.conceptIds,
      ...linkedAssociations.flatMap((item) => item.parentConceptIds)
    ]);
    const matchedExclusions = [...candidateConcepts].flatMap((id) => indexes.hardExclusionsByConcept.get(id) ?? []);
    if (matchedExclusions.length > 0) {
      preliminaryLog.push({
        candidateId: candidate.candidateId,
        matchedLanes: provisional.matchedLanes,
        score: provisional.scoreComponents.total,
        scoreComponents: provisional.scoreComponents,
        decision: 'hard-exclusion',
        reason: 'An explicit scoped exclusion matched this candidate; exclusions override every ranking lane',
        sourceIds,
        evidenceIds: unique([...provisional.evidenceIds, ...matchedExclusions.flatMap((item) => item.evidenceIds)]),
        hardExcludedConceptIds: unique(matchedExclusions.map((item) => item.conceptId))
      });
      continue;
    }
    scored.push(provisional);
  }

  const ranked = [...scored].sort(sortScored);
  const broadCandidates = ranked.filter((item) => item.candidate.pool === 'broad');
  const broadFloorRequested = Math.ceil(selectionLimit * EPISTEME_BRIEF_BROAD_FLOOR);
  const broadFloor = Math.min(selectionLimit, broadFloorRequested, broadCandidates.length);
  const selectedIds = new Set<string>();
  const selectedRows: Array<{ item: ScoredCandidate; lane: EpistemeBriefLaneV1; decision: 'selected-broad-floor' | 'selected-ranked' }> = [];
  for (const item of broadCandidates.slice(0, broadFloor)) {
    selectedIds.add(item.candidate.candidateId);
    selectedRows.push({ item, lane: 'broad', decision: 'selected-broad-floor' });
  }
  for (const item of ranked) {
    if (selectedRows.length >= selectionLimit) break;
    if (selectedIds.has(item.candidate.candidateId)) continue;
    selectedIds.add(item.candidate.candidateId);
    selectedRows.push({ item, lane: item.selectedLane, decision: 'selected-ranked' });
  }

  const selected = selectedRows.map(({ item, lane }, index): EpistemeBriefSelectionV1 => ({
    candidate: item.candidate,
    rank: index + 1,
    selectedLane: lane,
    matchedLanes: item.matchedLanes,
    score: item.scoreComponents.total,
    scoreComponents: item.scoreComponents,
    sourceIds: item.sourceIds,
    evidenceIds: item.evidenceIds
  }));
  const lanes = emptyLanes();
  for (const selection of selected) lanes[selection.selectedLane].push(selection.candidate.candidateId);

  for (const { item, lane, decision } of selectedRows) {
    preliminaryLog.push({
      candidateId: item.candidate.candidateId,
      matchedLanes: item.matchedLanes,
      score: item.scoreComponents.total,
      scoreComponents: item.scoreComponents,
      decision,
      reason: decision === 'selected-broad-floor'
        ? 'Selected to preserve the versioned broad-material floor'
        : `Selected by deterministic ranking in the ${lane} lane`,
      sourceIds: item.sourceIds,
      evidenceIds: item.evidenceIds,
      hardExcludedConceptIds: []
    });
  }
  for (const item of ranked) {
    if (selectedIds.has(item.candidate.candidateId)) continue;
    preliminaryLog.push({
      candidateId: item.candidate.candidateId,
      matchedLanes: item.matchedLanes,
      score: item.scoreComponents.total,
      scoreComponents: item.scoreComponents,
      decision: 'ranked-out',
      reason: 'Eligible candidate fell below the deterministic selection limit',
      sourceIds: item.sourceIds,
      evidenceIds: item.evidenceIds,
      hardExcludedConceptIds: []
    });
  }

  const selectedRankById = new Map(selected.map((item) => [item.candidate.candidateId, item] as const));
  const selectionLog = preliminaryLog.map((item): EpistemeBriefDecisionV1 => {
    const chosen = selectedRankById.get(item.candidateId);
    return {
      ...item,
      selected: chosen !== undefined,
      selectedRank: chosen?.rank ?? null,
      selectedLane: chosen?.selectedLane ?? null
    };
  }).sort((left, right) => compareText(left.candidateId, right.candidateId));
  return {
    briefVersion: EPISTEME_BRIEF_VERSION,
    asOf: options.asOf,
    profileId: profile.profileId,
    profileRevision: profile.revision,
    mode: options.mode,
    language: options.language,
    selectionLimit,
    broadFloorRequested,
    broadFloorMet: selected.filter((item) => item.selectedLane === 'broad').length,
    hardExclusions,
    lanes,
    selected,
    selectionLog
  };
}
