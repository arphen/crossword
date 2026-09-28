import {
  CLUE_GRAMMAR_VERSION,
  type ClueFamily,
  type ClueGrammarAnnotation,
  type ClueVariantRole,
  type PuzzleMechanic,
  validateClueGrammar,
} from './clueGrammar.js';

/**
 * First publishable construction slice. This intentionally supports only a
 * conventional 15x15 grid with one ASCII letter in each open cell. Rebus and
 * multi-token mechanics need a later schema version with explicit reading
 * rules; they must not be smuggled into this document as ordinary cells.
 */
export const PUZZLE_DOCUMENT_V2_VERSION = 2 as const;
export const PUZZLE_DOCUMENT_V2_SIZE = 15 as const;
export const PUZZLE_DOCUMENT_V2_CANONICALIZATION = 'json-canonical-v1' as const;

export type PuzzleV2Weekday =
  | 'Monday'
  | 'Tuesday'
  | 'Wednesday'
  | 'Thursday'
  | 'Friday'
  | 'Saturday'
  | 'Sunday';

export type PuzzleV2Cell = Readonly<{
  id: string;
  row: number;
  column: number;
  block: boolean;
  circled: boolean;
  shaded: boolean;
  /** null for blocks; exactly one A-Z letter for an open cell. */
  token: string | null;
}>;

export type PuzzleV2Entry = Readonly<{
  id: string;
  number: number;
  direction: 'across' | 'down';
  cellIds: readonly string[];
  /** Canonical, unspaced, one-letter-per-cell lexical answer. */
  answer: string;
  lexemeId: string;
  senseId: string;
  retrievalTaskId?: string;
}>;

export type PuzzleV2ClueSupport = Readonly<{
  senseIds: readonly string[];
  factIds: readonly string[];
}>;

export type PuzzleV2ClueVariant = Readonly<{
  clueVariantId: string;
  /** Identity of the admitted clue reused to create this entry-specific variant. */
  sourceClueId: string;
  entryId: string;
  variantRole: ClueVariantRole;
  primaryFamily: ClueFamily;
  text: string;
  grammar: ClueGrammarAnnotation;
  support: PuzzleV2ClueSupport;
}>;

export type PuzzleV2SourcePin = Readonly<{
  sourceId: string;
  version: string;
  artifactSha256: string;
  spdx: string;
  attribution: string;
  contentClass: 'public' | 'synthetic';
}>;

export type PuzzleV2LexemeProvenance = Readonly<{
  id: string;
  sourceIds: readonly string[];
}>;

export type PuzzleV2SenseProvenance = Readonly<{
  id: string;
  lexemeId: string;
  sourceIds: readonly string[];
  evidenceProvenance: PuzzleV2EvidenceProvenance;
}>;

export type PuzzleV2FactProvenance = Readonly<{
  id: string;
  lexemeId: string;
  sourceIds: readonly string[];
  review: 'verified' | 'quarantined' | 'retired';
  evidenceProvenance: PuzzleV2EvidenceProvenance;
}>;

/** Shape-preserving projection of an admitted record's reviewed provenance. */
export type PuzzleV2EvidenceProvenance = Readonly<{
  source: Readonly<{
    sourceId: string;
    version: string;
    artifactSha256: string;
    spdx: string;
    attribution: string;
    contentClass: 'public' | 'synthetic';
  }>;
  evidenceRefs: readonly string[];
  reviewerId: string;
  reviewedAt: string;
}>;

export type PuzzleV2ClueProvenance = Readonly<{
  clueVariantId: string;
  sourceClueId: string;
  entryId: string;
  senseIds: readonly string[];
  factIds: readonly string[];
  sourceIds: readonly string[];
  evidenceKind: 'sense' | 'fact';
  evidenceId: string;
  evidenceRefs: readonly string[];
  evidenceProvenance: PuzzleV2EvidenceProvenance;
  reviewerId: string;
  reviewedAt: string;
  semanticTruthStatus: 'not-established-by-grammar-validator';
}>;

export type PuzzleV2Provenance = Readonly<{
  sources: readonly PuzzleV2SourcePin[];
  lexemes: readonly PuzzleV2LexemeProvenance[];
  senses: readonly PuzzleV2SenseProvenance[];
  facts: readonly PuzzleV2FactProvenance[];
  clues: readonly PuzzleV2ClueProvenance[];
}>;

export type PuzzleV2Topology = Readonly<{
  width: 15;
  height: 15;
  blockedCellIds: readonly string[];
  minEntryLength: 3;
  numbering: 'standard-row-major-v1';
}>;

export type PuzzleV2Receipt = Readonly<{
  constructionSeed: string;
  recipe: Readonly<{
    id: string;
    version: string;
    weekday: PuzzleV2Weekday;
  }>;
  runtime: Readonly<{
    id: string;
    version: string;
    artifactDigest: string;
  }>;
  validators: readonly Readonly<{ id: string; version: string }>[];
  generatedAt: string;
  /** Private, local-only generation context. Never copy into a public export. */
  profileProjection?: Readonly<{ revision: number; digest: string }>;
}>;

export type PuzzleV2CrossingSupport = Readonly<{
  version: string;
  edges: readonly Readonly<{
    acrossEntryId: string;
    downEntryId: string;
    cellId: string;
    /** Conservative estimated player support, [0,1]; zero is required when no estimate exists. */
    score: number;
    /** Confidence in a player-support estimate, [0,1]; zero is required when uncalibrated. */
    confidence: number;
  }>[];
  minimumScore: number;
  meanScore: number;
  uncertainty: Readonly<{
    level: 'low' | 'medium' | 'high' | 'unknown';
    notes: string;
  }>;
}>;

export type PuzzleV2SemanticAttestation = Readonly<{
  reviewerId: string;
  reviewedAt: string;
  clueVariantIds: readonly string[];
  sourceIds: readonly string[];
  evidenceRefs: readonly string[];
}>;

export type PuzzleV2Quality = Readonly<{
  verdict: 'accept' | 'review' | 'reject';
  reasons: readonly string[];
  /** Separate editorial evidence; grammar validation alone cannot establish truth. */
  semanticAttestation?: PuzzleV2SemanticAttestation;
}>;

export type PuzzleV2Integrity = Readonly<{
  algorithm: 'sha256';
  canonicalization: typeof PUZZLE_DOCUMENT_V2_CANONICALIZATION;
  value: string;
}>;

export type PuzzleDocumentV2 = Readonly<{
  schemaVersion: typeof PUZZLE_DOCUMENT_V2_VERSION;
  id: string;
  seed: string;
  title: string;
  subtitle: string;
  width: 15;
  height: 15;
  language: string;
  languagePolicy: Readonly<{
    version: 'ascii-uppercase-v1';
    cellTokenPolicy: 'single-ascii-letter-v1';
  }>;
  cells: readonly PuzzleV2Cell[];
  entries: readonly PuzzleV2Entry[];
  clues: readonly PuzzleV2ClueVariant[];
  mechanics: readonly PuzzleMechanic[];
  provenance: PuzzleV2Provenance;
  topology: PuzzleV2Topology;
  receipt: PuzzleV2Receipt;
  crossingSupport: PuzzleV2CrossingSupport;
  quality: PuzzleV2Quality;
  integrity: PuzzleV2Integrity;
}>;

export type PuzzleV2ValidationIssue = Readonly<{
  code: string;
  path?: string;
  message: string;
}>;

export type PuzzleV2Validation = Readonly<{
  valid: boolean;
  issues: readonly PuzzleV2ValidationIssue[];
}>;

const RAW_SHA256_PATTERN = /^[0-9a-f]{64}$/;
const INTEGRITY_PATTERN = /^sha256:[0-9a-f]{64}$/;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const ISO_DATE_TIME_PATTERN = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|([+-])(\d{2}):(\d{2}))$/;
const LANGUAGE_PATTERN = /^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/;
const WEEKDAYS: readonly string[] = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];

type RecordValue = Record<string, unknown>;

function isRecord(value: unknown): value is RecordValue {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: RecordValue,
  required: readonly string[],
  optional: readonly string[] = [],
): boolean {
  const allowed = new Set([...required, ...optional]);
  return required.every((key) => Object.hasOwn(value, key)) &&
    Object.keys(value).every((key) => allowed.has(key));
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isFiniteUnit(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1;
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== 'string' || !ISO_DATE_PATTERN.test(value)) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value;
}

function isIsoDateTime(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const match = ISO_DATE_TIME_PATTERN.exec(value);
  if (!match) return false;

  const [, yearText, monthText, dayText, hourText, minuteText, secondText, , , offsetHourText, offsetMinuteText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  if (
    year < 1 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59 ||
    (offsetHourText !== undefined && Number(offsetHourText) > 23) ||
    (offsetMinuteText !== undefined && Number(offsetMinuteText) > 59)
  ) return false;

  // Date.parse accepts and normalizes out-of-range days (for example, Feb 30).
  // Validate the written calendar date before parsing the timezone-bearing form.
  const calendarDate = new Date(0);
  calendarDate.setUTCFullYear(year, month - 1, day);
  calendarDate.setUTCHours(0, 0, 0, 0);
  if (
    calendarDate.getUTCFullYear() !== year ||
    calendarDate.getUTCMonth() !== month - 1 ||
    calendarDate.getUTCDate() !== day
  ) return false;

  return !Number.isNaN(Date.parse(value));
}

function uniqueStrings(values: readonly unknown[]): values is readonly string[] {
  return values.every(isNonEmptyString) && new Set(values).size === values.length;
}

function canonicalJson(value: unknown): string {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') {
    return JSON.stringify(value);
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new TypeError('Canonical JSON cannot contain a non-finite number');
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(',')}]`;
  }
  if (isRecord(value)) {
    const keys = Object.keys(value).sort();
    return `{${keys.map((key) => {
      const child = value[key];
      if (child === undefined) throw new TypeError('Canonical JSON cannot contain undefined values');
      return `${JSON.stringify(key)}:${canonicalJson(child)}`;
    }).join(',')}}`;
  }
  throw new TypeError('Value is not representable as canonical JSON');
}

/** Canonical JSON: recursively sorted object keys, preserved array order, compact UTF-8 JSON. */
export function canonicalizePuzzleDocumentV2(value: unknown): string {
  return canonicalJson(value);
}

async function sha256Hex(value: string): Promise<string> {
  const cryptoApi = globalThis.crypto;
  if (!cryptoApi?.subtle) throw new Error('Web Crypto SHA-256 is unavailable');
  const digest = await cryptoApi.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function withoutIntegrity(value: RecordValue): RecordValue {
  const copy = { ...value };
  delete copy.integrity;
  return copy;
}

export async function computePuzzleDocumentV2Digest(value: unknown): Promise<string> {
  if (!isRecord(value)) throw new TypeError('Puzzle document must be an object');
  return `sha256:${await sha256Hex(canonicalJson(withoutIntegrity(value)))}`;
}

export async function sealPuzzleDocumentV2(
  value: Omit<PuzzleDocumentV2, 'integrity'>,
): Promise<PuzzleDocumentV2> {
  const draft = value as Omit<PuzzleDocumentV2, 'integrity'>;
  const digest = await computePuzzleDocumentV2Digest(draft);
  return {
    ...draft,
    integrity: {
      algorithm: 'sha256',
      canonicalization: PUZZLE_DOCUMENT_V2_CANONICALIZATION,
      value: digest,
    },
  };
}

/** Removes the private profile projection before sharing and computes a new public digest. */
export async function createPublicPuzzleDocumentV2(value: PuzzleDocumentV2): Promise<PuzzleDocumentV2> {
  await assertValidPuzzleDocumentV2(value);
  const content: Record<string, unknown> = { ...value };
  delete content.integrity;
  const publicReceipt: Record<string, unknown> = { ...value.receipt };
  delete publicReceipt.profileProjection;
  content.receipt = publicReceipt;
  return sealPuzzleDocumentV2(content as unknown as Omit<PuzzleDocumentV2, 'integrity'>);
}

type ExpectedRun = Readonly<{
  number: number;
  direction: 'across' | 'down';
  cellIds: readonly string[];
}>;

function deriveExpectedRuns(cells: readonly PuzzleV2Cell[]): readonly ExpectedRun[] {
  const cellAt = new Map(cells.map((cell) => [`${cell.row}:${cell.column}`, cell] as const));
  const entries: ExpectedRun[] = [];
  let nextNumber = 1;
  for (let row = 0; row < PUZZLE_DOCUMENT_V2_SIZE; row += 1) {
    for (let column = 0; column < PUZZLE_DOCUMENT_V2_SIZE; column += 1) {
      const cell = cellAt.get(`${row}:${column}`);
      if (!cell || cell.block) continue;
      const left = cellAt.get(`${row}:${column - 1}`);
      const above = cellAt.get(`${row - 1}:${column}`);
      const startsAcross = !left || left.block;
      const startsDown = !above || above.block;
      if (!startsAcross && !startsDown) continue;
      const number = nextNumber;
      nextNumber += 1;
      if (startsAcross) {
        const cellIds: string[] = [];
        for (let c = column; c < PUZZLE_DOCUMENT_V2_SIZE; c += 1) {
          const part = cellAt.get(`${row}:${c}`);
          if (!part || part.block) break;
          cellIds.push(part.id);
        }
        entries.push({ number, direction: 'across', cellIds });
      }
      if (startsDown) {
        const cellIds: string[] = [];
        for (let r = row; r < PUZZLE_DOCUMENT_V2_SIZE; r += 1) {
          const part = cellAt.get(`${r}:${column}`);
          if (!part || part.block) break;
          cellIds.push(part.id);
        }
        entries.push({ number, direction: 'down', cellIds });
      }
    }
  }
  return entries;
}

function arraysEqual(left: readonly unknown[], right: readonly unknown[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function addIssue(
  issues: PuzzleV2ValidationIssue[],
  code: string,
  message: string,
  path?: string,
): void {
  issues.push(path ? { code, path, message } : { code, message });
}

function validateExactShape(value: unknown, keys: readonly string[], path: string, issues: PuzzleV2ValidationIssue[], optional: readonly string[] = []): value is RecordValue {
  if (!isRecord(value) || !hasExactKeys(value, keys, optional)) {
    addIssue(issues, 'shape', 'Object does not have the exact supported fields.', path);
    return false;
  }
  return true;
}

function validateSourcePin(value: unknown, path: string, issues: PuzzleV2ValidationIssue[]): value is PuzzleV2SourcePin {
  if (!validateExactShape(value, ['sourceId', 'version', 'artifactSha256', 'spdx', 'attribution', 'contentClass'], path, issues)) return false;
  const source = value;
  if (!isNonEmptyString(source.sourceId) || !isNonEmptyString(source.version) || typeof source.artifactSha256 !== 'string' || !RAW_SHA256_PATTERN.test(source.artifactSha256) || !isNonEmptyString(source.spdx) || !isNonEmptyString(source.attribution) || !['public', 'synthetic'].includes(String(source.contentClass))) {
    addIssue(issues, 'source-pin', 'Source identity, digest, license, attribution, or content class is invalid.', path);
    return false;
  }
  return true;
}

function validateEvidenceProvenance(
  value: unknown,
  allowedSourceIds: readonly string[],
  sources: readonly unknown[],
  path: string,
  issues: PuzzleV2ValidationIssue[],
): value is PuzzleV2EvidenceProvenance {
  if (!isRecord(value) || !hasExactKeys(value, ['source', 'evidenceRefs', 'reviewerId', 'reviewedAt'])) {
    addIssue(issues, 'evidence-provenance-shape', 'Reviewed evidence provenance has an invalid exact shape.', path);
    return false;
  }
  const linkedSource = value.source;
  if (!isRecord(linkedSource) || !hasExactKeys(linkedSource, ['sourceId', 'version', 'artifactSha256', 'spdx', 'attribution', 'contentClass'])) {
    addIssue(issues, 'evidence-source-shape', 'Evidence source pin has an invalid shape.', `${path}.source`);
    return false;
  }
  const sourcePin = sources.find((item) => isRecord(item) && item.sourceId === linkedSource.sourceId) as PuzzleV2SourcePin | undefined;
  if (!sourcePin || !allowedSourceIds.includes(String(linkedSource.sourceId)) || sourcePin.version !== linkedSource.version || sourcePin.artifactSha256 !== linkedSource.artifactSha256 || sourcePin.spdx !== linkedSource.spdx || sourcePin.attribution !== linkedSource.attribution || sourcePin.contentClass !== linkedSource.contentClass) {
    addIssue(issues, 'evidence-source-link', 'Evidence source must exactly match a linked pinned source.', path);
  }
  if (!Array.isArray(value.evidenceRefs) || value.evidenceRefs.length === 0 || !uniqueStrings(value.evidenceRefs) || !isNonEmptyString(value.reviewerId) || !isIsoDate(value.reviewedAt)) {
    addIssue(issues, 'evidence-review', 'Evidence provenance needs unique references, reviewer, and date.', path);
  }
  return true;
}

function validateProvenance(value: unknown, entriesById: ReadonlyMap<string, PuzzleV2Entry>, cluesById: ReadonlyMap<string, PuzzleV2ClueVariant>, issues: PuzzleV2ValidationIssue[]): value is PuzzleV2Provenance {
  if (!validateExactShape(value, ['sources', 'lexemes', 'senses', 'facts', 'clues'], 'provenance', issues)) return false;
  const provenance = value;
  if (![provenance.sources, provenance.lexemes, provenance.senses, provenance.facts, provenance.clues].every(Array.isArray)) {
    addIssue(issues, 'provenance-arrays', 'Every provenance collection must be an array.', 'provenance');
    return false;
  }
  const sources = provenance.sources as unknown[];
  const sourceIds = new Set<string>();
  sources.forEach((source, index) => {
    if (!validateSourcePin(source, `provenance.sources[${index}]`, issues)) return;
    if (sourceIds.has(source.sourceId)) addIssue(issues, 'duplicate-source', 'Source IDs must be unique.', `provenance.sources[${index}].sourceId`);
    sourceIds.add(source.sourceId);
  });
  const idsFor = <T extends RecordValue>(rows: readonly unknown[], required: readonly string[], label: string, identityKey = 'id'): Map<string, T> => {
    const output = new Map<string, T>();
    rows.forEach((row, index) => {
      if (!validateExactShape(row, required, `provenance.${label}[${index}]`, issues)) return;
      const identity = row[identityKey];
      if (!isNonEmptyString(identity)) {
        addIssue(issues, 'provenance-id', `Provenance ${identityKey} must be nonempty.`, `provenance.${label}[${index}].${identityKey}`);
      } else if (output.has(identity)) {
        addIssue(issues, 'duplicate-provenance', `${label} IDs must be unique.`, `provenance.${label}[${index}].${identityKey}`);
      } else output.set(identity, row as T);
    });
    return output;
  };
  const sourceLinks = (raw: unknown, path: string): raw is readonly string[] => {
    if (!Array.isArray(raw) || raw.length === 0 || !uniqueStrings(raw) || !raw.every((id) => sourceIds.has(id))) {
      addIssue(issues, 'source-link', 'Source IDs must be a nonempty, unique list of pinned sources.', path);
      return false;
    }
    return true;
  };
  const lexemes = idsFor<PuzzleV2LexemeProvenance & RecordValue>(provenance.lexemes as unknown[], ['id', 'sourceIds'], 'lexemes');
  const senses = idsFor<PuzzleV2SenseProvenance & RecordValue>(provenance.senses as unknown[], ['id', 'lexemeId', 'sourceIds', 'evidenceProvenance'], 'senses');
  const facts = idsFor<PuzzleV2FactProvenance & RecordValue>(provenance.facts as unknown[], ['id', 'lexemeId', 'sourceIds', 'review', 'evidenceProvenance'], 'facts');
  const clueProvenance = idsFor<PuzzleV2ClueProvenance & RecordValue>(provenance.clues as unknown[], ['clueVariantId', 'sourceClueId', 'entryId', 'senseIds', 'factIds', 'sourceIds', 'evidenceKind', 'evidenceId', 'evidenceRefs', 'evidenceProvenance', 'reviewerId', 'reviewedAt', 'semanticTruthStatus'], 'clues', 'clueVariantId');

  lexemes.forEach((row, id) => sourceLinks(row.sourceIds, `provenance.lexemes.${id}.sourceIds`));
  senses.forEach((row, id) => {
    if (!lexemes.has(String(row.lexemeId))) addIssue(issues, 'unknown-lexeme', 'Sense references an unknown lexeme.', `provenance.senses.${id}.lexemeId`);
    sourceLinks(row.sourceIds, `provenance.senses.${id}.sourceIds`);
    validateEvidenceProvenance(row.evidenceProvenance, Array.isArray(row.sourceIds) ? row.sourceIds as string[] : [], sources, `provenance.senses.${id}.evidenceProvenance`, issues);
  });
  facts.forEach((row, id) => {
    if (!lexemes.has(String(row.lexemeId))) addIssue(issues, 'unknown-lexeme', 'Fact references an unknown lexeme.', `provenance.facts.${id}.lexemeId`);
    sourceLinks(row.sourceIds, `provenance.facts.${id}.sourceIds`);
    validateEvidenceProvenance(row.evidenceProvenance, Array.isArray(row.sourceIds) ? row.sourceIds as string[] : [], sources, `provenance.facts.${id}.evidenceProvenance`, issues);
    if (!['verified', 'quarantined', 'retired'].includes(String(row.review))) addIssue(issues, 'fact-review', 'Fact review status is unknown.', `provenance.facts.${id}.review`);
  });

  const clueVariants = new Set(cluesById.keys());
  if (clueProvenance.size !== clueVariants.size || [...clueVariants].some((id) => !clueProvenance.has(id))) {
    addIssue(issues, 'clue-provenance-coverage', 'Every clue variant must have exactly one provenance record.', 'provenance.clues');
  }
  clueProvenance.forEach((row, id) => {
    const clue = cluesById.get(id);
    const entry = entriesById.get(String(row.entryId));
    if (!clue || clue.entryId !== row.entryId || clue.sourceClueId !== row.sourceClueId) addIssue(issues, 'clue-provenance-link', 'Clue provenance must resolve to its exact source clue, clue variant, and entry.', `provenance.clues.${id}`);
    if (!entry) addIssue(issues, 'clue-entry-link', 'Clue provenance references an unknown entry.', `provenance.clues.${id}.entryId`);
    if (!Array.isArray(row.senseIds) || !uniqueStrings(row.senseIds) || !Array.isArray(row.factIds) || !uniqueStrings(row.factIds)) {
      addIssue(issues, 'clue-evidence-shape', 'Clue sense/fact references must be unique ID arrays.', `provenance.clues.${id}`);
      return;
    }
    if (!clue || !arraysEqual(row.senseIds, clue.support.senseIds) || !arraysEqual(row.factIds, clue.support.factIds)) {
      addIssue(issues, 'clue-evidence-mismatch', 'Clue provenance references must exactly match the clue support declaration.', `provenance.clues.${id}`);
    }
    if (!entry || !row.senseIds.includes(entry.senseId)) addIssue(issues, 'entry-sense-support', 'Clue support must cite the entry’s pinned sense.', `provenance.clues.${id}.senseIds`);
    if (!sourceLinks(row.sourceIds, `provenance.clues.${id}.sourceIds`)) return;
    row.senseIds.forEach((senseId) => {
      const sense = senses.get(senseId);
      if (!sense || (entry && sense.lexemeId !== entry.lexemeId)) addIssue(issues, 'sense-support-link', 'Supported sense must resolve to the entry lexeme.', `provenance.clues.${id}.senseIds`);
      else if (!sense.sourceIds.some((sourceId) => row.sourceIds.includes(sourceId))) addIssue(issues, 'sense-source-link', 'Clue source list must include a source supporting each cited sense.', `provenance.clues.${id}.sourceIds`);
    });
    row.factIds.forEach((factId) => {
      const fact = facts.get(factId);
      if (!fact || !entry || fact.lexemeId !== entry.lexemeId || fact.review !== 'verified') addIssue(issues, 'fact-support-link', 'Cited facts must be verified and linked to the entry lexeme.', `provenance.clues.${id}.factIds`);
      else if (!fact.sourceIds.some((sourceId) => row.sourceIds.includes(sourceId))) addIssue(issues, 'fact-source-link', 'Clue source list must include a source supporting each cited fact.', `provenance.clues.${id}.sourceIds`);
    });
    if (row.evidenceKind !== 'sense' && row.evidenceKind !== 'fact') addIssue(issues, 'evidence-kind', 'Evidence kind must be sense or fact.', `provenance.clues.${id}.evidenceKind`);
    if (typeof row.evidenceId !== 'string' || !row.evidenceId.trim()) {
      addIssue(issues, 'evidence-id', 'Primary evidence ID must be a nonempty string.', `provenance.clues.${id}.evidenceId`);
    } else if (row.evidenceKind === 'sense' && (!row.senseIds.includes(row.evidenceId) || !senses.has(row.evidenceId))) {
      addIssue(issues, 'evidence-link', 'Primary sense evidence must appear in clue support.', `provenance.clues.${id}.evidenceId`);
    } else if (row.evidenceKind === 'fact' && (!row.factIds.includes(row.evidenceId) || !facts.has(row.evidenceId))) {
      addIssue(issues, 'evidence-link', 'Primary fact evidence must appear in clue support.', `provenance.clues.${id}.evidenceId`);
    }
    if (!Array.isArray(row.evidenceRefs) || row.evidenceRefs.length === 0 || !uniqueStrings(row.evidenceRefs)) addIssue(issues, 'evidence-refs', 'Clue evidence references must be nonempty unique IDs.', `provenance.clues.${id}.evidenceRefs`);
    if (!isNonEmptyString(row.reviewerId) || !isIsoDate(row.reviewedAt)) addIssue(issues, 'clue-review', 'Clue reviewer and ISO review date are required.', `provenance.clues.${id}`);
    if (row.semanticTruthStatus !== 'not-established-by-grammar-validator') addIssue(issues, 'semantic-status', 'This schema slice records that grammar validation does not establish semantic truth.', `provenance.clues.${id}.semanticTruthStatus`);
    validateEvidenceProvenance(row.evidenceProvenance, Array.isArray(row.sourceIds) ? row.sourceIds as string[] : [], sources, `provenance.clues.${id}.evidenceProvenance`, issues);
    const primaryEvidence = typeof row.evidenceId === 'string'
      ? row.evidenceKind === 'fact' ? facts.get(row.evidenceId) : senses.get(row.evidenceId)
      : undefined;
    if (primaryEvidence && canonicalJson(primaryEvidence.evidenceProvenance) !== canonicalJson(row.evidenceProvenance)) addIssue(issues, 'evidence-provenance-mismatch', 'Clue must preserve the exact linked sense/fact provenance; clue-level review fields are separate.', `provenance.clues.${id}.evidenceProvenance`);
  });

  const expectedLexemeIds = new Set([...entriesById.values()].map((entry) => entry.lexemeId));
  const expectedSenseIds = new Set([...entriesById.values()].map((entry) => entry.senseId));
  const expectedFactIds = new Set<string>();
  cluesById.forEach((clue) => {
    clue.support.senseIds.forEach((id) => expectedSenseIds.add(id));
    clue.support.factIds.forEach((id) => expectedFactIds.add(id));
  });
  const sameSet = (left: ReadonlySet<string>, right: ReadonlySet<string>): boolean => left.size === right.size && [...left].every((id) => right.has(id));
  if (!sameSet(expectedLexemeIds, new Set(lexemes.keys()))) addIssue(issues, 'lexeme-provenance-coverage', 'Lexeme provenance must exactly cover entry lexeme references.', 'provenance.lexemes');
  if (!sameSet(expectedSenseIds, new Set(senses.keys()))) addIssue(issues, 'sense-provenance-coverage', 'Sense provenance must exactly cover entry and clue support references.', 'provenance.senses');
  if (!sameSet(expectedFactIds, new Set(facts.keys()))) addIssue(issues, 'fact-provenance-coverage', 'Fact provenance must exactly cover clue support references.', 'provenance.facts');
  const referencedSourceIds = new Set<string>();
  for (const row of [...lexemes.values(), ...senses.values(), ...facts.values(), ...clueProvenance.values()]) {
    if (Array.isArray(row.sourceIds)) row.sourceIds.forEach((sourceId) => referencedSourceIds.add(String(sourceId)));
  }
  if (!sameSet(referencedSourceIds, sourceIds)) addIssue(issues, 'source-provenance-coverage', 'Pinned source records must exactly cover source links used by content provenance.', 'provenance.sources');
  return issues.length === 0;
}

function validateGrid(value: RecordValue, issues: PuzzleV2ValidationIssue[]): ReadonlyMap<string, PuzzleV2Entry> | null {
  if (!Array.isArray(value.cells) || !Array.isArray(value.entries)) {
    addIssue(issues, 'grid-arrays', 'Cells and entries must be arrays.', 'grid');
    return null;
  }
  const cells = value.cells as unknown[];
  const entries = value.entries as unknown[];
  if (cells.length !== PUZZLE_DOCUMENT_V2_SIZE ** 2) addIssue(issues, 'cell-count', 'A V2 construction grid has exactly 225 cells.', 'cells');
  const cellById = new Map<string, PuzzleV2Cell>();
  const cellAt = new Map<string, PuzzleV2Cell>();
  cells.forEach((rawCell, index) => {
    const path = `cells[${index}]`;
    if (!validateExactShape(rawCell, ['id', 'row', 'column', 'block', 'circled', 'shaded', 'token'], path, issues)) return;
    const cell = rawCell as unknown as PuzzleV2Cell;
    if (!isNonEmptyString(cell.id) || !Number.isInteger(cell.row) || !Number.isInteger(cell.column) || cell.row < 0 || cell.row >= 15 || cell.column < 0 || cell.column >= 15 || typeof cell.block !== 'boolean' || typeof cell.circled !== 'boolean' || typeof cell.shaded !== 'boolean') {
      addIssue(issues, 'cell', 'Cell identity, coordinate, or decoration is invalid.', path);
      return;
    }
    if (cellById.has(cell.id) || cellAt.has(`${cell.row}:${cell.column}`)) addIssue(issues, 'duplicate-cell', 'Cell IDs and coordinates must be unique.', path);
    if (cell.block ? cell.token !== null : (typeof cell.token !== 'string' || !/^[A-Z]$/.test(cell.token))) addIssue(issues, 'cell-token', 'Blocks need null tokens and open cells need exactly one A-Z token; rebus and multi-token cells are unsupported.', `${path}.token`);
    cellById.set(cell.id, cell);
    cellAt.set(`${cell.row}:${cell.column}`, cell);
  });
  for (let row = 0; row < 15; row += 1) {
    for (let column = 0; column < 15; column += 1) {
      const cell = cellAt.get(`${row}:${column}`);
      if (!cell) addIssue(issues, 'missing-cell', 'Every 15x15 coordinate must appear exactly once.', `cells[${row},${column}]`);
      else if (cells[row * 15 + column] !== cell) addIssue(issues, 'cell-order', 'Cells must be stored in row-major order.', `cells[${row * 15 + column}]`);
    }
  }
  const entryById = new Map<string, PuzzleV2Entry>();
  const actualRuns = new Map<string, PuzzleV2Entry>();
  entries.forEach((rawEntry, index) => {
    const path = `entries[${index}]`;
    if (!validateExactShape(rawEntry, ['id', 'number', 'direction', 'cellIds', 'answer', 'lexemeId', 'senseId'], path, issues, ['retrievalTaskId'])) return;
    const entry = rawEntry as unknown as PuzzleV2Entry;
    if (!isNonEmptyString(entry.id) || !Number.isInteger(entry.number) || entry.number < 1 || (entry.direction !== 'across' && entry.direction !== 'down') || !Array.isArray(entry.cellIds) || entry.cellIds.length < 3 || !uniqueStrings(entry.cellIds) || !/^[A-Z]+$/.test(entry.answer) || entry.answer.length !== entry.cellIds.length || !isNonEmptyString(entry.lexemeId) || !isNonEmptyString(entry.senseId) || (entry.retrievalTaskId !== undefined && !isNonEmptyString(entry.retrievalTaskId))) {
      addIssue(issues, 'entry', 'Entry fields or lexical answer are invalid.', path);
      return;
    }
    const key = `${entry.direction}:${entry.number}`;
    if (entryById.has(entry.id) || actualRuns.has(key)) addIssue(issues, 'duplicate-entry', 'Entry IDs and direction-number pairs must be unique.', path);
    entryById.set(entry.id, entry);
    actualRuns.set(key, entry);
    const cellsForEntry = entry.cellIds.map((cellId) => cellById.get(cellId));
    if (cellsForEntry.some((cell) => !cell || cell.block)) addIssue(issues, 'entry-cell-link', 'Entry references a missing or blocked cell.', `${path}.cellIds`);
    const letters = cellsForEntry.map((cell) => cell?.token ?? '').join('');
    if (letters !== entry.answer) addIssue(issues, 'entry-answer', 'Entry answer must equal its one-letter cell tokens.', `${path}.answer`);
    cellsForEntry.forEach((cell, position) => {
      const previous = cellsForEntry[position - 1];
      if (!cell || !previous) return;
      const contiguous = entry.direction === 'across'
        ? cell.row === previous.row && cell.column === previous.column + 1
        : cell.column === previous.column && cell.row === previous.row + 1;
      if (!contiguous) addIssue(issues, 'entry-contiguity', 'Entry cells must be contiguous in their direction.', `${path}.cellIds`);
    });
  });

  const blockedCellIds = cells.filter((cell): cell is PuzzleV2Cell => isRecord(cell) && cell.block === true).map((cell) => cell.id);
  const topology = value.topology;
  if (!validateExactShape(topology, ['width', 'height', 'blockedCellIds', 'minEntryLength', 'numbering'], 'topology', issues)) return entryById;
  if (topology.width !== 15 || topology.height !== 15 || topology.minEntryLength !== 3 || topology.numbering !== 'standard-row-major-v1' || !Array.isArray(topology.blockedCellIds) || !uniqueStrings(topology.blockedCellIds) || !arraysEqual([...topology.blockedCellIds].sort(), [...blockedCellIds].sort())) addIssue(issues, 'topology', 'Topology must describe the exact 15x15 blocked cells and standard numbering policy.', 'topology');

  if (cellAt.size === 225) {
    const expectedRuns = deriveExpectedRuns([...cellAt.values()]);
    const expectedByKey = new Map<string, ExpectedRun>(expectedRuns.map((run) => [`${run.direction}:${run.number}`, run] as const));
    if (actualRuns.size !== expectedByKey.size) addIssue(issues, 'run-coverage', 'Entries must exactly cover all maximal across and down runs.', 'entries');
    expectedByKey.forEach((run, key) => {
      const entry = actualRuns.get(key);
      if (!entry || entry.cellIds.length < 3 || !arraysEqual(entry.cellIds, run.cellIds)) addIssue(issues, 'run-mismatch', 'Each entry must exactly match a numbered maximal run of at least three cells.', `entries.${key}`);
    });
    actualRuns.forEach((entry, key) => {
      if (!expectedByKey.has(key)) addIssue(issues, 'stray-run', 'Entry does not correspond to a standard numbered grid run.', `entries.${key}`);
    });
  }

  const openCells = cells.filter((cell): cell is PuzzleV2Cell => isRecord(cell) && cell.block === false);
  const acrossAt = new Map<string, PuzzleV2Entry>();
  const downAt = new Map<string, PuzzleV2Entry>();
  entryById.forEach((entry) => entry.cellIds.forEach((cellId) => (entry.direction === 'across' ? acrossAt : downAt).set(cellId, entry)));
  openCells.forEach((cell) => {
    if (!acrossAt.has(cell.id) || !downAt.has(cell.id)) addIssue(issues, 'unchecked-cell', 'Every open cell must belong to one across and one down entry.', `cells.${cell.id}`);
  });
  return entryById;
}

function validateMechanics(value: unknown, entries: ReadonlyMap<string, PuzzleV2Entry>, issues: PuzzleV2ValidationIssue[]): value is readonly PuzzleMechanic[] {
  if (!Array.isArray(value)) {
    addIssue(issues, 'mechanics', 'Mechanics must be an array.', 'mechanics');
    return false;
  }
  const ids = new Set<string>();
  value.forEach((rawMechanic, index) => {
    const path = `mechanics[${index}]`;
    if (!validateExactShape(rawMechanic, ['id', 'family', 'affectedEntryIds'], path, issues, ['requiredSignal', 'explanationRequired'])) return;
    const mechanic = rawMechanic;
    if (!isNonEmptyString(mechanic.id) || !isNonEmptyString(mechanic.family) || ids.has(String(mechanic.id)) || !Array.isArray(mechanic.affectedEntryIds) || mechanic.affectedEntryIds.length === 0 || !uniqueStrings(mechanic.affectedEntryIds) || !mechanic.affectedEntryIds.every((id) => entries.has(id))) addIssue(issues, 'mechanic', 'Mechanic must have a unique ID and reference existing affected entries.', path);
    if (mechanic.requiredSignal !== undefined && !['theme-indicator', 'mechanic-indicator'].includes(String(mechanic.requiredSignal))) addIssue(issues, 'mechanic-signal', 'Mechanic signal is unsupported.', `${path}.requiredSignal`);
    if (mechanic.explanationRequired !== undefined && typeof mechanic.explanationRequired !== 'boolean') addIssue(issues, 'mechanic-explanation', 'explanationRequired must be boolean.', `${path}.explanationRequired`);
    ids.add(String(mechanic.id));
  });
  return true;
}

function validateClues(value: unknown, entries: ReadonlyMap<string, PuzzleV2Entry>, mechanics: readonly PuzzleMechanic[], issues: PuzzleV2ValidationIssue[]): ReadonlyMap<string, PuzzleV2ClueVariant> {
  const output = new Map<string, PuzzleV2ClueVariant>();
  if (!Array.isArray(value)) {
    addIssue(issues, 'clues', 'Clues must be an array.', 'clues');
    return output;
  }
  const counts = new Map<string, number>();
  const entryRefs = [...entries.values()].map((entry) => ({ entryId: entry.id, number: entry.number, direction: entry.direction }));
  value.forEach((rawClue, index) => {
    const path = `clues[${index}]`;
    if (!validateExactShape(rawClue, ['clueVariantId', 'sourceClueId', 'entryId', 'variantRole', 'primaryFamily', 'text', 'grammar', 'support'], path, issues)) return;
    const clue = rawClue as unknown as PuzzleV2ClueVariant;
    const entry = entries.get(clue.entryId);
    if (!isNonEmptyString(clue.clueVariantId) || !isNonEmptyString(clue.sourceClueId) || output.has(clue.clueVariantId) || !entry || !isNonEmptyString(clue.text) || !isRecord(clue.support) || !hasExactKeys(clue.support, ['senseIds', 'factIds']) || !Array.isArray(clue.support.senseIds) || !Array.isArray(clue.support.factIds) || !uniqueStrings(clue.support.senseIds) || !uniqueStrings(clue.support.factIds)) {
      addIssue(issues, 'clue', 'Clue identity, entry, literal text, or support is invalid.', path);
      return;
    }
    const grammarRecord = clue.grammar as unknown;
    const grammarAllowed = ['grammarVersion', 'clueId', 'entryId', 'clueText', 'answer', 'variantRole', 'primaryFamily', 'signalSpans'];
    const grammarOptional = ['answerIsAbbreviation', 'morphology', 'interpretation', 'abbreviationEvidence', 'mechanicRef'];
    if (!isRecord(grammarRecord) || !hasExactKeys(grammarRecord, grammarAllowed, grammarOptional)) {
      addIssue(issues, 'grammar-shape', 'Clue grammar annotation has unsupported or missing top-level fields.', `${path}.grammar`);
      return;
    }
    if (clue.grammar.grammarVersion !== CLUE_GRAMMAR_VERSION || clue.grammar.clueId !== clue.clueVariantId || clue.grammar.entryId !== clue.entryId || clue.grammar.clueText !== clue.text || clue.grammar.answer !== entry.answer || clue.grammar.variantRole !== clue.variantRole || clue.grammar.primaryFamily !== clue.primaryFamily) addIssue(issues, 'grammar-link', 'Grammar annotation must exactly match the clue variant and pinned entry answer.', `${path}.grammar`);
    const result = validateClueGrammar(clue.grammar, { currentEntryId: entry.id, entries: entryRefs, mechanics });
    result.issues.forEach((issue) => addIssue(issues, `grammar-${issue.code}`, issue.message, issue.path ? `${path}.grammar.${issue.path}` : `${path}.grammar`));
    output.set(clue.clueVariantId, clue);
    counts.set(clue.entryId, (counts.get(clue.entryId) ?? 0) + 1);
  });
  entries.forEach((_entry, id) => {
    if (!counts.has(id)) addIssue(issues, 'missing-clue', 'Every entry needs at least one reviewed clue variant.', `entries.${id}`);
  });
  return output;
}

function validateCrossingSupport(value: unknown, entries: ReadonlyMap<string, PuzzleV2Entry>, cells: readonly PuzzleV2Cell[], issues: PuzzleV2ValidationIssue[]): PuzzleV2CrossingSupport | null {
  if (!validateExactShape(value, ['version', 'edges', 'minimumScore', 'meanScore', 'uncertainty'], 'crossingSupport', issues)) return null;
  const report = value as unknown as PuzzleV2CrossingSupport;
  if (!isNonEmptyString(report.version) || !Array.isArray(report.edges) || !isFiniteUnit(report.minimumScore) || !isFiniteUnit(report.meanScore) || !validateExactShape(report.uncertainty, ['level', 'notes'], 'crossingSupport.uncertainty', issues) || !['low', 'medium', 'high', 'unknown'].includes(String(report.uncertainty.level)) || typeof report.uncertainty.notes !== 'string') {
    addIssue(issues, 'crossing-report', 'Crossing support report is malformed.', 'crossingSupport');
    return null;
  }
  const acrossAt = new Map<string, PuzzleV2Entry>();
  const downAt = new Map<string, PuzzleV2Entry>();
  entries.forEach((entry) => entry.cellIds.forEach((cellId) => (entry.direction === 'across' ? acrossAt : downAt).set(cellId, entry)));
  const expected = new Set(cells.filter((cell) => !cell.block).map((cell) => cell.id));
  const seen = new Set<string>();
  const scores: number[] = [];
  report.edges.forEach((rawEdge, index) => {
    const path = `crossingSupport.edges[${index}]`;
    if (!validateExactShape(rawEdge, ['acrossEntryId', 'downEntryId', 'cellId', 'score', 'confidence'], path, issues)) return;
    const edge = rawEdge as unknown as PuzzleV2CrossingSupport['edges'][number];
    const across = entries.get(edge.acrossEntryId);
    const down = entries.get(edge.downEntryId);
    if (!across || across.direction !== 'across' || !down || down.direction !== 'down' || !across.cellIds.includes(edge.cellId) || !down.cellIds.includes(edge.cellId) || seen.has(edge.cellId) || !isFiniteUnit(edge.score) || !isFiniteUnit(edge.confidence)) addIssue(issues, 'crossing-edge', 'Each edge must link the exact across/down entries at a unique open cell with finite scores.', path);
    seen.add(edge.cellId);
    scores.push(edge.score);
  });
  if (seen.size !== expected.size || [...expected].some((cellId) => !seen.has(cellId))) addIssue(issues, 'crossing-coverage', 'Crossing support must cover every open cell exactly once.', 'crossingSupport.edges');
  if (scores.length > 0) {
    const minimum = Math.min(...scores);
    const mean = scores.reduce((sum, score) => sum + score, 0) / scores.length;
    if (Math.abs(minimum - report.minimumScore) > 1e-9 || Math.abs(mean - report.meanScore) > 1e-9) addIssue(issues, 'crossing-aggregate', 'Reported minimum and mean must match the crossing edge scores.', 'crossingSupport');
  }
  if (report.version === 'structural-letter-agreement-v1' && (
    report.uncertainty.level !== 'unknown' ||
    report.edges.some((edge) => !isRecord(edge) || edge.score !== 0 || edge.confidence !== 0)
  )) {
    addIssue(issues, 'structural-crossing-estimate', 'Structural letter agreement cannot claim calibrated player support.', 'crossingSupport');
  }
  return report;
}

function validateReceipt(value: unknown, seed: unknown, issues: PuzzleV2ValidationIssue[]): value is PuzzleV2Receipt {
  if (!validateExactShape(value, ['constructionSeed', 'recipe', 'runtime', 'validators', 'generatedAt'], 'receipt', issues, ['profileProjection'])) return false;
  const receipt = value;
  if (!isNonEmptyString(receipt.constructionSeed) || receipt.constructionSeed !== seed || !validateExactShape(receipt.recipe, ['id', 'version', 'weekday'], 'receipt.recipe', issues) || !isNonEmptyString(receipt.recipe.id) || !isNonEmptyString(receipt.recipe.version) || !WEEKDAYS.includes(String(receipt.recipe.weekday)) || !validateExactShape(receipt.runtime, ['id', 'version', 'artifactDigest'], 'receipt.runtime', issues) || !isNonEmptyString(receipt.runtime.id) || !isNonEmptyString(receipt.runtime.version) || typeof receipt.runtime.artifactDigest !== 'string' || !RAW_SHA256_PATTERN.test(receipt.runtime.artifactDigest) || !Array.isArray(receipt.validators) || receipt.validators.length === 0 || !isIsoDateTime(receipt.generatedAt)) {
    addIssue(issues, 'receipt', 'Generation receipt or construction recipe is malformed.', 'receipt');
    return false;
  }
  const validatorIds = new Set<string>();
  receipt.validators.forEach((rawValidator, index) => {
    const path = `receipt.validators[${index}]`;
    if (!validateExactShape(rawValidator, ['id', 'version'], path, issues)) return;
    if (!isNonEmptyString(rawValidator.id) || !isNonEmptyString(rawValidator.version) || validatorIds.has(String(rawValidator.id))) addIssue(issues, 'receipt-validator', 'Validator IDs and versions must be unique and nonempty.', path);
    validatorIds.add(String(rawValidator.id));
  });
  if (receipt.profileProjection !== undefined) {
    const profileProjection = receipt.profileProjection;
    if (!validateExactShape(profileProjection, ['revision', 'digest'], 'receipt.profileProjection', issues) || typeof profileProjection.revision !== 'number' || !Number.isInteger(profileProjection.revision) || profileProjection.revision < 0 || typeof profileProjection.digest !== 'string' || !RAW_SHA256_PATTERN.test(profileProjection.digest)) addIssue(issues, 'profile-projection', 'Private profile projection receipt is malformed.', 'receipt.profileProjection');
  }
  return true;
}

function validateQuality(value: unknown, clueIds: ReadonlySet<string>, sourceIds: ReadonlySet<string>, crossing: PuzzleV2CrossingSupport | null, issues: PuzzleV2ValidationIssue[]): value is PuzzleV2Quality {
  if (!validateExactShape(value, ['verdict', 'reasons'], 'quality', issues, ['semanticAttestation'])) return false;
  const quality = value;
  if (!['accept', 'review', 'reject'].includes(String(quality.verdict)) || !Array.isArray(quality.reasons) || !quality.reasons.every(isNonEmptyString)) {
    addIssue(issues, 'quality', 'Quality verdict and reasons are malformed.', 'quality');
    return false;
  }
  let attested = false;
  if (quality.semanticAttestation !== undefined) {
    const attestation = quality.semanticAttestation;
    if (!validateExactShape(attestation, ['reviewerId', 'reviewedAt', 'clueVariantIds', 'sourceIds', 'evidenceRefs'], 'quality.semanticAttestation', issues) || !isNonEmptyString(attestation.reviewerId) || !isIsoDate(attestation.reviewedAt) || !Array.isArray(attestation.clueVariantIds) || !uniqueStrings(attestation.clueVariantIds) || !arraysEqual([...attestation.clueVariantIds].sort(), [...clueIds].sort()) || !Array.isArray(attestation.sourceIds) || attestation.sourceIds.length === 0 || !uniqueStrings(attestation.sourceIds) || !attestation.sourceIds.every((id) => sourceIds.has(id)) || !Array.isArray(attestation.evidenceRefs) || attestation.evidenceRefs.length === 0 || !uniqueStrings(attestation.evidenceRefs)) {
      addIssue(issues, 'semantic-attestation', 'Semantic review must identify a reviewer, date, pinned sources, evidence, and every exact clue variant.', 'quality.semanticAttestation');
    } else attested = true;
  }
  if (quality.verdict === 'accept' && (!attested || !crossing || crossing.uncertainty.level === 'unknown' || crossing.uncertainty.level === 'high')) addIssue(issues, 'acceptance-gate', 'Accept requires a separate complete semantic attestation and crossing uncertainty below high/unknown.', 'quality.verdict');
  return true;
}

/** Runtime validation at the persistence/publication boundary, including SHA-256 integrity. */
export async function validatePuzzleDocumentV2(value: unknown): Promise<PuzzleV2Validation> {
  const issues: PuzzleV2ValidationIssue[] = [];
  const rootKeys = ['schemaVersion', 'id', 'seed', 'title', 'subtitle', 'width', 'height', 'language', 'languagePolicy', 'cells', 'entries', 'clues', 'mechanics', 'provenance', 'topology', 'receipt', 'crossingSupport', 'quality', 'integrity'];
  if (!validateExactShape(value, rootKeys, 'puzzle', issues)) return { valid: false, issues };
  const puzzle = value;
  if (puzzle.schemaVersion !== 2 || !isNonEmptyString(puzzle.id) || !isNonEmptyString(puzzle.seed) || !isNonEmptyString(puzzle.title) || typeof puzzle.subtitle !== 'string' || puzzle.width !== 15 || puzzle.height !== 15 || typeof puzzle.language !== 'string' || !LANGUAGE_PATTERN.test(puzzle.language)) addIssue(issues, 'identity', 'Puzzle identity, language, and fixed 15x15 dimensions are invalid.', 'puzzle');
  if (!validateExactShape(puzzle.languagePolicy, ['version', 'cellTokenPolicy'], 'languagePolicy', issues) || puzzle.languagePolicy.version !== 'ascii-uppercase-v1' || puzzle.languagePolicy.cellTokenPolicy !== 'single-ascii-letter-v1') addIssue(issues, 'language-policy', 'This version supports only single uppercase ASCII letters.', 'languagePolicy');
  const entriesById = validateGrid(puzzle, issues) ?? new Map<string, PuzzleV2Entry>();
  const mechanicsValid = validateMechanics(puzzle.mechanics, entriesById, issues);
  const mechanics: readonly PuzzleMechanic[] = mechanicsValid ? puzzle.mechanics as unknown as readonly PuzzleMechanic[] : [];
  const cluesById = validateClues(puzzle.clues, entriesById, mechanics, issues);
  const provenanceValid = validateProvenance(puzzle.provenance, entriesById, cluesById, issues);
  validateReceipt(puzzle.receipt, puzzle.seed, issues);
  const cells = Array.isArray(puzzle.cells) ? puzzle.cells.filter((cell): cell is PuzzleV2Cell => isRecord(cell) && typeof cell.id === 'string' && typeof cell.block === 'boolean') : [];
  const crossing = validateCrossingSupport(puzzle.crossingSupport, entriesById, cells, issues);
  const provenanceSourceIds = isRecord(puzzle.provenance) && Array.isArray(puzzle.provenance.sources)
    ? new Set(puzzle.provenance.sources.filter((source) => isRecord(source) && typeof source.sourceId === 'string').map((source) => String((source as RecordValue).sourceId)))
    : new Set<string>();
  validateQuality(puzzle.quality, new Set(cluesById.keys()), provenanceSourceIds, crossing, issues);
  if (isRecord(puzzle.quality) && puzzle.quality.verdict === 'accept') {
    if (!provenanceValid) addIssue(issues, 'acceptance-provenance', 'Accept is forbidden when clue/source provenance is incomplete or invalid.', 'quality.verdict');
    if (isRecord(puzzle.provenance) && Array.isArray(puzzle.provenance.sources) && puzzle.provenance.sources.some((source) => isRecord(source) && source.contentClass !== 'public')) addIssue(issues, 'synthetic-acceptance', 'Synthetic-source puzzles cannot receive an accept verdict.', 'quality.verdict');
  }
  if (!validateExactShape(puzzle.integrity, ['algorithm', 'canonicalization', 'value'], 'integrity', issues) || puzzle.integrity.algorithm !== 'sha256' || puzzle.integrity.canonicalization !== PUZZLE_DOCUMENT_V2_CANONICALIZATION || typeof puzzle.integrity.value !== 'string' || !INTEGRITY_PATTERN.test(puzzle.integrity.value)) {
    addIssue(issues, 'integrity-shape', 'Integrity must contain the supported SHA-256 algorithm, canonicalization, and digest.', 'integrity');
  } else {
    try {
      const expected = await computePuzzleDocumentV2Digest(puzzle);
      if (puzzle.integrity.value !== expected) addIssue(issues, 'integrity-mismatch', 'Puzzle content does not match its canonical SHA-256 digest.', 'integrity.value');
    } catch (error) {
      addIssue(issues, 'integrity-computation', error instanceof Error ? error.message : 'Digest computation failed.', 'integrity');
    }
  }
  return { valid: issues.length === 0, issues };
}

export async function assertValidPuzzleDocumentV2(value: unknown): Promise<void> {
  const result = await validatePuzzleDocumentV2(value);
  if (!result.valid) {
    const first = result.issues[0];
    throw new Error(first ? `Invalid PuzzleDocumentV2 (${first.code}${first.path ? ` at ${first.path}` : ''}): ${first.message}` : 'Invalid PuzzleDocumentV2');
  }
}
