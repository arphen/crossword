import { validatePuzzle } from './puzzle';
import type { CellId, EntryId, PuzzleDocument } from './puzzle';
import type { PuzzleDocumentV2 } from './puzzleV2';

/** A canonical crossword token. Multi-character tokens leave room for rebus and language packs. */
export type SolveTokenV2 = string;

export type SolveEventV2Base = Readonly<{
  schemaVersion: 2;
  eventId: string;
  sessionId: string;
  profileId?: string;
  segmentId: string;
  seq: number;
  elapsedMs: number;
  recordedAt: string;
  puzzleHash: string;
}>;

export type VisiblePatternCellV2 = Readonly<{
  cellId: CellId;
  token: SolveTokenV2 | null;
  origin: 'player' | 'crossing' | 'reveal' | 'unknown';
  sourceEntryId: EntryId | null;
}>;

export type SolveEventV2 = SolveEventV2Base &
  (
    | Readonly<{
        type: 'session-started';
        reason: 'fresh';
      }>
    | Readonly<{
        type: 'session-resumed';
        reason: 'reload' | 'handoff';
        snapshotSeq: number;
      }>
    | Readonly<{
        type: 'session-finished';
        reason: 'complete' | 'stopped' | 'abandoned';
      }>
    | Readonly<{
        type: 'visibility-changed';
        visibility: 'visible' | 'hidden';
      }>
    | Readonly<{
        type: 'paused' | 'resumed';
        reason: 'user' | 'background' | 'system';
      }>
    | Readonly<{
        type: 'entry-focused';
        entryId: EntryId;
        variantId: string | null;
        reason: 'pointer' | 'keyboard' | 'programmatic';
        visiblePattern: readonly VisiblePatternCellV2[];
      }>
    | Readonly<{
        type: 'cell-written';
        cellId: CellId;
        beforeToken: SolveTokenV2 | null;
        afterToken: SolveTokenV2;
        activeEntryId: EntryId | null;
        actionId: string;
        source:
          | 'keyboard'
          | 'touch'
          | 'accessibility'
          | 'composition'
          | 'unknown';
      }>
    | Readonly<{
        type: 'cell-cleared';
        cellId: CellId;
        beforeToken: SolveTokenV2 | null;
        activeEntryId: EntryId | null;
        actionId: string;
        source:
          | 'keyboard'
          | 'touch'
          | 'accessibility'
          | 'composition'
          | 'unknown';
      }>
    | Readonly<{
        type: 'batch-entered';
        activeEntryId: EntryId | null;
        actionId: string;
        source: 'paste' | 'composition' | 'unknown';
        edits: readonly Readonly<{
          cellId: CellId;
          beforeToken: SolveTokenV2 | null;
          afterToken: SolveTokenV2;
        }>[];
      }>
    | Readonly<{
        type: 'check-result-shown';
        scope: 'cell' | 'entry' | 'puzzle';
        entryId: EntryId | null;
        results: readonly Readonly<{
          cellId: CellId;
          token: SolveTokenV2 | null;
          classification: 'correct' | 'incorrect' | 'blank';
        }>[];
      }>
    | Readonly<{
        type: 'answer-revealed';
        scope: 'cell' | 'entry' | 'puzzle';
        entryId: EntryId | null;
        cells: readonly Readonly<{
          cellId: CellId;
          beforeToken: SolveTokenV2 | null;
          token: SolveTokenV2;
        }>[];
      }>
    | Readonly<{
        type: 'hint-shown';
        entryId: EntryId;
        hintId: string;
        assistanceTier: 'clue-reading' | 'context' | 'crossing' | 'letter' | 'answer';
        affectedCellIds: readonly CellId[];
      }>
  );

export type SolveSessionV2 = Readonly<{
  schemaVersion: 2;
  sessionId: string;
  profileId?: string;
  puzzleHash: string;
  /** Imported or otherwise unjournaled letters must stay explicitly unknown. */
  initialGrid: readonly Readonly<{
    cellId: CellId;
    token: SolveTokenV2 | null;
    origin: 'unknown';
  }>[];
  events: readonly SolveEventV2[];
}>;

export type EntryObservation = Readonly<{
  sessionId: string;
  puzzleHash: string;
  entryId: EntryId;
  finalState: 'correct' | 'incorrect' | 'incomplete' | 'indeterminate';
  outcome:
    | 'independent-retrieval'
    | 'supported-retrieval'
    | 'exposure'
    | 'check-assisted-correction'
    | 'reveal-assisted-correction'
    | 'check-confirmed'
    | 'batch-entry'
    | 'incorrect-attempt'
    | 'untouched'
    | 'indeterminate';
  inputMode: 'none' | 'manual' | 'batch' | 'mixed';
  /** Filled crossing, revealed, or unknown-provenance cells divided by entry length. */
  prefilledFraction: number;
  /** Exact positions whose value came from another crossing entry. */
  supportCellIds: readonly CellId[];
  revealedCellIds: readonly CellId[];
  correctnessShownCellIds: readonly CellId[];
  unknownProvenanceCellIds: readonly CellId[];
  attemptedCellIds: readonly CellId[];
  checkCorrectedCellIds: readonly CellId[];
  revealCorrectedCellIds: readonly CellId[];
  /** Distinct incorrect checked patterns, deduplicated within this session and answer. */
  incorrectAttemptCount: number;
  independentSuccessWeight: number;
  supportedSuccessWeight: number;
  failureWeight: number;
}>;

export type SessionAnalysis = Readonly<{
  schemaVersion: 1;
  analysisVersion: 'knowledge-reducer-v1';
  sessionId: string;
  puzzleHash: string;
  observations: readonly EntryObservation[];
}>;

const MAX_ID_LENGTH = 160;
const MAX_TOKEN_LENGTH = 24;
const MAX_EVENT_COUNT = 50_000;
const MAX_INITIAL_CELL_COUNT = 500;
const MAX_ENTRY_CELLS = 100;
const MAX_BATCH_EDITS = 500;

type RecordValue = Record<string, unknown>;

/** Minimal verified puzzle data consumed by the shared deterministic replay. */
type ReplayPuzzleCell = Readonly<{ id: CellId; block: boolean }>;
type ReplayPuzzleEntry = Readonly<{
  id: EntryId;
  cellIds: readonly CellId[];
  answer: string;
}>;
type ReplayPuzzleDocument = Readonly<{
  cells: readonly ReplayPuzzleCell[];
  entries: readonly ReplayPuzzleEntry[];
  integrity: Readonly<{ value: string }>;
}>;

function isRecord(value: unknown): value is RecordValue {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: RecordValue,
  required: readonly string[],
  optional: readonly string[] = [],
): boolean {
  const allowed = new Set([...required, ...optional]);
  return (
    required.every((key) => Object.hasOwn(value, key)) &&
    Object.keys(value).every((key) => allowed.has(key))
  );
}

function isBoundedString(value: unknown, max = MAX_ID_LENGTH): value is string {
  return (
    typeof value === 'string' && value.trim().length > 0 && value.length <= max
  );
}

function isToken(value: unknown): value is SolveTokenV2 {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    value.length <= MAX_TOKEN_LENGTH &&
    value.trim() === value &&
    value.normalize('NFC') === value
  );
}

function isNullableToken(value: unknown): value is SolveTokenV2 | null {
  return value === null || isToken(value);
}

function isNullableId(value: unknown): value is string | null {
  return value === null || isBoundedString(value);
}

function isFiniteNonNegative(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

function isRecordedAt(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 40) return false;
  return (
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(
      value,
    ) && Number.isFinite(Date.parse(value))
  );
}

function isStringArray(
  value: unknown,
  maxLength = MAX_ENTRY_CELLS,
): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= maxLength &&
    value.every((item) => isBoundedString(item)) &&
    new Set(value).size === value.length
  );
}

function isEnvelope(value: RecordValue): boolean {
  return (
    value.schemaVersion === 2 &&
    isBoundedString(value.eventId) &&
    isBoundedString(value.sessionId) &&
    (value.profileId === undefined || isBoundedString(value.profileId)) &&
    isBoundedString(value.segmentId) &&
    isPositiveInteger(value.seq) &&
    isFiniteNonNegative(value.elapsedMs) &&
    isRecordedAt(value.recordedAt) &&
    isBoundedString(value.puzzleHash)
  );
}

function validateVisiblePatternCell(
  value: unknown,
): value is VisiblePatternCellV2 {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ['cellId', 'token', 'origin', 'sourceEntryId'])
  )
    return false;
  if (!isBoundedString(value.cellId) || !isNullableToken(value.token))
    return false;
  if (
    !['player', 'crossing', 'reveal', 'unknown'].includes(
      value.origin as string,
    )
  )
    return false;
  if (!isNullableId(value.sourceEntryId)) return false;
  if (value.origin === 'player' || value.origin === 'crossing')
    return value.sourceEntryId !== null;
  return value.sourceEntryId === null;
}

function isEventType(value: unknown): value is SolveEventV2['type'] {
  return (
    typeof value === 'string' &&
    [
      'session-started',
      'session-resumed',
      'session-finished',
      'visibility-changed',
      'paused',
      'resumed',
      'entry-focused',
      'cell-written',
      'cell-cleared',
      'batch-entered',
      'check-result-shown',
      'answer-revealed',
      'hint-shown',
    ].includes(value)
  );
}

/** Strict shape validation for version 2 semantic solve events. */
export function validateSolveEventV2(value: unknown): value is SolveEventV2 {
  if (!isRecord(value) || !isEnvelope(value) || !isEventType(value.type))
    return false;
  const envelopeKeys = [
    'schemaVersion',
    'eventId',
    'sessionId',
    'segmentId',
    'seq',
    'elapsedMs',
    'recordedAt',
    'puzzleHash',
  ];
  if (Object.hasOwn(value, 'profileId')) envelopeKeys.push('profileId');
  const exact = (payload: readonly string[]) =>
    hasExactKeys(value, [...envelopeKeys, 'type', ...payload]);

  switch (value.type) {
    case 'session-started':
      return exact(['reason']) && value.reason === 'fresh';
    case 'session-resumed':
      return (
        exact(['reason', 'snapshotSeq']) &&
        ['reload', 'handoff'].includes(value.reason as string) &&
        Number.isSafeInteger(value.snapshotSeq) &&
        (value.snapshotSeq as number) >= 0
      );
    case 'session-finished':
      return (
        exact(['reason']) &&
        ['complete', 'stopped', 'abandoned'].includes(value.reason as string)
      );
    case 'visibility-changed':
      return (
        exact(['visibility']) &&
        ['visible', 'hidden'].includes(value.visibility as string)
      );
    case 'paused':
    case 'resumed':
      return (
        exact(['reason']) &&
        ['user', 'background', 'system'].includes(value.reason as string)
      );
    case 'entry-focused':
      return (
        exact(['entryId', 'variantId', 'reason', 'visiblePattern']) &&
        isBoundedString(value.entryId) &&
        (value.variantId === null || isBoundedString(value.variantId)) &&
        ['pointer', 'keyboard', 'programmatic'].includes(
          value.reason as string,
        ) &&
        Array.isArray(value.visiblePattern) &&
        value.visiblePattern.length <= MAX_ENTRY_CELLS &&
        value.visiblePattern.every(validateVisiblePatternCell) &&
        new Set(value.visiblePattern.map((cell) => cell.cellId)).size ===
          value.visiblePattern.length
      );
    case 'cell-written':
      return (
        exact([
          'cellId',
          'beforeToken',
          'afterToken',
          'activeEntryId',
          'actionId',
          'source',
        ]) &&
        isBoundedString(value.cellId) &&
        isNullableToken(value.beforeToken) &&
        isToken(value.afterToken) &&
        isNullableId(value.activeEntryId) &&
        isBoundedString(value.actionId) &&
        [
          'keyboard',
          'touch',
          'accessibility',
          'composition',
          'unknown',
        ].includes(value.source as string)
      );
    case 'cell-cleared':
      return (
        exact([
          'cellId',
          'beforeToken',
          'activeEntryId',
          'actionId',
          'source',
        ]) &&
        isBoundedString(value.cellId) &&
        isNullableToken(value.beforeToken) &&
        isNullableId(value.activeEntryId) &&
        isBoundedString(value.actionId) &&
        [
          'keyboard',
          'touch',
          'accessibility',
          'composition',
          'unknown',
        ].includes(value.source as string)
      );
    case 'batch-entered': {
      if (
        !exact(['activeEntryId', 'actionId', 'source', 'edits']) ||
        !isNullableId(value.activeEntryId) ||
        !isBoundedString(value.actionId) ||
        !['paste', 'composition', 'unknown'].includes(value.source as string) ||
        !Array.isArray(value.edits) ||
        value.edits.length === 0 ||
        value.edits.length > MAX_BATCH_EDITS
      )
        return false;
      const cells = new Set<string>();
      for (const edit of value.edits) {
        if (
          !isRecord(edit) ||
          !hasExactKeys(edit, ['cellId', 'beforeToken', 'afterToken']) ||
          !isBoundedString(edit.cellId) ||
          !isNullableToken(edit.beforeToken) ||
          !isToken(edit.afterToken) ||
          cells.has(edit.cellId)
        )
          return false;
        cells.add(edit.cellId);
      }
      return true;
    }
    case 'check-result-shown': {
      if (
        !exact(['scope', 'entryId', 'results']) ||
        !['cell', 'entry', 'puzzle'].includes(value.scope as string) ||
        !isNullableId(value.entryId) ||
        !Array.isArray(value.results) ||
        value.results.length === 0 ||
        value.results.length > MAX_BATCH_EDITS
      )
        return false;
      const cells = new Set<string>();
      for (const result of value.results) {
        if (
          !isRecord(result) ||
          !hasExactKeys(result, ['cellId', 'token', 'classification']) ||
          !isBoundedString(result.cellId) ||
          !isNullableToken(result.token) ||
          !['correct', 'incorrect', 'blank'].includes(
            result.classification as string,
          ) ||
          cells.has(result.cellId)
        )
          return false;
        if ((result.classification === 'blank') !== (result.token === null))
          return false;
        cells.add(result.cellId);
      }
      return (value.scope === 'puzzle') === (value.entryId === null);
    }
    case 'answer-revealed': {
      if (
        !exact(['scope', 'entryId', 'cells']) ||
        !['cell', 'entry', 'puzzle'].includes(value.scope as string) ||
        !isNullableId(value.entryId) ||
        !Array.isArray(value.cells) ||
        value.cells.length === 0 ||
        value.cells.length > MAX_BATCH_EDITS
      )
        return false;
      const cells = new Set<string>();
      for (const cell of value.cells) {
        if (
          !isRecord(cell) ||
          !hasExactKeys(cell, ['cellId', 'beforeToken', 'token']) ||
          !isBoundedString(cell.cellId) ||
          !isNullableToken(cell.beforeToken) ||
          !isToken(cell.token) ||
          cells.has(cell.cellId)
        )
          return false;
        cells.add(cell.cellId);
      }
      return (value.scope === 'puzzle') === (value.entryId === null);
    }
    case 'hint-shown':
      return (
        exact(['entryId', 'hintId', 'assistanceTier', 'affectedCellIds']) &&
        isBoundedString(value.entryId) &&
        isBoundedString(value.hintId) &&
        [
          'clue-reading',
          'context',
          'crossing',
          'letter',
          'answer',
        ].includes(value.assistanceTier as string) &&
        isStringArray(value.affectedCellIds)
      );
  }
}

function validateInitialCell(
  value: unknown,
): value is SolveSessionV2['initialGrid'][number] {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['cellId', 'token', 'origin']) &&
    isBoundedString(value.cellId) &&
    isNullableToken(value.token) &&
    value.origin === 'unknown'
  );
}

/** Validate an immutable replay bundle, including writer ordering and envelope ownership. */
export function validateSolveSessionV2(
  value: unknown,
): value is SolveSessionV2 {
  if (
    !isRecord(value) ||
    !hasExactKeys(
      value,
      ['schemaVersion', 'sessionId', 'puzzleHash', 'initialGrid', 'events'],
      ['profileId'],
    )
  )
    return false;
  if (
    value.schemaVersion !== 2 ||
    !isBoundedString(value.sessionId) ||
    !isBoundedString(value.puzzleHash) ||
    (value.profileId !== undefined && !isBoundedString(value.profileId)) ||
    !Array.isArray(value.initialGrid) ||
    value.initialGrid.length > MAX_INITIAL_CELL_COUNT ||
    !value.initialGrid.every(validateInitialCell) ||
    !Array.isArray(value.events) ||
    value.events.length === 0 ||
    value.events.length > MAX_EVENT_COUNT ||
    !value.events.every(validateSolveEventV2)
  )
    return false;

  const cellIds = new Set(value.initialGrid.map((cell) => cell.cellId));
  if (cellIds.size !== value.initialGrid.length) return false;
  const eventIds = new Set<string>();
  const segmentTimes = new Map<string, number>();
  const events = value.events as SolveEventV2[];
  if (events[0]?.type !== 'session-started') return false;
  let hasFinished = false;
  for (const [index, event] of events.entries()) {
    if (
      event.sessionId !== value.sessionId ||
      event.puzzleHash !== value.puzzleHash ||
      event.seq !== index + 1 ||
      hasFinished
    )
      return false;
    if (index > 0 && event.type === 'session-started') return false;
    if (event.type === 'session-finished') {
      hasFinished = true;
      if (index !== events.length - 1) return false;
    }
    if (event.profileId !== undefined && event.profileId !== value.profileId)
      return false;
    if (eventIds.has(event.eventId)) return false;
    const lastTime = segmentTimes.get(event.segmentId);
    if (lastTime !== undefined && event.elapsedMs < lastTime) return false;
    eventIds.add(event.eventId);
    segmentTimes.set(event.segmentId, event.elapsedMs);
  }
  return true;
}

const observationOutcomes: readonly EntryObservation['outcome'][] = [
  'independent-retrieval',
  'supported-retrieval',
  'exposure',
  'check-assisted-correction',
  'reveal-assisted-correction',
  'check-confirmed',
  'batch-entry',
  'incorrect-attempt',
  'untouched',
  'indeterminate',
];

const observationStates: readonly EntryObservation['finalState'][] = [
  'correct',
  'incorrect',
  'incomplete',
  'indeterminate',
];

/** Strict validator for deterministic per-entry evidence. */
export function validateEntryObservation(
  value: unknown,
): value is EntryObservation {
  const keys = [
    'sessionId',
    'puzzleHash',
    'entryId',
    'finalState',
    'outcome',
    'inputMode',
    'prefilledFraction',
    'supportCellIds',
    'revealedCellIds',
    'correctnessShownCellIds',
    'unknownProvenanceCellIds',
    'attemptedCellIds',
    'checkCorrectedCellIds',
    'revealCorrectedCellIds',
    'incorrectAttemptCount',
    'independentSuccessWeight',
    'supportedSuccessWeight',
    'failureWeight',
  ];
  if (
    !isRecord(value) ||
    !hasExactKeys(value, keys) ||
    !isBoundedString(value.sessionId) ||
    !isBoundedString(value.puzzleHash) ||
    !isBoundedString(value.entryId) ||
    !observationStates.includes(
      value.finalState as EntryObservation['finalState'],
    ) ||
    !observationOutcomes.includes(
      value.outcome as EntryObservation['outcome'],
    ) ||
    !['none', 'manual', 'batch', 'mixed'].includes(value.inputMode as string) ||
    typeof value.prefilledFraction !== 'number' ||
    !Number.isFinite(value.prefilledFraction) ||
    value.prefilledFraction < 0 ||
    value.prefilledFraction > 1 ||
    !isStringArray(value.supportCellIds) ||
    !isStringArray(value.revealedCellIds) ||
    !isStringArray(value.correctnessShownCellIds) ||
    !isStringArray(value.unknownProvenanceCellIds) ||
    !isStringArray(value.attemptedCellIds) ||
    !isStringArray(value.checkCorrectedCellIds) ||
    !isStringArray(value.revealCorrectedCellIds) ||
    !Number.isSafeInteger(value.incorrectAttemptCount) ||
    (value.incorrectAttemptCount as number) < 0 ||
    typeof value.independentSuccessWeight !== 'number' ||
    !Number.isFinite(value.independentSuccessWeight) ||
    typeof value.supportedSuccessWeight !== 'number' ||
    !Number.isFinite(value.supportedSuccessWeight) ||
    typeof value.failureWeight !== 'number' ||
    !Number.isFinite(value.failureWeight)
  )
    return false;

  const independent = value.independentSuccessWeight as number;
  const supported = value.supportedSuccessWeight as number;
  const failure = value.failureWeight as number;
  if (
    independent < 0 ||
    independent > 1 ||
    supported < 0 ||
    supported > 0.35 ||
    failure < 0 ||
    failure > 0.5
  )
    return false;
  if ((value.outcome === 'independent-retrieval') !== independent > 0)
    return false;
  if ((value.outcome === 'supported-retrieval') !== supported > 0) return false;
  if (independent > 0 && supported > 0) return false;
  if (failure > 0 && (value.incorrectAttemptCount as number) === 0)
    return false;
  return true;
}

/** Strict validator for the serialized result of one reducer version. */
export function validateSessionAnalysis(
  value: unknown,
): value is SessionAnalysis {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, [
      'schemaVersion',
      'analysisVersion',
      'sessionId',
      'puzzleHash',
      'observations',
    ]) ||
    value.schemaVersion !== 1 ||
    value.analysisVersion !== 'knowledge-reducer-v1' ||
    !isBoundedString(value.sessionId) ||
    !isBoundedString(value.puzzleHash) ||
    !Array.isArray(value.observations) ||
    value.observations.length > 500 ||
    !value.observations.every(validateEntryObservation)
  )
    return false;
  if (
    value.observations.some(
      (item) =>
        item.sessionId !== value.sessionId ||
        item.puzzleHash !== value.puzzleHash,
    )
  )
    return false;
  return (
    new Set(value.observations.map((item) => item.entryId)).size ===
    value.observations.length
  );
}

type CellOrigin = 'unknown' | 'player' | 'reveal';

type CellState = Readonly<{
  token: SolveTokenV2 | null;
  origin: CellOrigin;
  sourceEntryId: EntryId | null;
}>;

type MutableEntryEvidence = {
  focused: boolean;
  supportCellIds: Set<string>;
  directCorrectCellIds: Set<string>;
  revealedCellIds: Set<string>;
  correctnessShownCellIds: Set<string>;
  unknownProvenanceCellIds: Set<string>;
  attemptedCellIds: Set<string>;
  checkCorrectedCellIds: Set<string>;
  revealCorrectedCellIds: Set<string>;
  manualAction: boolean;
  batchAction: boolean;
  incorrectPatterns: Set<string>;
  checkFailedValues: Map<string, string>;
};

function normalizeToken(token: string): string {
  return token.normalize('NFC').toLocaleUpperCase('en-US');
}

function sameToken(left: string | null, right: string | null): boolean {
  return (
    left === right ||
    (left !== null &&
      right !== null &&
      normalizeToken(left) === normalizeToken(right))
  );
}

function entryAnswerTokens(
  entry: ReplayPuzzleEntry,
): readonly string[] | undefined {
  const answer = Array.from(entry.answer.normalize('NFC'));
  if (answer.length !== entry.cellIds.length) return undefined;
  return answer;
}

function emptyEvidence(): MutableEntryEvidence {
  return {
    focused: false,
    supportCellIds: new Set(),
    directCorrectCellIds: new Set(),
    revealedCellIds: new Set(),
    correctnessShownCellIds: new Set(),
    unknownProvenanceCellIds: new Set(),
    attemptedCellIds: new Set(),
    checkCorrectedCellIds: new Set(),
    revealCorrectedCellIds: new Set(),
    manualAction: false,
    batchAction: false,
    incorrectPatterns: new Set(),
    checkFailedValues: new Map(),
  };
}

function sortedForEntry(
  entry: ReplayPuzzleEntry,
  cellIds: Set<string>,
): CellId[] {
  return entry.cellIds.filter((cellId) => cellIds.has(cellId)) as CellId[];
}

function resultPattern(
  entry: ReplayPuzzleEntry,
  state: Map<string, CellState>,
): string {
  return entry.cellIds
    .map((cellId) => state.get(cellId)?.token ?? '')
    .join('\u001f');
}

function answerAtCell(
  puzzle: ReplayPuzzleDocument,
  cellId: string,
): string | undefined {
  for (const entry of puzzle.entries) {
    const position = entry.cellIds.indexOf(cellId as CellId);
    if (position < 0) continue;
    const tokens = entryAnswerTokens(entry);
    if (tokens) return tokens[position];
  }
  return undefined;
}

function isKnownCrossing(
  sourceEntryId: EntryId | null,
  targetEntryId: EntryId,
  cellId: CellId,
  entriesById: Map<EntryId, ReplayPuzzleEntry>,
): boolean {
  if (!sourceEntryId || sourceEntryId === targetEntryId) return false;
  const source = entriesById.get(sourceEntryId);
  return source !== undefined && source.cellIds.includes(cellId as CellId);
}

/**
 * Replay a validated v2 event bundle and return conservative, per-entry evidence.
 * Timing fields are validated for integrity but never influence the observations.
 */
export function analyzeSessionV2(
  session: SolveSessionV2,
  puzzle: PuzzleDocument,
): SessionAnalysis {
  if (!validateSolveSessionV2(session))
    throw new Error('Invalid solve session v2');
  if (!validatePuzzle(puzzle)) throw new Error('Invalid puzzle document');
  if (session.puzzleHash !== puzzle.integrity.value)
    throw new Error('Solve session puzzle hash does not match puzzle');

  return replayValidatedSession(session, {
    cells: puzzle.cells.map(({ id, block }) => ({ id, block })),
    entries: puzzle.entries.map(({ id, cellIds, answer }) => ({
      id,
      cellIds,
      answer,
    })),
    integrity: { value: puzzle.integrity.value },
  });
}

/**
 * Analyze an explicit V2 puzzle document after strict schema and digest checks.
 * This is intentionally a separate entry point: solve-session version does not
 * select which puzzle-document validator runs.
 */
export async function analyzeSessionV2Document(
  session: unknown,
  puzzle: unknown,
): Promise<SessionAnalysis> {
  if (!validateSolveSessionV2(session))
    throw new Error('Invalid solve session v2');
  const { assertValidPuzzleDocumentV2 } = await import('./puzzleV2');
  await assertValidPuzzleDocumentV2(puzzle);
  const puzzleDocument = puzzle as PuzzleDocumentV2;
  if (session.puzzleHash !== puzzleDocument.integrity.value)
    throw new Error('Solve session puzzle hash does not match puzzle');

  const replayPuzzle: ReplayPuzzleDocument = {
    cells: puzzleDocument.cells.map(({ id, block }) => ({ id: id as CellId, block })),
    entries: puzzleDocument.entries.map(({ id, cellIds, answer }) => ({
      id: id as EntryId,
      cellIds: cellIds as readonly CellId[],
      answer,
    })),
    integrity: { value: puzzleDocument.integrity.value },
  };
  return replayValidatedSession(session, replayPuzzle);
}

/** Shared deterministic event reducer; both callers validate their own puzzle schema first. */
function replayValidatedSession(
  session: SolveSessionV2,
  puzzle: ReplayPuzzleDocument,
): SessionAnalysis {

  const cellsById = new Map(
    puzzle.cells.map((cell) => [cell.id, cell] as const),
  );
  const entriesById = new Map<EntryId, ReplayPuzzleEntry>(
    puzzle.entries.map((entry) => [entry.id, entry] as const),
  );
  const entriesByCellId = new Map<
    CellId,
    ReplayPuzzleEntry[]
  >();
  for (const entry of puzzle.entries) {
    for (const cellId of entry.cellIds) {
      const list = entriesByCellId.get(cellId) ?? [];
      list.push(entry);
      entriesByCellId.set(cellId, list);
    }
  }

  const state = new Map<string, CellState>();
  for (const cell of puzzle.cells) {
    if (!cell.block)
      state.set(cell.id, {
        token: null,
        origin: 'unknown',
        sourceEntryId: null,
      });
  }
  for (const initial of session.initialGrid) {
    const cell = cellsById.get(initial.cellId);
    if (!cell || cell.block)
      throw new Error(
        `Initial grid contains an invalid cell: ${initial.cellId}`,
      );
    state.set(initial.cellId, {
      token: initial.token,
      origin: 'unknown',
      sourceEntryId: null,
    });
  }

  const completedEntries = new Set<EntryId>();
  const markCompletedEntries = () => {
    for (const entry of puzzle.entries) {
      const answer = entryAnswerTokens(entry);
      if (
        answer &&
        entry.cellIds.every((cellId, index) =>
          sameToken(state.get(cellId)?.token ?? null, answer[index] ?? null),
        )
      ) {
        completedEntries.add(entry.id);
      }
    }
  };
  markCompletedEntries();

  const evidence = new Map<EntryId, MutableEntryEvidence>(
    puzzle.entries.map((entry) => [entry.id, emptyEvidence()]),
  );
  for (const initial of session.initialGrid) {
    if (initial.token === null) continue;
    for (const entry of entriesByCellId.get(initial.cellId) ?? []) {
      evidence.get(entry.id)!.unknownProvenanceCellIds.add(initial.cellId);
    }
  }
  const entryEvidence = (entryId: EntryId): MutableEntryEvidence => {
    const found = evidence.get(entryId);
    if (!found)
      throw new Error(`Event references an unknown entry: ${entryId}`);
    return found;
  };
  const assertOpenCell = (cellId: CellId) => {
    const cell = cellsById.get(cellId);
    if (!cell || cell.block)
      throw new Error(`Event references an invalid cell: ${cellId}`);
  };
  const verifyBefore = (cellId: CellId, beforeToken: string | null) => {
    assertOpenCell(cellId);
    if (!sameToken(state.get(cellId)?.token ?? null, beforeToken)) {
      throw new Error(
        `Event beforeToken does not match replay state for ${cellId}`,
      );
    }
  };

  const recordPlayerAction = (
    cellId: CellId,
    activeEntryId: EntryId | null,
    isBatch: boolean,
    sourceIsKnown: boolean,
    tokenWillBePresent = true,
  ) => {
    for (const entry of entriesByCellId.get(cellId) ?? []) {
      const item = entryEvidence(entry.id);
      if (activeEntryId === entry.id) {
        item.attemptedCellIds.add(cellId);
        if (isBatch) item.batchAction = true;
        else item.manualAction = true;
        if (!sourceIsKnown) item.unknownProvenanceCellIds.add(cellId);
      } else if (!tokenWillBePresent || completedEntries.has(entry.id)) {
        continue;
      } else if (
        sourceIsKnown &&
        isKnownCrossing(activeEntryId, entry.id, cellId, entriesById)
      ) {
        item.supportCellIds.add(cellId);
      } else {
        item.unknownProvenanceCellIds.add(cellId);
      }
    }
  };

  const applyWrite = (
    cellId: CellId,
    beforeToken: string | null,
    afterToken: string,
    activeEntryId: EntryId | null,
    sourceKnown: boolean,
    isBatch: boolean,
  ) => {
    verifyBefore(cellId, beforeToken);
    recordPlayerAction(cellId, activeEntryId, isBatch, sourceKnown);
    const answerToken = answerAtCell(puzzle, cellId);
    if (activeEntryId !== null) {
      const item = entryEvidence(activeEntryId);
      const activeEntry = entriesById.get(activeEntryId);
      if (
        !isBatch &&
        sourceKnown &&
        activeEntry?.cellIds.includes(cellId) &&
        sameToken(afterToken, answerToken ?? null)
      ) {
        item.directCorrectCellIds.add(cellId);
      }
    }
    for (const entry of entriesByCellId.get(cellId) ?? []) {
      const item = entryEvidence(entry.id);
      const pending = item.checkFailedValues.get(cellId);
      if (
        pending !== undefined &&
        sameToken(beforeToken, pending) &&
        sameToken(afterToken, answerToken ?? null)
      ) {
        item.checkCorrectedCellIds.add(cellId);
        item.checkFailedValues.delete(cellId);
      }
    }
    let origin: CellOrigin = 'unknown';
    let sourceEntryId: EntryId | null = null;
    if (sourceKnown && activeEntryId) {
      const activeEntry = entriesById.get(activeEntryId);
      if (activeEntry?.cellIds.includes(cellId as CellId)) {
        origin = 'player';
        sourceEntryId = activeEntryId;
      }
    }
    state.set(cellId, { token: afterToken, origin, sourceEntryId });
    markCompletedEntries();
  };

  for (const event of session.events) {
    switch (event.type) {
      case 'session-started':
      case 'session-resumed':
      case 'session-finished':
      case 'visibility-changed':
      case 'paused':
      case 'resumed':
        break;
      case 'hint-shown': {
        const entry = entriesById.get(event.entryId);
        if (!entry)
          throw new Error(`Hint references an unknown entry: ${event.entryId}`);
        if (
          event.affectedCellIds.some(
            (cellId) => !entry.cellIds.includes(cellId),
          )
        ) {
          throw new Error(`Hint cells do not match entry ${entry.id}`);
        }
        break;
      }
      case 'entry-focused': {
        const entry = entriesById.get(event.entryId);
        if (!entry)
          throw new Error(
            `Event references an unknown entry: ${event.entryId}`,
          );
        if (
          event.visiblePattern.length !== entry.cellIds.length ||
          event.visiblePattern.some(
            (cell, index) => cell.cellId !== entry.cellIds[index],
          )
        ) {
          throw new Error(
            `Visible pattern does not match entry ${event.entryId}`,
          );
        }
        const item = entryEvidence(event.entryId);
        item.focused = true;
        for (const visible of event.visiblePattern) {
          assertOpenCell(visible.cellId);
          if (
            !sameToken(state.get(visible.cellId)?.token ?? null, visible.token)
          ) {
            throw new Error(
              `Visible pattern token does not match replay state for ${visible.cellId}`,
            );
          }
          const sourceState = state.get(visible.cellId)!;
          const sourceIsCrossing =
            sourceState.origin === 'player' &&
            isKnownCrossing(
              sourceState.sourceEntryId,
              entry.id,
              visible.cellId,
              entriesById,
            );
          const expectedOrigin =
            sourceState.origin === 'reveal'
              ? 'reveal'
              : sourceState.origin === 'unknown'
                ? 'unknown'
                : sourceIsCrossing
                  ? 'crossing'
                  : sourceState.sourceEntryId === entry.id
                    ? 'player'
                    : 'unknown';
          const expectedSourceEntryId =
            expectedOrigin === 'crossing' || expectedOrigin === 'player'
              ? sourceState.sourceEntryId
              : null;
          if (
            visible.origin !== expectedOrigin ||
            visible.sourceEntryId !== expectedSourceEntryId
          ) {
            throw new Error(
              `Visible pattern provenance does not match replay state for ${visible.cellId}`,
            );
          }
          if (completedEntries.has(entry.id)) continue;
          if (visible.token === null) continue;
          if (
            visible.origin === 'crossing' &&
            isKnownCrossing(
              visible.sourceEntryId,
              entry.id,
              visible.cellId,
              entriesById,
            )
          ) {
            item.supportCellIds.add(visible.cellId);
          } else if (visible.origin === 'reveal') {
            item.revealedCellIds.add(visible.cellId);
          } else if (
            visible.origin === 'unknown' ||
            (visible.origin === 'player' &&
              !isKnownCrossing(
                visible.sourceEntryId,
                entry.id,
                visible.cellId,
                entriesById,
              ) &&
              visible.sourceEntryId !== entry.id)
          ) {
            item.unknownProvenanceCellIds.add(visible.cellId);
          }
        }
        break;
      }
      case 'cell-written':
        applyWrite(
          event.cellId,
          event.beforeToken,
          event.afterToken,
          event.activeEntryId,
          event.source !== 'unknown',
          false,
        );
        break;
      case 'cell-cleared':
        verifyBefore(event.cellId, event.beforeToken);
        recordPlayerAction(
          event.cellId,
          event.activeEntryId,
          false,
          event.source !== 'unknown',
          false,
        );
        state.set(event.cellId, {
          token: null,
          origin: 'unknown',
          sourceEntryId: null,
        });
        markCompletedEntries();
        break;
      case 'batch-entered':
        for (const edit of event.edits) {
          applyWrite(
            edit.cellId,
            edit.beforeToken,
            edit.afterToken,
            event.activeEntryId,
            event.source !== 'unknown',
            true,
          );
        }
        break;
      case 'check-result-shown': {
        if (event.entryId !== null && !entriesById.has(event.entryId)) {
          throw new Error(
            `Check references an unknown entry: ${event.entryId}`,
          );
        }
        const incorrectEntries = new Set<EntryId>();
        const checkedEntry =
          event.entryId === null ? undefined : entriesById.get(event.entryId);
        if (
          event.scope === 'entry' &&
          checkedEntry &&
          event.results.some(
            (result) => !checkedEntry.cellIds.includes(result.cellId),
          )
        ) {
          throw new Error(
            `Check results do not match entry ${checkedEntry.id}`,
          );
        }
        if (event.scope === 'cell' && event.results.length !== 1)
          throw new Error('A cell check must contain exactly one result');
        for (const result of event.results) {
          assertOpenCell(result.cellId);
          if (
            !sameToken(state.get(result.cellId)?.token ?? null, result.token)
          ) {
            throw new Error(
              `Check result token does not match replay state for ${result.cellId}`,
            );
          }
          const correctToken = answerAtCell(puzzle, result.cellId);
          const actuallyCorrect =
            result.token !== null &&
            sameToken(result.token, correctToken ?? null);
          for (const entry of entriesByCellId.get(result.cellId) ?? []) {
            const item = entryEvidence(entry.id);
            if (result.classification !== 'blank')
              item.correctnessShownCellIds.add(result.cellId);
            if (
              event.entryId === entry.id &&
              result.classification === 'incorrect' &&
              !actuallyCorrect &&
              result.token !== null
            ) {
              item.checkFailedValues.set(result.cellId, result.token);
              incorrectEntries.add(entry.id);
            }
          }
        }
        for (const entryId of incorrectEntries) {
          const entry = entriesById.get(entryId)!;
          entryEvidence(entryId).incorrectPatterns.add(
            resultPattern(entry, state),
          );
        }
        break;
      }
      case 'answer-revealed': {
        if (event.entryId !== null && !entriesById.has(event.entryId)) {
          throw new Error(
            `Reveal references an unknown entry: ${event.entryId}`,
          );
        }
        const revealedEntry =
          event.entryId === null ? undefined : entriesById.get(event.entryId);
        if (
          event.scope === 'entry' &&
          revealedEntry &&
          event.cells.some(
            (cell) => !revealedEntry.cellIds.includes(cell.cellId),
          )
        ) {
          throw new Error(
            `Reveal cells do not match entry ${revealedEntry.id}`,
          );
        }
        if (event.scope === 'cell' && event.cells.length !== 1)
          throw new Error('A cell reveal must contain exactly one cell');
        for (const reveal of event.cells) {
          verifyBefore(reveal.cellId, reveal.beforeToken);
          const answerToken = answerAtCell(puzzle, reveal.cellId);
          for (const entry of entriesByCellId.get(reveal.cellId) ?? []) {
            const item = entryEvidence(entry.id);
            item.revealedCellIds.add(reveal.cellId);
            if (
              event.entryId === entry.id &&
              reveal.beforeToken !== null &&
              !sameToken(reveal.beforeToken, answerToken ?? null) &&
              sameToken(reveal.token, answerToken ?? null)
            )
              item.revealCorrectedCellIds.add(reveal.cellId);
          }
          state.set(reveal.cellId, {
            token: reveal.token,
            origin: 'reveal',
            sourceEntryId: null,
          });
          markCompletedEntries();
        }
        break;
      }
    }
  }

  const observations = puzzle.entries.map((entry): EntryObservation => {
    const item = evidence.get(entry.id)!;
    const answerTokens = entryAnswerTokens(entry);
    const cellStates = entry.cellIds.map((cellId) => state.get(cellId));
    const finalTokens = cellStates.map((cell) => cell?.token ?? null);
    const finalState: EntryObservation['finalState'] =
      !answerTokens || cellStates.some((cell) => cell === undefined)
        ? 'indeterminate'
        : finalTokens.every((token) => token !== null) &&
            finalTokens.every((token, index) =>
              sameToken(token, answerTokens[index] ?? null),
            )
          ? 'correct'
          : finalTokens.some((token) => token === null)
            ? 'incomplete'
            : 'incorrect';

    const prefilledCellIds = new Set([
      ...item.supportCellIds,
      ...item.revealedCellIds,
      ...item.unknownProvenanceCellIds,
    ]);
    const prefilledFraction =
      entry.cellIds.length === 0
        ? 0
        : Math.min(1, prefilledCellIds.size / entry.cellIds.length);
    const hasManual = item.manualAction;
    const hasBatch = item.batchAction;
    const inputMode: EntryObservation['inputMode'] =
      hasManual && hasBatch
        ? 'mixed'
        : hasBatch
          ? 'batch'
          : hasManual
            ? 'manual'
            : 'none';
    const hasUserEntry = hasManual || hasBatch;
    const allSuppliedByCrossings =
      finalState === 'correct' &&
      !hasUserEntry &&
      entry.cellIds.every((cellId) => {
        const current = state.get(cellId);
        return (
          current?.token !== null &&
          current?.origin === 'player' &&
          isKnownCrossing(current.sourceEntryId, entry.id, cellId, entriesById)
        );
      });
    const allSuppliedWithoutRecall =
      finalState === 'correct' &&
      !hasUserEntry &&
      entry.cellIds.every((cellId) => {
        const current = state.get(cellId);
        if (current?.token === null || current === undefined) return false;
        if (current.origin === 'reveal') return true;
        return (
          current.origin === 'player' &&
          isKnownCrossing(current.sourceEntryId, entry.id, cellId, entriesById)
        );
      });
    let outcome: EntryObservation['outcome'] = 'indeterminate';
    let independentSuccessWeight = 0;
    let supportedSuccessWeight = 0;
    let failureWeight = item.incorrectPatterns.size > 0 ? 0.5 : 0;

    if (finalState === 'correct') {
      if (allSuppliedByCrossings || allSuppliedWithoutRecall) {
        outcome = 'exposure';
      } else if (item.checkCorrectedCellIds.size > 0) {
        outcome = 'check-assisted-correction';
      } else if (
        item.revealCorrectedCellIds.size > 0 ||
        (item.revealedCellIds.size > 0 && hasUserEntry)
      ) {
        outcome = 'reveal-assisted-correction';
      } else if (hasBatch) {
        outcome = 'batch-entry';
      } else if (item.correctnessShownCellIds.size > 0) {
        outcome = 'check-confirmed';
      } else if (prefilledFraction > 0.6) {
        const knownSupportFraction =
          (item.supportCellIds.size + item.revealedCellIds.size) /
          entry.cellIds.length;
        outcome = knownSupportFraction > 0.6 ? 'exposure' : 'indeterminate';
      } else if (!hasManual) {
        outcome = 'indeterminate';
      } else if (
        item.directCorrectCellIds.size <
        Math.max(1, Math.ceil(entry.cellIds.length * 0.2))
      ) {
        outcome = 'indeterminate';
      } else if (prefilledFraction > 0.2) {
        outcome = 'supported-retrieval';
        supportedSuccessWeight = 0.35;
      } else {
        outcome = 'independent-retrieval';
        independentSuccessWeight = 1;
      }
    } else if (finalState === 'incorrect') {
      outcome =
        item.incorrectPatterns.size > 0 || hasUserEntry
          ? 'incorrect-attempt'
          : 'indeterminate';
    } else if (
      !item.focused &&
      !hasUserEntry &&
      item.correctnessShownCellIds.size === 0 &&
      item.revealedCellIds.size === 0 &&
      item.supportCellIds.size === 0
    ) {
      outcome = 'untouched';
      failureWeight = 0;
    } else if (item.incorrectPatterns.size > 0) {
      outcome = 'incorrect-attempt';
    }

    // Imported/unknown letters and correctness feedback can never contribute independent recall.
    if (
      item.unknownProvenanceCellIds.size > 0 ||
      item.correctnessShownCellIds.size > 0 ||
      item.revealedCellIds.size > 0
    ) {
      independentSuccessWeight = 0;
      if (outcome === 'independent-retrieval') outcome = 'indeterminate';
    }
    if (outcome !== 'supported-retrieval') supportedSuccessWeight = 0;
    if (
      outcome === 'untouched' ||
      outcome === 'exposure' ||
      outcome === 'batch-entry' ||
      outcome === 'check-confirmed'
    ) {
      if (item.incorrectPatterns.size === 0) failureWeight = 0;
    }

    const observation: EntryObservation = {
      sessionId: session.sessionId,
      puzzleHash: session.puzzleHash,
      entryId: entry.id,
      finalState,
      outcome,
      inputMode,
      prefilledFraction,
      supportCellIds: sortedForEntry(entry, item.supportCellIds),
      revealedCellIds: sortedForEntry(entry, item.revealedCellIds),
      correctnessShownCellIds: sortedForEntry(
        entry,
        item.correctnessShownCellIds,
      ),
      unknownProvenanceCellIds: sortedForEntry(
        entry,
        item.unknownProvenanceCellIds,
      ),
      attemptedCellIds: sortedForEntry(entry, item.attemptedCellIds),
      checkCorrectedCellIds: sortedForEntry(entry, item.checkCorrectedCellIds),
      revealCorrectedCellIds: sortedForEntry(
        entry,
        item.revealCorrectedCellIds,
      ),
      incorrectAttemptCount: item.incorrectPatterns.size,
      independentSuccessWeight,
      supportedSuccessWeight,
      failureWeight,
    };
    if (!validateEntryObservation(observation))
      throw new Error(`Reducer produced invalid observation for ${entry.id}`);
    return observation;
  });

  const analysis: SessionAnalysis = {
    schemaVersion: 1,
    analysisVersion: 'knowledge-reducer-v1',
    sessionId: session.sessionId,
    puzzleHash: session.puzzleHash,
    observations,
  };
  if (!validateSessionAnalysis(analysis))
    throw new Error('Reducer produced invalid session analysis');
  return analysis;
}
