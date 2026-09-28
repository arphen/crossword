import { validatePuzzleDocumentV2 } from '@crossword/domain';

export const FUTURE_PUZZLE_V2_PUBLICATION_RECEIPT_VERSION =
  'puzzle-v2-publication-receipt-v1';

const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/;
const ISO_TIMESTAMP_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|([+-])(\d{2}):(\d{2}))$/;

export class PuzzleV2AdapterError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'PuzzleV2AdapterError';
    this.code = code;
  }
}

function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasExactKeys(value, keys) {
  return (
    isRecord(value) &&
    Object.keys(value).length === keys.length &&
    keys.every(key => Object.hasOwn(value, key))
  );
}

function isIsoTimestamp(value) {
  if (typeof value !== 'string') return false;
  const match = ISO_TIMESTAMP_PATTERN.exec(value);
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

  const calendarDate = new Date(0);
  calendarDate.setUTCFullYear(year, month - 1, day);
  calendarDate.setUTCHours(0, 0, 0, 0);
  return calendarDate.getUTCFullYear() === year &&
    calendarDate.getUTCMonth() === month - 1 &&
    calendarDate.getUTCDate() === day &&
    Number.isFinite(Date.parse(value));
}

/** @returns {never} */
function reject(code, message) {
  throw new PuzzleV2AdapterError(code, message);
}

/**
 * @param {import('@crossword/domain').PuzzleDocumentV2} puzzle
 * @param {string} candidateDigest
 */
/**
 * Internal projection primitive. The caller must first pass the full V2
 * validator and publication gates. Exported only for direct unit coverage;
 * it is not re-exported as a product API and does not authorize gameplay.
 * @internal
 * @param {import('@crossword/domain').PuzzleDocumentV2} puzzle
 * @param {string} candidateDigest
 */
export function projectValidatedPuzzleDocumentV2(puzzle, candidateDigest) {
  const cellsById = new Map(puzzle.cells.map(cell => [cell.id, cell]));
  const cellsByPosition = new Map(
    puzzle.cells.map(cell => [`${cell.row}:${cell.column}`, cell]),
  );
  const cluesByEntryId = new Map(puzzle.clues.map(clue => [clue.entryId, clue]));
  const crossword = [];
  const idMappings = [];

  const orderedEntries = [...puzzle.entries].sort(
    (left, right) =>
      left.number - right.number || left.direction.localeCompare(right.direction),
  );

  for (const entry of orderedEntries) {
    const firstCell = cellsById.get(entry.cellIds[0]);
    const clue = cluesByEntryId.get(entry.id);
    // The strict domain validator guarantees these references and geometry.
    // Keep these guards so a future validator regression fails closed here too.
    if (!firstCell || !clue || entry.answer.length !== entry.cellIds.length) {
      reject('invalid-puzzle-geometry', 'Puzzle entries do not map to valid solver geometry.');
    }
    const solverEntryId = `${entry.direction}-${entry.number}`;

    crossword.push({
      clue_number: entry.number,
      clue_text: clue.text,
      direction: entry.direction,
      start_x: firstCell.column,
      start_y: firstCell.row,
      characters: [...entry.answer].map(letters => ({ letters })),
      solver_entry_id: solverEntryId,
      v2_entry_id: entry.id,
      clue_variant_id: clue.clueVariantId,
    });
    idMappings.push({
      solverEntryId,
      v2EntryId: entry.id,
      clueVariantId: clue.clueVariantId,
    });
  }

  const grid = Array.from({ length: puzzle.height }, (_, row) =>
    Array.from({ length: puzzle.width }, (_, column) => {
      const cell = cellsByPosition.get(`${row}:${column}`);
      if (!cell) {
        reject('invalid-puzzle-geometry', 'Puzzle grid is missing a validated cell coordinate.');
      }
      return cell.block ? null : '';
    }),
  );

  return {
    puzzleId: puzzle.id,
    candidateDigest,
    grid,
    crossword,
    idMappings,
  };
}

/**
 * Convert an already-published V2 host envelope to the existing solver view
 * model. This is deliberately not a route or session operation.
 *
 * The receipt and digest checks establish strict envelope shape and document
 * integrity only; they do not authenticate a host publisher. The future host
 * route must be the authority that proves a record was published.
 *
 * @param {unknown} envelope
 */
export async function adaptPublishedPuzzleV2Envelope(envelope) {
  if (!hasExactKeys(envelope, ['status', 'candidateDigest', 'puzzle', 'publicationReceipt'])) {
    reject('invalid-envelope', 'Published PuzzleDocumentV2 envelope has an invalid shape.');
  }
  const payload = /** @type {Record<string, unknown>} */ (envelope);
  if (payload.status !== 'published') {
    reject('not-published', 'Only a published PuzzleDocumentV2 can be adapted for solving.');
  }
  const candidateDigest = payload.candidateDigest;
  if (typeof candidateDigest !== 'string' || !DIGEST_PATTERN.test(candidateDigest)) {
    reject('invalid-candidate-digest', 'Published puzzle candidate digest is malformed.');
  }

  const receiptValue = payload.publicationReceipt;
  if (!hasExactKeys(receiptValue, ['version', 'candidateDigest', 'publishedAt', 'reviewerId'])) {
    reject('invalid-publication-receipt', 'Published puzzle receipt is malformed.');
  }
  const receipt = /** @type {Record<string, unknown>} */ (receiptValue);
  if (
      receipt.version !== FUTURE_PUZZLE_V2_PUBLICATION_RECEIPT_VERSION ||
      typeof receipt.candidateDigest !== 'string' ||
      !DIGEST_PATTERN.test(receipt.candidateDigest) ||
      !isIsoTimestamp(receipt.publishedAt) ||
      typeof receipt.reviewerId !== 'string' ||
      receipt.reviewerId.trim().length === 0) {
    reject('invalid-publication-receipt', 'Published puzzle receipt is malformed.');
  }
  if (receipt.candidateDigest !== candidateDigest) {
    reject('publication-receipt-mismatch', 'Publication receipt does not bind this candidate digest.');
  }

  const puzzleValue = payload.puzzle;
  const validation = await validatePuzzleDocumentV2(puzzleValue);
  if (!validation.valid) {
    reject('invalid-puzzle-document', 'PuzzleDocumentV2 failed strict schema or integrity validation.');
  }
  const puzzle = /** @type {import('@crossword/domain').PuzzleDocumentV2} */ (puzzleValue);
  if (puzzle.integrity.value !== candidateDigest) {
    reject('candidate-digest-mismatch', 'Envelope digest does not match the PuzzleDocumentV2 integrity digest.');
  }
  if (puzzle.receipt.profileProjection !== undefined) {
    reject('private-generation-receipt', 'A published puzzle must not expose its private profile projection.');
  }
  if (puzzle.quality.verdict !== 'accept') {
    reject('puzzle-not-accepted', 'Review and rejected candidates are not playable puzzles.');
  }

  return projectValidatedPuzzleDocumentV2(puzzle, candidateDigest);
}
