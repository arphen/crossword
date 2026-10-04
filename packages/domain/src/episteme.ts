import type { EntryId } from './puzzle';
import { validateSessionAnalysis } from './solveV2';
import type { SessionAnalysis } from './solveV2';

/** Reducer versions are persisted with every profile revision. Changing a rule requires a new version. */
export const KNOWLEDGE_REDUCER_VERSION = 'knowledge-reducer-v1' as const;
export const PREFERENCE_REDUCER_VERSION = 'preference-reducer-v1' as const;
export const ASSOCIATION_REDUCER_VERSION = 'association-reducer-v2' as const;
export const EPISTEME_SCHEMA_VERSION = 1 as const;

const INFERRED_SESSION_CAP = 0.25;
const CLEAR_SIGNAL_EVENT_CAP = 0.2;
const AMBIGUOUS_SIGNAL_EVENT_CAP = 0.05;
const EXPLICIT_SAVE_WEIGHT = 0.15;
const SUPPORTED_RETRIEVAL_CAP = 0.35;
const FAILED_ATTEMPT_CAP = 0.5;
const HALF_LIFE_DAYS = 90;

export type ClaimKindV1 = 'taste' | 'goal' | 'style' | 'context';
export type ClaimStanceV1 = 'seek' | 'avoid' | 'ambivalent';
export type EvidenceAdequacyV1 = 'single-signal' | 'repeated' | 'contradictory' | 'explicit';
export type PreferenceScopeV1 = Readonly<{
  mode?: string;
  language?: string;
  expiresAt?: string;
}>;

/** A deliberately open concept vocabulary. IDs and labels are supplied by evidence, never ontology enums. */
export type OpenConceptV1 = Readonly<{
  conceptId: string;
  label: string;
  language?: string;
}>;

export type KnowledgeTaskV1 = Readonly<{
  /** Stable content identity: normally a sense, fact, answer form, or clue mechanism ID. */
  taskId: string;
  taskKind: 'sense' | 'fact' | 'answer-form' | 'clue-mechanism';
  /** Direction is open vocabulary (for example prompt-to-answer or answer-to-gloss). */
  direction: string;
  language: string;
  /** Open vocabulary; keep the clue relation separate from the item being learned. */
  clueFamily: string;
  /** Literal clue-surface family used only for reversible exposure rotation. */
  surfaceFamily?: string;
  /** Bounded source/task receipt for an optional language-learning lane. */
  taskPack?: Readonly<Record<string, unknown>>;
  /** Only reviewed content can contribute knowledge evidence. */
  contentReview: 'approved' | 'quarantined' | 'unreviewed';
}>;

export type SessionAnalysisEvidenceV1 = Readonly<{
  evidenceId: string;
  recordedAt: string;
  type: 'session-analysis';
  analysis: SessionAnalysis;
  /** Frozen, reviewed links from puzzle entries to exact learnable tasks. */
  taskLinks: readonly Readonly<{ entryId: EntryId; tasks: readonly KnowledgeTaskV1[] }>[];
}>;

export type PreferenceMappingV1 = Readonly<{
  mappingId: string;
  concept: OpenConceptV1;
  kind: ClaimKindV1;
  stance: Exclude<ClaimStanceV1, 'ambivalent'>;
  /** Reducer caps this weight; it is not a model confidence value. */
  weight: number;
  scope: PreferenceScopeV1;
}>;

export type PreferenceResponseV1 = 'keep' | 'not-for-me' | 'pass';

/**
 * A frozen interpretation map copied from the exact card/stimulus version shown.
 * The selected response only activates its own predeclared map. In particular,
 * "not-for-me" is never inferred by negating the "keep" map.
 */
export type PreferenceSignalEvidenceV1 = Readonly<{
  evidenceId: string;
  recordedAt: string;
  type: 'preference-signal';
  source: 'reflection-card' | 'ambiguous-association';
  sessionId?: string;
  response: PreferenceResponseV1;
  ambiguity: 'clear' | 'ambiguous';
  stimulusId: string;
  stimulusVersion: string;
  mappings: Readonly<Partial<Record<Exclude<PreferenceResponseV1, 'pass'>, readonly PreferenceMappingV1[]>>>;
}>;

/** An explicit control is separate from the soft inferred score and always wins when unambiguous. */
export type ExplicitPreferenceEvidenceV1 = Readonly<{
  evidenceId: string;
  recordedAt: string;
  type: 'explicit-preference';
  concept: OpenConceptV1;
  kind: ClaimKindV1;
  action: 'seek' | 'exclude' | 'clear';
  scope: PreferenceScopeV1;
  /** A user correction can explicitly supersede old statements; old evidence remains inspectable. */
  supersedesEvidenceIds: readonly string[];
  userText?: string;
}>;

export type PerformanceEvidenceV1 = Readonly<{
  evidenceId: string;
  recordedAt: string;
  type: 'performance';
  sessionId: string;
  measure:
    | 'correctness'
    | 'speed'
    | 'completion'
    | 'hint-use'
    | 'playtest-worth'
    | 'playtest-return'
    | 'playtest-rough-edge';
  value: number | string;
}>;

type AssociationProposalEvidenceBaseV1 = Readonly<{
  evidenceId: string;
  recordedAt: string;
  type: 'association-proposal';
  associationId: string;
  phrase: string;
  language: string;
  relation: 'adjacent' | 'contrast' | 'metaphor' | 'sound' | 'etymology';
  parentConceptIds: readonly string[];
  explanation: string;
}>;

/** Model-authored proposals have no calibration provenance. */
export type ModelAssociationProposalEvidenceV1 = AssociationProposalEvidenceBaseV1 & Readonly<{
  origin: 'model-proposal';
  /** Unendorsed postgame paths expire without becoming durable profile direction. */
  expiresAt?: string;
  expireAfterSessions?: 10;
}>;

/** A bounded association hypothesis grounded in the exact calibration trace that produced it. */
export type CalibrationAssociationProposalEvidenceV1 = AssociationProposalEvidenceBaseV1 & Readonly<{
  origin: 'calibration-proposal';
  calibrationId: string;
  sourceObservationIds: readonly string[];
  sourceStimulusIds: readonly string[];
  expiresAt: string;
  expireAfterSessions: 5;
}>;

export type AssociationProposalEvidenceV1 =
  | ModelAssociationProposalEvidenceV1
  | CalibrationAssociationProposalEvidenceV1;

export type AssociationResponseEvidenceV1 = Readonly<{
  evidenceId: string;
  recordedAt: string;
  type: 'association-response';
  associationId: string;
  proposalEvidenceId: string;
  response: 'keep' | 'not-for-me' | 'pass';
}>;

export type EpistemeEvidenceV1 =
  | SessionAnalysisEvidenceV1
  | PreferenceSignalEvidenceV1
  | ExplicitPreferenceEvidenceV1
  | PerformanceEvidenceV1
  | AssociationProposalEvidenceV1
  | AssociationResponseEvidenceV1;

export type EvidenceActionV1 = Readonly<{
  actionId: string;
  recordedAt: string;
  targetEvidenceId: string;
  action: 'retract' | 'restore';
  reason?: string;
}>;

export type ProfileClaimV1 = Readonly<{
  claimId: string;
  concept: OpenConceptV1;
  kind: ClaimKindV1;
  stance: ClaimStanceV1;
  authority: 'explicit' | 'inferred';
  /** Ranking weight, not a psychometric measurement or probability. */
  strength: number;
  /** Signed open-facet weight in [-1, 1]; source links preserve the two sides of a conflict. */
  signedScore: number;
  positiveWeight: number;
  negativeWeight: number;
  adequacy: EvidenceAdequacyV1;
  scope: PreferenceScopeV1;
  evidenceIds: readonly string[];
  counterEvidenceIds: readonly string[];
  lockedByUser: boolean;
}>;

export type ExplicitPolicyV1 = Readonly<{
  conceptId: string;
  scope: PreferenceScopeV1;
  mode: 'include' | 'exclude' | 'conflict';
  evidenceIds: readonly string[];
  lockedByUser: true;
}>;

export type KnowledgeChannelV1 = Readonly<{
  successWeight: number;
  failureWeight: number;
  mean: number;
  /** Approximate 95% Beta interval from the versioned Beta(1,1) prior. */
  interval: readonly [number, number];
  evidenceCount: number;
  insufficientEvidence: boolean;
}>;

export type KnowledgeEstimateV1 = Readonly<{
  task: Omit<KnowledgeTaskV1, 'contentReview'>;
  independent: KnowledgeChannelV1;
  supported: KnowledgeChannelV1;
  supportEvidenceIds: readonly string[];
  failureEvidenceIds: readonly string[];
  exposureEvidenceIds: readonly string[];
  lastExposureAt?: string;
  lastIndependentAt?: string;
}>;

export type ProfileAssociationV1 = Readonly<{
  associationId: string;
  phrase: string;
  language: string;
  relation: AssociationProposalEvidenceV1['relation'];
  parentConceptIds: readonly string[];
  explanation: string;
  origin: AssociationProposalEvidenceV1['origin'];
  evidenceStatus: 'untested' | 'responded-to';
  response: 'kept' | 'rejected' | 'passed' | null;
  supportEvidenceIds: readonly string[];
  counterEvidenceIds: readonly string[];
  explorationWeight: number;
  /** Calibration traces are provenance only; they are not preference or knowledge claims. */
  calibrationProvenance: Readonly<{
    calibrationId: string;
    sourceObservationIds: readonly string[];
    sourceStimulusIds: readonly string[];
    expiresAt: string;
    expireAfterSessions: 5;
    expired: boolean;
    expirationReasons: readonly ('age' | 'sessions')[];
  }> | null;
  modelProvenance: Readonly<{
    expiresAt: string;
    expireAfterSessions: 10;
    expired: boolean;
    expirationReasons: readonly ('age' | 'sessions')[];
  }> | null;
}>;

export type EpistemeProjectionV1 = Readonly<{
  schemaVersion: 1;
  knowledgeReducerVersion: typeof KNOWLEDGE_REDUCER_VERSION;
  preferenceReducerVersion: typeof PREFERENCE_REDUCER_VERSION;
  associationReducerVersion: typeof ASSOCIATION_REDUCER_VERSION;
  asOf: string;
  claims: readonly ProfileClaimV1[];
  policies: readonly ExplicitPolicyV1[];
  knowledge: readonly KnowledgeEstimateV1[];
  associations: readonly ProfileAssociationV1[];
}>;

export type EpistemeProfileV1 = Readonly<{
  schemaVersion: 1;
  profileId: string;
  revision: number;
  updatedAt: string;
  evidence: readonly EpistemeEvidenceV1[];
  evidenceActions: readonly EvidenceActionV1[];
  projection: EpistemeProjectionV1;
  updates: readonly EpistemeUpdateReceiptV1[];
}>;

export type EpistemeUpdateCommandV1 = Readonly<{
  updateId: string;
  profileId: string;
  baseRevision: number;
  recordedAt: string;
  evidence: readonly EpistemeEvidenceV1[];
  evidenceActions: readonly EvidenceActionV1[];
}>;

export type EpistemeChangeV1 = Readonly<{
  entity: 'claim' | 'policy' | 'knowledge' | 'association';
  entityId: string;
  before: unknown | null;
  after: unknown | null;
}>;

export type EpistemeUpdateReceiptV1 = Readonly<{
  updateId: string;
  baseRevision: number;
  resultRevision: number;
  recordedAt: string;
  /** Canonical bytes to hash with SHA-256 at the persistence boundary. */
  idempotencyHashInput: string;
  acceptedEvidenceIds: readonly string[];
  actionIds: readonly string[];
  changes: readonly EpistemeChangeV1[];
}>;

export type EpistemeUpdateResultV1 = Readonly<{
  profile: EpistemeProfileV1;
  receipt: EpistemeUpdateReceiptV1;
  replayed: boolean;
}>;

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function nonEmpty(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= 500;
}

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function unique(values: readonly string[]): string[] {
  return [...new Set(values)].sort();
}

/** JSON canonicalization used for hashes, equality checks, and generated entity IDs. */
export function stableEpistemeStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null';
  if (Array.isArray(value)) return `[${value.map(stableEpistemeStringify).join(',')}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${stableEpistemeStringify(record[key])}`).join(',')}}`;
}

function validDate(value: string): boolean {
  return Number.isFinite(Date.parse(value));
}

function validIsoDateTime(value: unknown): value is string {
  return typeof value === 'string' && value.length <= 40 &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value));
}

function hasExactKeys(value: Record<string, unknown>, required: readonly string[], optional: readonly string[] = []): boolean {
  const allowed = new Set([...required, ...optional]);
  return required.every((key) => Object.hasOwn(value, key)) && Object.keys(value).every((key) => allowed.has(key));
}

function validScope(value: unknown): value is PreferenceScopeV1 {
  if (!isRecord(value) || !Object.keys(value).every((key) => ['mode', 'language', 'expiresAt'].includes(key))) return false;
  if (value.mode !== undefined && !nonEmpty(value.mode)) return false;
  if (value.language !== undefined && !nonEmpty(value.language)) return false;
  if (value.expiresAt !== undefined && (typeof value.expiresAt !== 'string' || !validDate(value.expiresAt))) return false;
  return true;
}

function validConcept(value: unknown): value is OpenConceptV1 {
  return isRecord(value) && hasExactKeys(value, ['conceptId', 'label'], ['language']) &&
    nonEmpty(value.conceptId) && nonEmpty(value.label) &&
    (value.language === undefined || nonEmpty(value.language));
}

function validateConcept(value: OpenConceptV1): void {
  assert(validConcept(value), 'Invalid open-vocabulary concept');
}

function claimKey(conceptId: string, scope: PreferenceScopeV1): string {
  return stableEpistemeStringify([conceptId, scope]);
}

function evidenceIdForTask(evidenceId: string, entryId: string, taskId: string): string {
  return `${evidenceId}/entry/${encodeURIComponent(entryId)}/task/${encodeURIComponent(taskId)}`;
}

function taskKey(task: Omit<KnowledgeTaskV1, 'contentReview'>): string {
  return stableEpistemeStringify([
    task.taskId,
    task.taskKind,
    task.direction,
    task.language,
    task.clueFamily
  ]);
}

function canonicalizeEvidence(evidence: readonly EpistemeEvidenceV1[]): EpistemeEvidenceV1[] {
  return [...evidence].sort((left, right) => left.evidenceId.localeCompare(right.evidenceId));
}

function canonicalizeActions(actions: readonly EvidenceActionV1[]): EvidenceActionV1[] {
  return [...actions].sort((left, right) => left.actionId.localeCompare(right.actionId));
}

function validateTask(task: KnowledgeTaskV1): void {
  assert(isRecord(task) && hasExactKeys(task, ['taskId', 'taskKind', 'direction', 'language', 'clueFamily', 'contentReview'], ['surfaceFamily', 'taskPack']), 'Knowledge task has unexpected fields');
  assert(nonEmpty(task.taskId) && nonEmpty(task.direction) && nonEmpty(task.language) && nonEmpty(task.clueFamily), 'Knowledge task identifiers and descriptors must be non-empty');
  assert(['sense', 'fact', 'answer-form', 'clue-mechanism'].includes(task.taskKind), 'Unknown knowledge task kind');
  if (task.surfaceFamily !== undefined) {
    assert(nonEmpty(task.surfaceFamily), 'Knowledge task surface family must be non-empty');
  }
  if (task.taskPack !== undefined) {
    assert(isRecord(task.taskPack), 'Knowledge task pack receipt must be an object');
    assert(hasExactKeys(task.taskPack, [
      'packId',
      'packVersion',
      'packDigest',
      'pairId',
      'sourceLanguage',
      'targetLanguage',
      'sourceText',
      'direction',
      'source',
      'grammar',
      'reviewStatus',
      'semanticStatus',
      'masteryClaim',
    ]), 'Knowledge task pack receipt has unexpected fields');
    for (const key of [
      'packId',
      'packVersion',
      'packDigest',
      'pairId',
      'sourceLanguage',
      'targetLanguage',
      'sourceText',
      'direction',
    ]) {
      assert(nonEmpty(task.taskPack[key]), `Knowledge task pack ${key} must be non-empty`);
    }
    assert(isRecord(task.taskPack.source) && isRecord(task.taskPack.grammar), 'Knowledge task pack source and grammar must be objects');
    assert(task.taskPack.reviewStatus === 'synthetic-unadmitted' || task.taskPack.reviewStatus === 'reviewed-admitted', 'Unknown knowledge task pack review status');
    assert(task.taskPack.semanticStatus === 'not-established' || task.taskPack.semanticStatus === 'reviewed', 'Unknown knowledge task pack semantic status');
    assert(task.taskPack.masteryClaim === 'none', 'Knowledge task pack cannot make a mastery claim');
  }
  assert(['approved', 'quarantined', 'unreviewed'].includes(task.contentReview), 'Unknown content review status');
}

function validateMapping(mapping: PreferenceMappingV1): void {
  assert(isRecord(mapping) && hasExactKeys(mapping, ['mappingId', 'concept', 'kind', 'stance', 'weight', 'scope']), 'Preference mapping has unexpected fields');
  assert(nonEmpty(mapping.mappingId), 'Preference mapping ID must be non-empty');
  validateConcept(mapping.concept);
  assert(['taste', 'goal', 'style', 'context'].includes(mapping.kind), 'Unknown claim kind');
  assert(mapping.stance === 'seek' || mapping.stance === 'avoid', 'Preference mapping stance must be seek or avoid');
  assert(finite(mapping.weight) && mapping.weight >= 0 && mapping.weight <= 1, 'Preference mapping weight must be in [0, 1]');
  assert(validScope(mapping.scope), 'Preference scope is invalid');
}

/** Runtime boundary validation; model text never becomes evidence by being well-shaped. */
export function validateEpistemeEvidence(value: unknown): value is EpistemeEvidenceV1 {
  if (!isRecord(value) || !nonEmpty(value.evidenceId) || typeof value.recordedAt !== 'string' || !validDate(value.recordedAt)) return false;
  try {
    switch (value.type) {
      case 'session-analysis': {
        if (!hasExactKeys(value, ['evidenceId', 'recordedAt', 'type', 'analysis', 'taskLinks'])) return false;
        if (!validateSessionAnalysis(value.analysis) || !Array.isArray(value.taskLinks)) return false;
        if (value.analysis.analysisVersion !== KNOWLEDGE_REDUCER_VERSION) return false;
        const observations = new Set(value.analysis.observations.map((observation) => observation.entryId));
        const seen = new Set<string>();
        for (const link of value.taskLinks) {
          if (!isRecord(link) || !hasExactKeys(link, ['entryId', 'tasks']) || !nonEmpty(link.entryId) || !observations.has(link.entryId as EntryId) || !Array.isArray(link.tasks)) return false;
          if (seen.has(link.entryId)) return false;
          seen.add(link.entryId);
          for (const task of link.tasks) validateTask(task);
          const taskKeys = link.tasks.map((item) => taskKey({
            taskId: item.taskId,
            taskKind: item.taskKind,
            direction: item.direction,
            language: item.language,
            clueFamily: item.clueFamily
          }));
          if (new Set(taskKeys).size !== taskKeys.length) return false;
        }
        return true;
      }
      case 'preference-signal': {
        if (!hasExactKeys(value, ['evidenceId', 'recordedAt', 'type', 'source', 'response', 'ambiguity', 'stimulusId', 'stimulusVersion', 'mappings'], ['sessionId'])) return false;
        if (!['reflection-card', 'ambiguous-association'].includes(value.source as string) || !['keep', 'not-for-me', 'pass'].includes(value.response as string)) return false;
        if (!['clear', 'ambiguous'].includes(value.ambiguity as string) || !nonEmpty(value.stimulusId) || !nonEmpty(value.stimulusVersion) || !isRecord(value.mappings)) return false;
        if (value.sessionId !== undefined && !nonEmpty(value.sessionId)) return false;
        const maps = value.mappings as PreferenceSignalEvidenceV1['mappings'];
        if (value.response === 'pass') return Object.keys(maps).length === 0;
        if (!Object.keys(maps).every((key) => key === 'keep' || key === 'not-for-me')) return false;
        for (const choices of Object.values(maps)) {
          if (!Array.isArray(choices)) return false;
          for (const mapping of choices) validateMapping(mapping);
          if (new Set(choices.map((mapping) => mapping.mappingId)).size !== choices.length) return false;
        }
        return true;
      }
      case 'explicit-preference':
        if (!hasExactKeys(value, ['evidenceId', 'recordedAt', 'type', 'concept', 'kind', 'action', 'scope', 'supersedesEvidenceIds'], ['userText'])) return false;
        if (!validConcept(value.concept)) return false;
        return ['taste', 'goal', 'style', 'context'].includes(value.kind as string) &&
          ['seek', 'exclude', 'clear'].includes(value.action as string) &&
          validScope(value.scope) && Array.isArray(value.supersedesEvidenceIds) &&
          value.supersedesEvidenceIds.every(nonEmpty) &&
          (value.userText === undefined || (typeof value.userText === 'string' && value.userText.length <= 2_000));
      case 'performance':
        if (!hasExactKeys(value, ['evidenceId', 'recordedAt', 'type', 'sessionId', 'measure', 'value'])) return false;
        return nonEmpty(value.sessionId) && ['correctness', 'speed', 'completion', 'hint-use', 'playtest-worth', 'playtest-return', 'playtest-rough-edge'].includes(value.measure as string) &&
          (typeof value.value === 'string' ? value.value.length <= 500 : finite(value.value));
      case 'association-proposal': {
        const baseKeys = ['evidenceId', 'recordedAt', 'type', 'associationId', 'phrase', 'language', 'relation', 'parentConceptIds', 'explanation', 'origin'];
        const model = value.origin === 'model-proposal' && (
          hasExactKeys(value, baseKeys) || hasExactKeys(value, [...baseKeys, 'expiresAt', 'expireAfterSessions'])
        );
        const calibration = value.origin === 'calibration-proposal' && hasExactKeys(value, [
          ...baseKeys,
          'calibrationId',
          'sourceObservationIds',
          'sourceStimulusIds',
          'expiresAt',
          'expireAfterSessions'
        ]);
        if (!model && !calibration) return false;
        if (!nonEmpty(value.associationId) || !nonEmpty(value.phrase) || !nonEmpty(value.language) ||
          !['adjacent', 'contrast', 'metaphor', 'sound', 'etymology'].includes(value.relation as string) ||
          !Array.isArray(value.parentConceptIds) || value.parentConceptIds.length === 0 || !value.parentConceptIds.every(nonEmpty) ||
          new Set(value.parentConceptIds).size !== value.parentConceptIds.length || !nonEmpty(value.explanation)) return false;
        if (model) {
          if (Object.hasOwn(value, 'expiresAt') || Object.hasOwn(value, 'expireAfterSessions')) {
            return validIsoDateTime(value.expiresAt) &&
              Date.parse(value.expiresAt as string) === Date.parse(value.recordedAt) + 30 * 86_400_000 &&
              value.expireAfterSessions === 10;
          }
          return true;
        }
        const observations = value.sourceObservationIds;
        const stimuli = value.sourceStimulusIds;
        return nonEmpty(value.calibrationId) && Array.isArray(observations) && observations.length >= 1 && observations.length <= 5 &&
          observations.every(nonEmpty) && new Set(observations).size === observations.length &&
          Array.isArray(stimuli) && stimuli.length >= 1 && stimuli.length <= 12 &&
          stimuli.every(nonEmpty) && new Set(stimuli).size === stimuli.length &&
          value.parentConceptIds.length === stimuli.length &&
          value.parentConceptIds.every((id, index) => id === stimuli[index]) &&
          validIsoDateTime(value.expiresAt) &&
          Date.parse(value.expiresAt) === Date.parse(value.recordedAt as string) + 14 * 86_400_000 &&
          value.expireAfterSessions === 5;
      }
      case 'association-response':
        if (!hasExactKeys(value, ['evidenceId', 'recordedAt', 'type', 'associationId', 'proposalEvidenceId', 'response'])) return false;
        return nonEmpty(value.associationId) && nonEmpty(value.proposalEvidenceId) &&
          ['keep', 'not-for-me', 'pass'].includes(value.response as string);
      default:
        return false;
    }
  } catch {
    return false;
  }
}

function validateAllEvidence(evidence: readonly EpistemeEvidenceV1[]): void {
  const ids = new Map<string, string>();
  for (const item of evidence) {
    assert(validateEpistemeEvidence(item), `Invalid episteme evidence: ${isRecord(item) ? String(item.evidenceId) : 'unknown'}`);
    const canonical = stableEpistemeStringify(item);
    const prior = ids.get(item.evidenceId);
    assert(prior === undefined || prior === canonical, `Conflicting evidence reuses ID ${item.evidenceId}`);
    ids.set(item.evidenceId, canonical);
  }
}

function interval(success: number, failure: number): readonly [number, number] {
  const alpha = 1 + success;
  const beta = 1 + failure;
  const total = alpha + beta;
  const mean = alpha / total;
  const standardError = Math.sqrt((alpha * beta) / (total * total * (total + 1)));
  return [Math.max(0, mean - 1.96 * standardError), Math.min(1, mean + 1.96 * standardError)];
}

function makeChannel(successWeight: number, failureWeight: number, evidenceCount: number): KnowledgeChannelV1 {
  const total = successWeight + failureWeight;
  return {
    successWeight,
    failureWeight,
    mean: (1 + successWeight) / (2 + total),
    interval: interval(successWeight, failureWeight),
    evidenceCount,
    insufficientEvidence: evidenceCount < 3
  };
}

type KnowledgeDelta = {
  task: Omit<KnowledgeTaskV1, 'contentReview'>;
  sessionId: string;
  evidenceId: string;
  recordedAt: string;
  independentSuccess: number;
  supportedSuccess: number;
  failure: number;
  failureChannel: 'independent' | 'supported' | null;
  exposure: boolean;
  qualifyingSupport: boolean;
  qualifyingFailure: boolean;
};

function knowledgeDeltas(evidence: readonly SessionAnalysisEvidenceV1[]): KnowledgeDelta[] {
  const deltas: KnowledgeDelta[] = [];
  for (const source of evidence) {
    const tasksByEntry = new Map(source.taskLinks.map((link) => [link.entryId, link.tasks] as const));
    for (const observation of source.analysis.observations) {
      const tasks = tasksByEntry.get(observation.entryId) ?? [];
      for (const task of tasks) {
        if (task.contentReview !== 'approved') continue;
        const taskRef: Omit<KnowledgeTaskV1, 'contentReview'> = {
          taskId: task.taskId,
          taskKind: task.taskKind,
          direction: task.direction,
          language: task.language,
          clueFamily: task.clueFamily
        };
        const id = evidenceIdForTask(source.evidenceId, observation.entryId, task.taskId);
        const noDisclosure = observation.revealedCellIds.length === 0 && observation.correctnessShownCellIds.length === 0;
        const manual = observation.inputMode === 'manual' && observation.attemptedCellIds.length > 0;
        const hasUnknown = observation.unknownProvenanceCellIds.length > 0;
        const independentSuccess = observation.finalState === 'correct' && observation.outcome === 'independent-retrieval' &&
          noDisclosure && manual && !hasUnknown && observation.prefilledFraction <= 0.2
          ? Math.min(1, Math.max(0, observation.independentSuccessWeight)) : 0;
        const supportedSuccess = observation.finalState === 'correct' && observation.outcome === 'supported-retrieval' &&
          noDisclosure && manual && !hasUnknown && observation.prefilledFraction > 0.2 && observation.prefilledFraction <= 0.6
          ? Math.min(SUPPORTED_RETRIEVAL_CAP, Math.max(0, observation.supportedSuccessWeight)) : 0;
        const failedAttempt = observation.incorrectAttemptCount > 0 &&
          (['check-assisted-correction', 'reveal-assisted-correction'].includes(observation.outcome) ||
            (observation.outcome === 'incorrect-attempt' && observation.correctnessShownCellIds.length > 0)) &&
          observation.prefilledFraction <= 0.6;
        const failure = failedAttempt
          ? Math.min(FAILED_ATTEMPT_CAP, Math.max(0, observation.failureWeight))
          : 0;
        const failureChannel = failure === 0 ? null : observation.prefilledFraction > 0.2 ? 'supported' : 'independent';
        const exposure = ['exposure', 'batch-entry', 'check-assisted-correction', 'check-confirmed', 'reveal-assisted-correction'].includes(observation.outcome);
        if (independentSuccess + supportedSuccess + failure === 0 && !exposure) continue;
        deltas.push({
          task: taskRef,
          sessionId: source.analysis.sessionId,
          evidenceId: id,
          recordedAt: source.recordedAt,
          independentSuccess,
          supportedSuccess,
          failure,
          failureChannel,
          exposure,
          qualifyingSupport: independentSuccess > 0 || supportedSuccess > 0,
          qualifyingFailure: failure > 0
        });
      }
    }
  }
  return deltas;
}

function buildKnowledge(evidence: readonly EpistemeEvidenceV1[]): KnowledgeEstimateV1[] {
  const sessionEntries = new Map<string, KnowledgeDelta[]>();
  const deltas = knowledgeDeltas(evidence.filter((item): item is SessionAnalysisEvidenceV1 => item.type === 'session-analysis'));
  for (const delta of deltas) {
    const key = stableEpistemeStringify([taskKey(delta.task), delta.sessionId]);
    const bucket = sessionEntries.get(key) ?? [];
    bucket.push(delta);
    sessionEntries.set(key, bucket);
  }

  const byTask = new Map<string, KnowledgeDelta[]>();
  for (const bucket of sessionEntries.values()) {
    const first = bucket[0];
    if (!first) continue;
    const key = taskKey(first.task);
    const entries = byTask.get(key) ?? [];
    // Apply caps in stable event order while retaining the exact sources that contributed.
    let remainingIndependent = 1;
    let remainingSupported = SUPPORTED_RETRIEVAL_CAP;
    let remainingFailure = FAILED_ATTEMPT_CAP;
    for (const item of bucket.sort((left, right) => left.recordedAt.localeCompare(right.recordedAt) || left.evidenceId.localeCompare(right.evidenceId))) {
      const independentSuccess = Math.min(remainingIndependent, item.independentSuccess);
      const supportedSuccess = Math.min(remainingSupported, item.supportedSuccess);
      const failure = Math.min(remainingFailure, item.failure);
      remainingIndependent -= independentSuccess;
      remainingSupported -= supportedSuccess;
      remainingFailure -= failure;
      entries.push({ ...item, independentSuccess, supportedSuccess, failure });
    }
    byTask.set(key, entries);
  }

  return [...byTask.entries()].map(([key, entries]) => {
    const task = entries[0]?.task;
    if (!task) throw new Error('Knowledge reduction lost its task key');
    const sessions = new Map<string, KnowledgeDelta[]>();
    for (const entry of entries) {
      const groupKey = stableEpistemeStringify([key, entry.sessionId]);
      const current = sessions.get(groupKey) ?? [];
      current.push(entry);
      sessions.set(groupKey, current);
    }
    const independentSuccess = entries.reduce((sum, item) => sum + item.independentSuccess, 0);
    const supportedSuccess = entries.reduce((sum, item) => sum + item.supportedSuccess, 0);
    const independentFailure = entries.filter((item) => item.failureChannel === 'independent').reduce((sum, item) => sum + item.failure, 0);
    const supportedFailure = entries.filter((item) => item.failureChannel === 'supported').reduce((sum, item) => sum + item.failure, 0);
    const supportEvidenceIds = unique(entries.filter((entry) => entry.qualifyingSupport).map((entry) => entry.evidenceId));
    const failureEvidenceIds = unique(entries.filter((entry) => entry.qualifyingFailure).map((entry) => entry.evidenceId));
    const exposureEvidenceIds = unique(entries.filter((entry) => entry.exposure).map((entry) => entry.evidenceId));
    const lastExposureAt = entries.filter((entry) => entry.exposure).map((entry) => entry.recordedAt).sort().at(-1);
    const lastIndependentAt = entries.filter((entry) => entry.independentSuccess > 0).map((entry) => entry.recordedAt).sort().at(-1);
    const independentEvidenceCount = new Set(entries.filter((entry) => entry.independentSuccess > 0 || (entry.failureChannel === 'independent' && entry.failure > 0)).map((entry) => entry.sessionId)).size;
    const supportedEvidenceCount = new Set(entries.filter((entry) => entry.supportedSuccess > 0 || (entry.failureChannel === 'supported' && entry.failure > 0)).map((entry) => entry.sessionId)).size;
    return {
      task,
      independent: makeChannel(independentSuccess, independentFailure, independentEvidenceCount),
      supported: makeChannel(supportedSuccess, supportedFailure, supportedEvidenceCount),
      supportEvidenceIds,
      failureEvidenceIds,
      exposureEvidenceIds,
      ...(lastExposureAt ? { lastExposureAt } : {}),
      ...(lastIndependentAt ? { lastIndependentAt } : {})
    };
  }).sort((left, right) => taskKey(left.task).localeCompare(taskKey(right.task)));
}

type WeightedSignal = Readonly<{
  mapping: PreferenceMappingV1;
  evidenceId: string;
  recordedAt: string;
  sessionId: string;
  explicit: boolean;
}>;

function decay(weight: number, recordedAt: string, asOf: string): number {
  const ageMs = Math.max(0, Date.parse(asOf) - Date.parse(recordedAt));
  const days = ageMs / 86_400_000;
  return weight * Math.pow(0.5, days / HALF_LIFE_DAYS);
}

function scopeIsActive(scope: PreferenceScopeV1, asOf: string): boolean {
  return scope.expiresAt === undefined || Date.parse(scope.expiresAt) > Date.parse(asOf);
}

function signalsFromEvidence(evidence: readonly EpistemeEvidenceV1[], asOf: string): WeightedSignal[] {
  const signals: WeightedSignal[] = [];
  const explicitItems = evidence.filter((item): item is ExplicitPreferenceEvidenceV1 => item.type === 'explicit-preference');
  const superseded = new Set(explicitItems.flatMap((item) => item.supersedesEvidenceIds));
  for (const item of evidence) {
    if (item.type === 'preference-signal' && item.response !== 'pass') {
      const maps = item.mappings[item.response] ?? [];
      const budget = item.source === 'ambiguous-association' || item.ambiguity === 'ambiguous'
        ? AMBIGUOUS_SIGNAL_EVENT_CAP
        : CLEAR_SIGNAL_EVENT_CAP;
      let remaining = budget;
      const sessionId = item.sessionId ?? `event:${item.evidenceId}`;
      for (const mapping of [...maps].sort((left, right) => left.mappingId.localeCompare(right.mappingId))) {
        if (!scopeIsActive(mapping.scope, asOf)) continue;
        const weight = Math.min(remaining, mapping.weight);
        remaining -= weight;
        if (weight <= 0) continue;
        signals.push({
          mapping: { ...mapping, weight },
          evidenceId: item.evidenceId,
          recordedAt: item.recordedAt,
          sessionId,
          explicit: false
        });
      }
    } else if (item.type === 'explicit-preference' && item.action !== 'clear' && !superseded.has(item.evidenceId) && scopeIsActive(item.scope, asOf)) {
      const stance = item.action === 'seek' ? 'seek' : 'avoid';
      signals.push({
        mapping: {
          mappingId: item.evidenceId,
          concept: item.concept,
          kind: item.kind,
          stance,
          weight: EXPLICIT_SAVE_WEIGHT,
          scope: item.scope
        },
        evidenceId: item.evidenceId,
        recordedAt: item.recordedAt,
        sessionId: `explicit:${item.evidenceId}`,
        explicit: true
      });
    }
  }
  return signals.sort((left, right) => left.recordedAt.localeCompare(right.recordedAt) || left.evidenceId.localeCompare(right.evidenceId) || left.mapping.mappingId.localeCompare(right.mapping.mappingId));
}

function buildPreferenceClaims(
  evidence: readonly EpistemeEvidenceV1[],
  asOf: string
): { claims: ProfileClaimV1[]; policies: ExplicitPolicyV1[] } {
  const signals = signalsFromEvidence(evidence, asOf);
  const usedBySessionFacet = new Map<string, number>();
  const weighted: Array<WeightedSignal & { decayedWeight: number }> = [];
  for (const signal of signals) {
    let effective = signal.mapping.weight;
    if (!signal.explicit) {
      const capKey = stableEpistemeStringify([signal.sessionId, signal.mapping.concept.conceptId]);
      const used = usedBySessionFacet.get(capKey) ?? 0;
      effective = Math.min(effective, Math.max(0, INFERRED_SESSION_CAP - used));
      usedBySessionFacet.set(capKey, used + effective);
      // Inferred scores decay toward neutral; explicit user evidence and controls do not.
      effective = decay(effective, signal.recordedAt, asOf);
    }
    if (effective > 0) weighted.push({ ...signal, decayedWeight: effective });
  }

  const explicitItems = evidence.filter((item): item is ExplicitPreferenceEvidenceV1 => item.type === 'explicit-preference');
  const superseded = new Set(explicitItems.flatMap((item) => item.supersedesEvidenceIds));
  const activeExplicit = explicitItems.filter((item) => !superseded.has(item.evidenceId) && scopeIsActive(item.scope, asOf));
  const grouped = new Map<string, Array<WeightedSignal & { decayedWeight: number }>>();
  for (const signal of weighted) {
    const key = claimKey(signal.mapping.concept.conceptId, signal.mapping.scope);
    const items = grouped.get(key) ?? [];
    items.push(signal);
    grouped.set(key, items);
  }
  // A clear action supersedes by reference but creates no replacement lock/score.
  for (const item of activeExplicit) {
    if (item.action === 'clear') continue;
    const key = claimKey(item.concept.conceptId, item.scope);
    if (!grouped.has(key)) grouped.set(key, []);
  }

  const policies: ExplicitPolicyV1[] = [];
  const claims: ProfileClaimV1[] = [];
  for (const [key, items] of grouped) {
    const exemplar = items[0];
    const explicitAtKey = activeExplicit.filter((item) => claimKey(item.concept.conceptId, item.scope) === key && item.action !== 'clear');
    const concepts = [
      ...items.map((item) => item.mapping.concept),
      ...explicitAtKey.map((item) => item.concept)
    ];
    const concept = concepts.sort((left, right) => stableEpistemeStringify(left).localeCompare(stableEpistemeStringify(right)))[0];
    if (!concept) continue;
    const scope = explicitAtKey[0]?.scope ?? exemplar?.mapping.scope ?? {};
    const kind = explicitAtKey[0]?.kind ?? exemplar?.mapping.kind ?? 'taste';
    const positive = items.filter((item) => item.mapping.stance === 'seek');
    const negative = items.filter((item) => item.mapping.stance === 'avoid');
    const positiveWeight = positive.reduce((sum, item) => sum + item.decayedWeight, 0);
    const negativeWeight = negative.reduce((sum, item) => sum + item.decayedWeight, 0);
    const explicitStances = new Set(explicitAtKey.map((item) => item.action));
    const policyMode = explicitStances.size > 1
      ? 'conflict'
      : explicitStances.has('seek') ? 'include'
        : explicitStances.has('exclude') ? 'exclude' : undefined;
    if (policyMode) {
      policies.push({
        conceptId: concept.conceptId,
        scope,
        mode: policyMode,
        evidenceIds: unique(explicitAtKey.map((item) => item.evidenceId)),
        lockedByUser: true
      });
    }
    if (positiveWeight + negativeWeight === 0 && !policyMode) continue;
    const stance: ClaimStanceV1 = policyMode === 'conflict' ||
      (policyMode === undefined && Math.abs(positiveWeight - negativeWeight) < 1e-9)
      ? 'ambivalent'
      : policyMode === 'include' ? 'seek'
        : policyMode === 'exclude' ? 'avoid'
          : positiveWeight > negativeWeight ? 'seek' : 'avoid';
    const support = stance === 'avoid' ? negative : positive;
    const counter = stance === 'avoid' ? positive : negative;
    const explicitEvidenceIds = unique(explicitAtKey.map((item) => item.evidenceId));
    const evidenceIds = explicitEvidenceIds.length > 0 && policyMode !== undefined
      ? explicitEvidenceIds
      : unique(support.map((item) => item.evidenceId));
    const counterEvidenceIds = policyMode !== undefined
      ? unique(items.map((item) => item.evidenceId).filter((id) => !explicitEvidenceIds.includes(id)))
      : unique(counter.map((item) => item.evidenceId));
    const authority = policyMode !== undefined ? 'explicit' : 'inferred';
    const adequacy: EvidenceAdequacyV1 = authority === 'explicit' ? 'explicit'
      : positive.length > 0 && negative.length > 0 ? 'contradictory'
        : new Set(items.map((item) => item.evidenceId)).size > 1 ? 'repeated' : 'single-signal';
    const claimId = `claim:${key}`;
    claims.push({
      claimId,
      concept,
      kind,
      stance,
      authority,
      strength: authority === 'explicit' ? 1 : Math.min(1, Math.max(positiveWeight, negativeWeight)),
      signedScore: Math.max(-1, Math.min(1, positiveWeight - negativeWeight)),
      positiveWeight: Math.min(1, positiveWeight),
      negativeWeight: Math.min(1, negativeWeight),
      adequacy,
      scope,
      evidenceIds,
      counterEvidenceIds,
      lockedByUser: authority === 'explicit'
    });
  }
  return {
    claims: claims.sort((left, right) => left.claimId.localeCompare(right.claimId)),
    policies: policies.sort((left, right) => claimKey(left.conceptId, left.scope).localeCompare(claimKey(right.conceptId, right.scope)))
  };
}

function buildAssociations(evidence: readonly EpistemeEvidenceV1[], asOf: string): ProfileAssociationV1[] {
  const knownConcepts = new Set<string>();
  for (const item of evidence) {
    if (item.type === 'explicit-preference') knownConcepts.add(item.concept.conceptId);
    if (item.type === 'preference-signal' && item.response !== 'pass') {
      for (const mapping of item.mappings[item.response] ?? []) knownConcepts.add(mapping.concept.conceptId);
    }
  }
  const proposals = evidence.filter((item): item is AssociationProposalEvidenceV1 => item.type === 'association-proposal');
  const responses = evidence.filter((item): item is AssociationResponseEvidenceV1 => item.type === 'association-response');
  const keptAssociationIds = new Set(responses.filter((response) => response.response === 'keep').map((response) => response.associationId));
  for (const proposal of proposals) {
    if (keptAssociationIds.has(proposal.associationId)) knownConcepts.add(`association:${proposal.associationId}`);
  }
  const byId = new Map<string, ProfileAssociationV1>();
  for (const proposal of proposals) {
    if (proposal.origin === 'model-proposal' && !proposal.parentConceptIds.every((parentId) => knownConcepts.has(parentId))) continue;
    const existing = byId.get(proposal.associationId);
    if (existing) {
      const sameProposal = stableEpistemeStringify({
        phrase: existing.phrase,
        language: existing.language,
        relation: existing.relation,
        parentConceptIds: existing.parentConceptIds,
        explanation: existing.explanation,
        origin: existing.origin,
        calibrationProvenance: existing.calibrationProvenance,
        modelProvenance: existing.modelProvenance
      }) === stableEpistemeStringify({
        phrase: proposal.phrase,
        language: proposal.language,
        relation: proposal.relation,
        parentConceptIds: unique(proposal.parentConceptIds),
        explanation: proposal.explanation,
        origin: proposal.origin,
        calibrationProvenance: calibrationProvenanceFor(proposal, evidence, asOf),
        modelProvenance: modelProvenanceFor(proposal, evidence, asOf)
      });
      assert(sameProposal, `Conflicting association proposal reuses ID ${proposal.associationId}`);
      continue;
    }
    const matching = responses.filter((response) => response.associationId === proposal.associationId && response.proposalEvidenceId === proposal.evidenceId);
    const latest = matching.sort((left, right) => left.recordedAt.localeCompare(right.recordedAt) || left.evidenceId.localeCompare(right.evidenceId)).at(-1);
    const response = latest?.response ?? null;
    const calibrationProvenance = calibrationProvenanceFor(proposal, evidence, asOf);
    const modelProvenance = modelProvenanceFor(proposal, evidence, asOf);
    const expired = calibrationProvenance?.expired ?? modelProvenance?.expired ?? false;
    byId.set(proposal.associationId, {
      associationId: proposal.associationId,
      phrase: proposal.phrase,
      language: proposal.language,
      relation: proposal.relation,
      parentConceptIds: unique(proposal.parentConceptIds),
      explanation: proposal.explanation,
      origin: proposal.origin,
      evidenceStatus: response === null ? 'untested' : 'responded-to',
      response: response === 'keep' ? 'kept' : response === 'not-for-me' ? 'rejected' : response === 'pass' ? 'passed' : null,
      supportEvidenceIds: response === 'keep' ? [latest!.evidenceId] : [],
      counterEvidenceIds: response === 'not-for-me' ? [latest!.evidenceId] : [],
      explorationWeight: response === 'keep' && !expired ? 0.05 : 0,
      calibrationProvenance,
      modelProvenance
    });
  }
  return [...byId.values()].sort((left, right) => left.associationId.localeCompare(right.associationId));
}

function modelProvenanceFor(
  proposal: AssociationProposalEvidenceV1,
  evidence: readonly EpistemeEvidenceV1[],
  asOf: string
): ProfileAssociationV1['modelProvenance'] {
  if (proposal.origin !== 'model-proposal' || proposal.expiresAt === undefined || proposal.expireAfterSessions === undefined) return null;
  const laterSessions = new Set(evidence.flatMap((item) =>
    item.type === 'session-analysis' && Date.parse(item.recordedAt) > Date.parse(proposal.recordedAt) && Date.parse(item.recordedAt) <= Date.parse(asOf)
      ? [item.analysis.sessionId]
      : []));
  const expirationReasons: Array<'age' | 'sessions'> = [];
  if (Date.parse(asOf) >= Date.parse(proposal.expiresAt)) expirationReasons.push('age');
  if (laterSessions.size >= proposal.expireAfterSessions) expirationReasons.push('sessions');
  return {
    expiresAt: proposal.expiresAt,
    expireAfterSessions: proposal.expireAfterSessions,
    expired: expirationReasons.length > 0,
    expirationReasons
  };
}

function calibrationProvenanceFor(
  proposal: AssociationProposalEvidenceV1,
  evidence: readonly EpistemeEvidenceV1[],
  asOf: string
): ProfileAssociationV1['calibrationProvenance'] {
  if (proposal.origin !== 'calibration-proposal') return null;
  const laterSessions = new Set(evidence.flatMap((item) =>
    item.type === 'session-analysis' && Date.parse(item.recordedAt) > Date.parse(proposal.recordedAt) && Date.parse(item.recordedAt) <= Date.parse(asOf)
      ? [item.analysis.sessionId]
      : []));
  const expirationReasons: Array<'age' | 'sessions'> = [];
  if (Date.parse(asOf) >= Date.parse(proposal.expiresAt)) expirationReasons.push('age');
  if (laterSessions.size >= proposal.expireAfterSessions) expirationReasons.push('sessions');
  return {
    calibrationId: proposal.calibrationId,
    sourceObservationIds: [...proposal.sourceObservationIds],
    sourceStimulusIds: [...proposal.sourceStimulusIds],
    expiresAt: proposal.expiresAt,
    expireAfterSessions: proposal.expireAfterSessions,
    expired: expirationReasons.length > 0,
    expirationReasons
  };
}

function liveEvidence(profile: EpistemeProfileV1): EpistemeEvidenceV1[] {
  const active = new Map<string, boolean>();
  for (const action of [...profile.evidenceActions].sort((left, right) => left.recordedAt.localeCompare(right.recordedAt) || left.actionId.localeCompare(right.actionId))) {
    active.set(action.targetEvidenceId, action.action === 'restore');
  }
  return profile.evidence.filter((item) => active.get(item.evidenceId) !== false);
}

/**
 * Rebuild the time-sensitive projection without creating a ledger revision or
 * changing the persisted evidence, actions, timestamps, or update receipts.
 */
export function projectEpistemeProfile(profile: EpistemeProfileV1, asOf: string): EpistemeProfileV1 {
  assert(validDate(asOf), 'Projection timestamp must be a valid date');
  return {
    ...profile,
    projection: reduceProjection(liveEvidence(profile), asOf)
  };
}

function reduceProjection(evidence: readonly EpistemeEvidenceV1[], asOf: string): EpistemeProjectionV1 {
  const { claims, policies } = buildPreferenceClaims(evidence, asOf);
  return {
    schemaVersion: 1,
    knowledgeReducerVersion: KNOWLEDGE_REDUCER_VERSION,
    preferenceReducerVersion: PREFERENCE_REDUCER_VERSION,
    associationReducerVersion: ASSOCIATION_REDUCER_VERSION,
    asOf,
    claims,
    policies,
    knowledge: buildKnowledge(evidence),
    associations: buildAssociations(evidence, asOf)
  };
}

/** Create a revision zero profile with no inferred interpretation. */
export function createEpistemeProfile(profileId: string, createdAt: string): EpistemeProfileV1 {
  assert(nonEmpty(profileId), 'Profile ID must be non-empty');
  assert(validDate(createdAt), 'Profile timestamp must be a valid date');
  return {
    schemaVersion: EPISTEME_SCHEMA_VERSION,
    profileId,
    revision: 0,
    updatedAt: createdAt,
    evidence: [],
    evidenceActions: [],
    projection: reduceProjection([], createdAt),
    updates: []
  };
}

function normalizeCommand(command: EpistemeUpdateCommandV1): EpistemeUpdateCommandV1 {
  return {
    ...command,
    evidence: canonicalizeEvidence(command.evidence),
    evidenceActions: canonicalizeActions(command.evidenceActions)
  };
}

/**
 * Return the exact canonical bytes a persistence adapter must SHA-256 for its idempotency key.
 * The same logical bundle has the same bytes regardless of evidence/action array order.
 */
export function canonicalEpistemeUpdateHashInput(command: EpistemeUpdateCommandV1): string {
  const normalized = normalizeCommand(command);
  return stableEpistemeStringify({
    profileId: normalized.profileId,
    baseRevision: normalized.baseRevision,
    evidence: normalized.evidence,
    evidenceActions: normalized.evidenceActions,
    knowledgeReducerVersion: KNOWLEDGE_REDUCER_VERSION,
    preferenceReducerVersion: PREFERENCE_REDUCER_VERSION,
    associationReducerVersion: ASSOCIATION_REDUCER_VERSION
  });
}

function diffById<T extends { [key: string]: unknown }>(
  entity: EpistemeChangeV1['entity'],
  before: readonly T[],
  after: readonly T[],
  getId: (item: T) => string
): EpistemeChangeV1[] {
  const left = new Map(before.map((item) => [getId(item), item] as const));
  const right = new Map(after.map((item) => [getId(item), item] as const));
  const ids = unique([...left.keys(), ...right.keys()]);
  return ids.flatMap((id) => {
    const oldValue = left.get(id) ?? null;
    const newValue = right.get(id) ?? null;
    if (stableEpistemeStringify(oldValue) === stableEpistemeStringify(newValue)) return [];
    return [{ entity, entityId: id, before: oldValue, after: newValue }];
  });
}

function profileChanges(before: EpistemeProjectionV1, after: EpistemeProjectionV1): EpistemeChangeV1[] {
  return [
    ...diffById('claim', before.claims, after.claims, (item) => item.claimId),
    ...diffById('policy', before.policies, after.policies, (item) => claimKey(item.conceptId, item.scope)),
    ...diffById('knowledge', before.knowledge, after.knowledge, (item) => taskKey(item.task)),
    ...diffById('association', before.associations, after.associations, (item) => item.associationId)
  ];
}

function assertActions(actions: readonly EvidenceActionV1[], evidenceIds: ReadonlySet<string>): void {
  const seen = new Map<string, string>();
  for (const action of actions) {
    assert(nonEmpty(action.actionId) && validDate(action.recordedAt) && nonEmpty(action.targetEvidenceId), 'Invalid evidence action');
    assert(action.action === 'retract' || action.action === 'restore', 'Unknown evidence action');
    assert(evidenceIds.has(action.targetEvidenceId), `Evidence action references missing evidence ${action.targetEvidenceId}`);
    const canonical = stableEpistemeStringify(action);
    const previous = seen.get(action.actionId);
    assert(previous === undefined || previous === canonical, `Conflicting action reuses ID ${action.actionId}`);
    seen.set(action.actionId, canonical);
  }
}

function assertEvidenceReferences(evidence: readonly EpistemeEvidenceV1[]): void {
  const byId = new Map(evidence.map((item) => [item.evidenceId, item] as const));
  for (const item of evidence) {
    if (item.type === 'explicit-preference') {
      for (const supersededId of item.supersedesEvidenceIds) {
        const old = byId.get(supersededId);
        assert(old !== undefined, `Explicit correction references missing evidence ${supersededId}`);
        const sameFacet = old.type === 'explicit-preference'
          ? old.concept.conceptId === item.concept.conceptId && claimKey(old.concept.conceptId, old.scope) === claimKey(item.concept.conceptId, item.scope)
          : old.type === 'preference-signal' && old.response !== 'pass' &&
            (old.mappings[old.response] ?? []).some((mapping) => mapping.concept.conceptId === item.concept.conceptId && claimKey(mapping.concept.conceptId, mapping.scope) === claimKey(item.concept.conceptId, item.scope));
        assert(sameFacet, `Explicit correction ${item.evidenceId} cannot supersede unrelated evidence ${supersededId}`);
      }
    }
    if (item.type === 'association-response') {
      const proposal = byId.get(item.proposalEvidenceId);
      assert(proposal?.type === 'association-proposal' && proposal.associationId === item.associationId,
        `Association response ${item.evidenceId} does not link to its exact proposal`);
    }
  }
}

/**
 * Apply an immutable evidence batch with compare-and-swap revision semantics.
 * Projections are rebuilt from the evidence ledger, so retraction and restoration are reversible.
 */
export function applyEpistemeUpdate(
  profile: EpistemeProfileV1,
  input: EpistemeUpdateCommandV1
): EpistemeUpdateResultV1 {
  const command = normalizeCommand(input);
  assert(command.profileId === profile.profileId, 'Profile ID mismatch');
  assert(nonEmpty(command.updateId) && validDate(command.recordedAt), 'Invalid update identity/timestamp');
  validateAllEvidence(command.evidence);
  const hashInput = canonicalEpistemeUpdateHashInput(command);
  const prior = profile.updates.find((receipt) => receipt.idempotencyHashInput === hashInput);
  if (prior) return { profile, receipt: prior, replayed: true };
  assert(!profile.updates.some((receipt) => receipt.updateId === command.updateId), 'Episteme updateId was reused with different evidence');
  assert(command.baseRevision === profile.revision, `Stale profile revision: expected ${profile.revision}, received ${command.baseRevision}`);

  const evidenceById = new Map(profile.evidence.map((item) => [item.evidenceId, item] as const));
  for (const item of command.evidence) {
    const previous = evidenceById.get(item.evidenceId);
    assert(previous === undefined || stableEpistemeStringify(previous) === stableEpistemeStringify(item), `Conflicting evidence reuses ID ${item.evidenceId}`);
    evidenceById.set(item.evidenceId, item);
  }
  const evidence = canonicalizeEvidence([...evidenceById.values()]);
  assertEvidenceReferences(evidence);
  const allEvidenceIds = new Set(evidence.map((item) => item.evidenceId));
  assertActions(command.evidenceActions, allEvidenceIds);
  const actionsById = new Map(profile.evidenceActions.map((item) => [item.actionId, item] as const));
  for (const action of command.evidenceActions) {
    const previous = actionsById.get(action.actionId);
    assert(previous === undefined || stableEpistemeStringify(previous) === stableEpistemeStringify(action), `Conflicting action reuses ID ${action.actionId}`);
    actionsById.set(action.actionId, action);
  }
  const evidenceActions = canonicalizeActions([...actionsById.values()]);
  const provisional: EpistemeProfileV1 = {
    ...profile,
    revision: profile.revision + 1,
    updatedAt: command.recordedAt,
    evidence,
    evidenceActions,
    projection: reduceProjection(liveEvidence({ ...profile, evidence, evidenceActions }), command.recordedAt)
  };
  const receipt: EpistemeUpdateReceiptV1 = {
    updateId: command.updateId,
    baseRevision: profile.revision,
    resultRevision: provisional.revision,
    recordedAt: command.recordedAt,
    idempotencyHashInput: hashInput,
    acceptedEvidenceIds: command.evidence.map((item) => item.evidenceId),
    actionIds: command.evidenceActions.map((item) => item.actionId),
    changes: profileChanges(profile.projection, provisional.projection)
  };
  const updated: EpistemeProfileV1 = { ...provisional, updates: [...profile.updates, receipt] };
  return { profile: updated, receipt, replayed: false };
}
