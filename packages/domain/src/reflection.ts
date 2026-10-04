import { validateEpistemeEvidence } from './episteme';
import type {
  EvidenceActionV1,
  PreferenceMappingV1,
  PreferenceScopeV1,
  PreferenceSignalEvidenceV1
} from './episteme';

export const REFLECTION_CARD_SCHEMA_VERSION = 1 as const;
export const REFLECTION_RESPONSE_SCHEMA_VERSION = 1 as const;
export const REFLECTION_ACTION_SCHEMA_VERSION = 1 as const;
export const REFLECTION_RESPONSE_BUDGET = 0.2;
export const AMBIGUOUS_REFLECTION_BUDGET = 0.05;
export const REFLECTION_NEGATIVE_SCOPE_MAX_DAYS = 90;

export type ReflectionResponseKindV1 = 'keep' | 'not-for-me' | 'pass';
export type ReflectionCardStatusV1 = 'pending' | 'approved' | 'rejected';

export type ReflectionGenerationReceiptV1 = Readonly<{
  generationId: string;
  model: string;
  promptVersion: string;
  generatedAt: string;
  reviewStatus: ReflectionCardStatusV1;
  reviewedAt?: string;
}>;

/**
 * A response-independent, reviewed interpretation of one reflection card.
 * Keep and not-for-me mappings are authored separately; one is never derived by
 * negating the other. Maps include the exact scope in which the signal may act.
 */
export type ReflectionCardV1 = Readonly<{
  schemaVersion: typeof REFLECTION_CARD_SCHEMA_VERSION;
  cardId: string;
  version: number;
  createdAt: string;
  expiresAt?: string;
  text: string;
  language: string;
  relatedEntryIds: readonly string[];
  source: 'authored' | 'model';
  status: ReflectionCardStatusV1;
  tone: 'lyrical' | 'wry' | 'plain' | 'curious';
  ambiguity: 'clear' | 'ambiguous';
  interpretation: Readonly<{
    keep: string;
    notForMe: string;
    pass: string;
  }>;
  keepMappings: readonly PreferenceMappingV1[];
  notForMeMappings: readonly PreferenceMappingV1[];
  groundingRefs: readonly string[];
  generationReceipt: ReflectionGenerationReceiptV1 | null;
}>;

/** Immutable response record. Deliberately has no duration, speed, or gesture-strength field. */
export type ReflectionResponseV1 = Readonly<{
  schemaVersion: typeof REFLECTION_RESPONSE_SCHEMA_VERSION;
  responseId: string;
  cardId: string;
  cardVersion: number;
  sessionId?: string;
  shownPosition: 0 | 1 | 2;
  recordedAt: string;
  response: ReflectionResponseKindV1;
}>;

/** Undo and restore link to the original response evidence instead of deleting it. */
export type ReflectionResponseActionV1 = Readonly<{
  schemaVersion: typeof REFLECTION_ACTION_SCHEMA_VERSION;
  actionId: string;
  targetResponseId: string;
  recordedAt: string;
  action: 'retract' | 'restore';
  reason?: string;
}>;

type RecordValue = Record<string, unknown>;

function isRecord(value: unknown): value is RecordValue {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: RecordValue,
  required: readonly string[],
  optional: readonly string[] = []
): boolean {
  const allowed = new Set([...required, ...optional]);
  return required.every((key) => Object.hasOwn(value, key)) && Object.keys(value).every((key) => allowed.has(key));
}

function nonEmpty(value: unknown, max = 240): value is string {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= max && value.trim() === value;
}

function validDate(value: unknown): value is string {
  return typeof value === 'string' && value.length <= 40 &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value));
}

function validLanguage(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/.test(value);
}

function validStringList(value: unknown, maxCount: number, maxLength = 160): value is string[] {
  return Array.isArray(value) && value.length <= maxCount && value.every((item) => nonEmpty(item, maxLength)) &&
    new Set(value).size === value.length;
}

function validScope(value: unknown): value is PreferenceScopeV1 {
  if (!isRecord(value) || !hasExactKeys(value, [], ['mode', 'language', 'expiresAt'])) return false;
  return (value.mode === undefined || nonEmpty(value.mode, 80)) &&
    (value.language === undefined || validLanguage(value.language)) &&
    (value.expiresAt === undefined || validDate(value.expiresAt));
}

function validMapping(value: unknown, expectedStance: 'seek' | 'avoid'): value is PreferenceMappingV1 {
  if (!isRecord(value) || !hasExactKeys(value, ['mappingId', 'concept', 'kind', 'stance', 'weight', 'scope'])) return false;
  if (!nonEmpty(value.mappingId, 160) || !isRecord(value.concept) ||
      !hasExactKeys(value.concept, ['conceptId', 'label'], ['language']) ||
      !nonEmpty(value.concept.conceptId, 160) || !nonEmpty(value.concept.label) ||
      (value.concept.language !== undefined && !validLanguage(value.concept.language)) ||
      !['taste', 'goal', 'style', 'context'].includes(value.kind as string) ||
      value.stance !== expectedStance || typeof value.weight !== 'number' || !Number.isFinite(value.weight) ||
      value.weight <= 0 || value.weight > REFLECTION_RESPONSE_BUDGET || !validScope(value.scope)) return false;
  return true;
}

function validMappings(
  value: unknown,
  expectedStance: 'seek' | 'avoid',
  budget: number
): value is readonly PreferenceMappingV1[] {
  if (!Array.isArray(value) || value.length > 3 || !value.every((item) => validMapping(item, expectedStance))) return false;
  const ids = value.map((item) => item.mappingId);
  const totalWeight = value.reduce((total, item) => total + item.weight, 0);
  return new Set(ids).size === ids.length && totalWeight <= budget + 1e-9;
}

function validGenerationReceipt(value: unknown, status: ReflectionCardStatusV1): boolean {
  if (!isRecord(value) || !hasExactKeys(
    value,
    ['generationId', 'model', 'promptVersion', 'generatedAt', 'reviewStatus'],
    ['reviewedAt']
  )) return false;
  if (!nonEmpty(value.generationId, 160) || !nonEmpty(value.model, 120) || !nonEmpty(value.promptVersion, 120) ||
      !validDate(value.generatedAt) || !['pending', 'approved', 'rejected'].includes(value.reviewStatus as string) ||
      value.reviewStatus !== status) return false;
  if (status === 'pending') return value.reviewedAt === undefined;
  return validDate(value.reviewedAt);
}

function validInterpretation(value: unknown): boolean {
  return isRecord(value) && hasExactKeys(value, ['keep', 'notForMe', 'pass']) &&
    nonEmpty(value.keep) && nonEmpty(value.notForMe) && nonEmpty(value.pass);
}

/** Validate a card, including the independently declared maps and their evidence budget. */
export function validateReflectionCard(value: unknown): value is ReflectionCardV1 {
  if (!isRecord(value) || !hasExactKeys(
    value,
    [
      'schemaVersion', 'cardId', 'version', 'createdAt', 'text', 'language', 'relatedEntryIds',
      'source', 'status', 'tone', 'ambiguity', 'interpretation', 'keepMappings', 'notForMeMappings',
      'groundingRefs', 'generationReceipt'
    ],
    ['expiresAt']
  )) return false;
  if (value.schemaVersion !== REFLECTION_CARD_SCHEMA_VERSION || !nonEmpty(value.cardId, 160) ||
      typeof value.version !== 'number' || !Number.isSafeInteger(value.version) || value.version < 1 ||
      !validDate(value.createdAt) || (value.expiresAt !== undefined && !validDate(value.expiresAt)) ||
      !nonEmpty(value.text) || !validLanguage(value.language) ||
      !validStringList(value.relatedEntryIds, 12) ||
      !['authored', 'model'].includes(value.source as string) ||
      !['pending', 'approved', 'rejected'].includes(value.status as string) ||
      !['lyrical', 'wry', 'plain', 'curious'].includes(value.tone as string) ||
      !['clear', 'ambiguous'].includes(value.ambiguity as string) ||
      !validInterpretation(value.interpretation) || !validStringList(value.groundingRefs, 20)) return false;

  const cap = value.ambiguity === 'ambiguous' ? AMBIGUOUS_REFLECTION_BUDGET : REFLECTION_RESPONSE_BUDGET;
  if (!validMappings(value.keepMappings, 'seek', cap) || !validMappings(value.notForMeMappings, 'avoid', cap)) return false;
  const keepMappings = value.keepMappings as readonly PreferenceMappingV1[];
  const notForMeMappings = value.notForMeMappings as readonly PreferenceMappingV1[];
  const cardCreatedAt = value.createdAt as string;
  const allMappingIds = [...keepMappings.map((mapping) => mapping.mappingId),
    ...notForMeMappings.map((mapping) => mapping.mappingId)];
  if (new Set(allMappingIds).size !== allMappingIds.length) return false;

  // One card can reject at most one narrow, temporary, mode-scoped facet.
  if (notForMeMappings.length > 1 || notForMeMappings.some((mapping) => {
    const mode = mapping.scope.mode;
    const expiresAt = mapping.scope.expiresAt;
    return !mode || !expiresAt || Date.parse(expiresAt) <= Date.parse(cardCreatedAt) ||
      Date.parse(expiresAt) - Date.parse(cardCreatedAt) > REFLECTION_NEGATIVE_SCOPE_MAX_DAYS * 86_400_000;
  })) return false;

  if (value.expiresAt !== undefined && Date.parse(value.expiresAt as string) <= Date.parse(value.createdAt as string)) return false;
  if (value.source === 'authored') return value.generationReceipt === null;
  return validGenerationReceipt(value.generationReceipt, value.status as ReflectionCardStatusV1);
}

/** A structurally sound proposal is not yet allowed to influence a player's profile. */
export function isPlayableReflectionCard(value: unknown): value is ReflectionCardV1 {
  return validateReflectionCard(value) && value.status === 'approved';
}

/** Validate a stored response and, when supplied, bind it to the exact frozen card version. */
export function validateReflectionResponse(value: unknown, card?: ReflectionCardV1): value is ReflectionResponseV1 {
  if (!isRecord(value) || !hasExactKeys(
    value,
    ['schemaVersion', 'responseId', 'cardId', 'cardVersion', 'shownPosition', 'recordedAt', 'response'],
    ['sessionId']
  ) || value.schemaVersion !== REFLECTION_RESPONSE_SCHEMA_VERSION || !nonEmpty(value.responseId, 160) ||
      !nonEmpty(value.cardId, 160) || typeof value.cardVersion !== 'number' ||
      !Number.isSafeInteger(value.cardVersion) || value.cardVersion < 1 ||
      ![0, 1, 2].includes(value.shownPosition as number) || !validDate(value.recordedAt) ||
      !['keep', 'not-for-me', 'pass'].includes(value.response as string) ||
      (value.sessionId !== undefined && !nonEmpty(value.sessionId, 160))) return false;
  return card === undefined || (isPlayableReflectionCard(card) && value.cardId === card.cardId && value.cardVersion === card.version);
}

/** Validate an immutable undo/retraction link. It carries no preference mapping itself. */
export function validateReflectionResponseAction(value: unknown): value is ReflectionResponseActionV1 {
  return isRecord(value) && hasExactKeys(
    value,
    ['schemaVersion', 'actionId', 'targetResponseId', 'recordedAt', 'action'],
    ['reason']
  ) && value.schemaVersion === REFLECTION_ACTION_SCHEMA_VERSION &&
    nonEmpty(value.actionId, 160) && nonEmpty(value.targetResponseId, 160) && validDate(value.recordedAt) &&
    (value.action === 'retract' || value.action === 'restore') &&
    (value.reason === undefined || nonEmpty(value.reason));
}

/** Convert one validated response to the existing evidence-ledger shape. Pass has no mappings. */
export function reflectionResponseToEvidence(
  card: ReflectionCardV1,
  response: ReflectionResponseV1
): PreferenceSignalEvidenceV1 {
  if (!isPlayableReflectionCard(card)) throw new Error('Reflection card must be valid and approved');
  if (!validateReflectionResponse(response, card)) throw new Error('Reflection response must match this exact card version');

  const mappings: PreferenceSignalEvidenceV1['mappings'] = response.response === 'pass'
    ? {}
    : response.response === 'keep'
      ? { keep: card.keepMappings }
      : { 'not-for-me': card.notForMeMappings };
  const evidence: PreferenceSignalEvidenceV1 = {
    evidenceId: response.responseId,
    recordedAt: response.recordedAt,
    type: 'preference-signal',
    source: 'reflection-card',
    ...(response.sessionId === undefined ? {} : { sessionId: response.sessionId }),
    response: response.response,
    ambiguity: card.ambiguity,
    stimulusId: card.cardId,
    stimulusVersion: String(card.version),
    mappings
  };
  if (!validateEpistemeEvidence(evidence)) throw new Error('Reflection response did not produce valid episteme evidence');
  return evidence;
}

/** Convert undo/redo into the episteme ledger's reversible evidence action. */
export function reflectionActionToEvidenceAction(action: ReflectionResponseActionV1): EvidenceActionV1 {
  if (!validateReflectionResponseAction(action)) throw new Error('Invalid reflection response action');
  return {
    actionId: action.actionId,
    recordedAt: action.recordedAt,
    targetEvidenceId: action.targetResponseId,
    action: action.action,
    ...(action.reason === undefined ? {} : { reason: action.reason })
  };
}
