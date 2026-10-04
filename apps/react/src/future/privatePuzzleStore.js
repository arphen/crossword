import { adaptFutureTokenPuzzle, validateFutureTokenManifest } from './tokenManifest';

const STORAGE_PREFIX = 'crossword.future.private-puzzle.v1:';
export const PRIVATE_PUZZLE_STORAGE_PREFIX = STORAGE_PREFIX;
const HISTORY_SUFFIX = ':history';
export const PRIVATE_PUZZLE_HISTORY_SUFFIX = HISTORY_SUFFIX;
const LOCAL_SOURCE = 'local-ollama-xfill';
const REVIEWED_SAMPLE_SOURCE = 'reviewed-sample';
const MAX_RECORD_BYTES = 512 * 1024;
const MAX_HISTORY_RECORDS = 3;
const WEEKDAYS = new Set([
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
]);

function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function validRecord(value, profileId) {
  if (
    !isRecord(value) ||
    value.schemaVersion !== 1 ||
    value.profileId !== profileId ||
    !Number.isSafeInteger(value.seed) ||
    value.seed < 0 ||
    value.seed > 2_147_483_647 ||
    !WEEKDAYS.has(value.weekday) ||
    !isRecord(value.puzzle) ||
    !isRecord(value.puzzle.metadata) ||
    !Array.isArray(value.puzzle.entries) ||
    !isRecord(value.puzzle.puzzleManifest) ||
    value.puzzle.puzzleManifest.schemaVersion !== 1 ||
    value.puzzle.puzzleManifest.integrity?.algorithm !== 'sha256' ||
    !/^[a-f0-9]{64}$/i.test(value.puzzle.puzzleManifest.integrity?.value || '') ||
    ![LOCAL_SOURCE, REVIEWED_SAMPLE_SOURCE].includes(
      value.puzzle.provenance?.source,
    ) ||
    value.puzzle.provenance?.seed !== value.seed ||
    value.puzzle.provenance?.weekday !== value.weekday
  ) {
    return false;
  }
  if (
    value.puzzle.tokenManifest !== undefined &&
    !validateFutureTokenManifest(value.puzzle.tokenManifest, value.puzzle).valid
  ) {
    return false;
  }
  return true;
}

function recordTimestamp(record) {
  const value = record?.savedAt;
  const parsed = typeof value === 'string' ? Date.parse(value) : NaN;
  return Number.isFinite(parsed) ? parsed : 0;
}

function recordFor(profileId, puzzle) {
  return {
    schemaVersion: 1,
    profileId,
    seed: puzzle.provenance?.seed,
    weekday: puzzle.provenance?.weekday,
    savedAt: new Date().toISOString(),
    puzzle: compactPuzzleForStorage(puzzle),
  };
}

function boundedStrings(value, limit) {
  if (!Array.isArray(value)) return undefined;
  const strings = value.filter((item) => typeof item === 'string').slice(0, limit);
  return strings.length > 0 ? strings : [];
}

function compactGrounding(grounding) {
  if (!isRecord(grounding)) return undefined;
  const compact = {
    version: grounding.version,
    entryCount: grounding.entryCount,
    reviewedCount: grounding.reviewedCount,
    familyCounts: grounding.familyCounts,
    relationCounts: grounding.relationCounts,
    statusCounts: grounding.statusCounts,
    entries: Array.isArray(grounding.entries)
      ? grounding.entries.slice(0, 256).map((entry) => ({
          id: entry?.id,
          riskFlags: boundedStrings(entry?.riskFlags, 8) || [],
          semanticStatus: entry?.semanticStatus,
        }))
      : [],
  };
  return compact;
}

function compactClueQuality(quality) {
  if (!isRecord(quality)) return undefined;
  const compact = {
    checkedCount: quality.checkedCount,
    issueCount: quality.issueCount,
    fallbackCount: quality.fallbackCount,
    issueCounts: quality.issueCounts,
    diversity: quality.diversity,
    semanticChallenge: quality.semanticChallenge,
    fallbackSupport: quality.fallbackSupport,
    grounding: compactGrounding(quality.grounding),
  };
  return compact;
}

/**
 * Keep the exact board and the small provenance lanes needed after reload,
 * while dropping the per-clue model transcripts that can exceed browser
 * storage limits. The host session remains the authoritative full receipt.
 */
export function compactPuzzleForStorage(puzzle) {
  if (!isRecord(puzzle)) return puzzle;
  const provenance = isRecord(puzzle.provenance) ? puzzle.provenance : {};
  const storedProvenance = {};
  const scalarFields = [
    'source',
    'model',
    'seed',
    'weekday',
    'languageInterest',
    'generatedAt',
    'engine',
    'experimental',
    'sampleId',
    'version',
  ];
  for (const field of scalarFields) {
    if (provenance[field] !== undefined) storedProvenance[field] = provenance[field];
  }
  const boundedArrayFields = ['themeAnswers'];
  for (const field of boundedArrayFields) {
    if (provenance[field] !== undefined) {
      storedProvenance[field] = boundedStrings(provenance[field], 16) || [];
    }
  }
  const boundedObjectFields = [
    'languageLearning',
    'tokenConstruction',
    'personalizationReceipt',
    'playCalibration',
    'themeExposure',
    'themeProposal',
    'fillQuality',
    'crossingSupport',
    'clueDiversity',
    'clueGenerationBatches',
    'semanticClueChallenge',
    'weekdayRecipe',
    'reviewedCluePack',
  ];
  for (const field of boundedObjectFields) {
    if (isRecord(provenance[field])) storedProvenance[field] = provenance[field];
  }
  if (isRecord(provenance.clueQuality)) {
    const clueQuality = compactClueQuality(provenance.clueQuality);
    if (clueQuality) storedProvenance.clueQuality = clueQuality;
  }
  if (isRecord(provenance.constructionEvidence)) {
    const construction = provenance.constructionEvidence;
    storedProvenance.constructionEvidence = {
      version: construction.version,
      boardDigest: construction.boardDigest,
      status: construction.status,
      footholdSeedPlan: construction.footholdSeedPlan,
    };
  }
  return {
    metadata: puzzle.metadata,
    entries: puzzle.entries,
    puzzleManifest: puzzle.puzzleManifest,
    ...(puzzle.tokenManifest !== undefined
      ? { tokenManifest: puzzle.tokenManifest }
      : {}),
    provenance: storedProvenance,
  };
}

function historyKey(profileId) {
  return `${STORAGE_PREFIX}${profileId}${HISTORY_SUFFIX}`;
}

function writeCurrentRecord(profileId, record, storage) {
  storage.setItem(`${STORAGE_PREFIX}${profileId}`, JSON.stringify(record));
}

/** Save the exact local puzzle response so an active game survives a reload. */
export function savePrivatePuzzle(profileId, puzzle, storage = globalThis.localStorage) {
  if (
    typeof profileId !== 'string' ||
    !profileId ||
    !puzzle ||
    typeof storage?.setItem !== 'function'
  ) {
    return false;
  }
  const record = recordFor(profileId, puzzle);
  if (!validRecord(record, profileId)) return false;
  try {
    const serialized = JSON.stringify(record);
    if (new TextEncoder().encode(serialized).byteLength > MAX_RECORD_BYTES) {
      return false;
    }
    const priorCurrent = loadPrivatePuzzle(profileId, storage);
    writeCurrentRecord(profileId, record, storage);
    // Keep a tiny local shelf for recovery after the player makes another
    // puzzle. Failure here must not make the active puzzle appear unsaved.
    const prior = listPrivatePuzzles(profileId, storage);
    if (priorCurrent) prior.push(priorCurrent);
    const manifestId = record.puzzle.puzzleManifest?.id || record.puzzle.puzzleManifest?.integrity?.value;
    const seen = new Set([manifestId]);
    const history = [
      record,
      ...prior.filter((item) => {
        const itemId = item.puzzle.puzzleManifest?.id || item.puzzle.puzzleManifest?.integrity?.value;
        if (seen.has(itemId)) return false;
        seen.add(itemId);
        return true;
      }),
    ].slice(0, MAX_HISTORY_RECORDS);
    const historySerialized = JSON.stringify(history);
    if (new TextEncoder().encode(historySerialized).byteLength <= MAX_HISTORY_RECORDS * MAX_RECORD_BYTES) {
      try {
        storage.setItem(historyKey(profileId), historySerialized);
      } catch {
        // The current puzzle is already durable in the primary slot.
      }
    }
    return true;
  } catch {
    return false;
  }
}

/** Return the bounded, newest-first shelf of locally recoverable puzzles. */
export function listPrivatePuzzles(profileId, storage = globalThis.localStorage) {
  if (
    typeof profileId !== 'string' ||
    !profileId ||
    typeof storage?.getItem !== 'function'
  ) return [];
  try {
    const serialized = storage.getItem(historyKey(profileId));
    if (!serialized || new TextEncoder().encode(serialized).byteLength > MAX_HISTORY_RECORDS * MAX_RECORD_BYTES) return [];
    const value = JSON.parse(serialized);
    if (!Array.isArray(value)) return [];
    return value
      .filter((record) => validRecord(record, profileId))
      .sort((left, right) => recordTimestamp(right) - recordTimestamp(left))
      .slice(0, MAX_HISTORY_RECORDS);
  } catch {
    return [];
  }
}

/** Return the saved response only when its profile and manifest shape match. */
export function loadPrivatePuzzle(profileId, storage = globalThis.localStorage) {
  if (
    typeof profileId !== 'string' ||
    !profileId ||
    typeof storage?.getItem !== 'function'
  ) {
    return null;
  }
  try {
    const serialized = storage.getItem(`${STORAGE_PREFIX}${profileId}`);
    if (!serialized || new TextEncoder().encode(serialized).byteLength > MAX_RECORD_BYTES) {
      return null;
    }
    const record = JSON.parse(serialized);
    return validRecord(record, profileId) ? record : null;
  } catch {
    return null;
  }
}

/** Restore a validated private puzzle through the solver's regular init path. */
export function restorePrivatePuzzle(app, profileId, storage, requestedRecord = null) {
  const record = requestedRecord && validRecord(requestedRecord, profileId)
    ? requestedRecord
    : loadPrivatePuzzle(profileId, storage);
  let puzzle = record?.puzzle;
  try {
    puzzle = puzzle ? adaptFutureTokenPuzzle(puzzle) : puzzle;
  } catch {
    return false;
  }
  if (
    !puzzle ||
    typeof app?.isValidPuzzle !== 'function' ||
    !app.isValidPuzzle(puzzle)
  ) {
    return false;
  }
  app.selectedWeekday = record.weekday;
  app.lastLoadedWeekday = record.weekday;
  app.currentPuzzleMetadata = puzzle.metadata;
  app.currentPuzzleManifest = puzzle.puzzleManifest;
  app.currentPuzzleTokenManifest = puzzle.tokenManifest ?? null;
  app.currentPuzzleProvenance = puzzle.provenance;
  app.currentPuzzleRequestSeed = record.seed;
  app.crossword = puzzle.entries;
  if (requestedRecord && typeof storage?.setItem === 'function') {
    try {
      writeCurrentRecord(profileId, requestedRecord, storage);
    } catch {
      // Restoring a shelf item remains useful even if the primary slot is full.
    }
  }
  app.init();
  return true;
}
