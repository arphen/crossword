import {
  describeLanguageToken,
  LANGUAGE_INPUT_PACK_VERSION,
  resolveLanguagePack,
} from './languageInput';

/**
 * Future-only token manifest.
 *
 * PuzzleDocumentV2 deliberately remains a one-ASCII-letter publication
 * contract. This sidecar is the smaller private-solver capability needed for
 * a language/rebus cell: each geometric cell has a display grapheme and an
 * explicit sequence of canonical ASCII fill units. The legacy solver consumes
 * the fill token; the metadata remains attached for a token-aware renderer.
 */
export const FUTURE_TOKEN_MANIFEST_VERSION = 'future-token-manifest-v1';
export const FUTURE_TOKEN_POLICY_VERSION = 'language-token-policy-v1';
export const FUTURE_TOKEN_CELL_POLICY = 'explicit-display-fill-v1';
export const FUTURE_TOKEN_FILL_POLICY = 'single-ascii-letter-v1';
/**
 * Producer contract for adapting an already-filled private answer into a
 * token-aware cell.  This is intentionally separate from the manifest: the
 * producer receipt says how a display grapheme was selected, while the
 * manifest remains the sealed geometry/fill contract consumed by the solver.
 */
export const FUTURE_TOKEN_PRODUCER_VERSION = 'future-token-producer-v1';

const DIGEST_PATTERN = /^[a-f0-9]{64}$/i;
const ROOT_KEYS = [
  'schemaVersion',
  'puzzleManifestDigest',
  'width',
  'height',
  'languagePolicy',
  'cells',
  'entries',
  'integrity',
];
const POLICY_KEYS = [
  'version',
  'packVersion',
  'language',
  'cellTokenPolicy',
  'fillUnitPolicy',
];
const CELL_KEYS = [
  'id',
  'row',
  'column',
  'displayToken',
  'fillToken',
  'displayUnits',
  'fillUnits',
  'rebus',
];
const ENTRY_KEYS = [
  'id',
  'number',
  'direction',
  'cellIds',
  'cellTokens',
  'answerDisplay',
  'answerFill',
];
const PRODUCER_HINT_KEYS = ['entryId', 'cellIndex', 'displayToken'];

function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function exactKeys(value, keys) {
  return (
    isRecord(value) &&
    Object.keys(value).length === keys.length &&
    keys.every((key) => Object.hasOwn(value, key))
  );
}

function nonEmptyString(value, max = 128) {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= max;
}

function issue(code, path, message) {
  return { code, path, message };
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (isRecord(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

async function digest(value, cryptoApi = globalThis.crypto) {
  if (!cryptoApi?.subtle) {
    throw new Error('Secure token-manifest hashing is unavailable in this browser');
  }
  const bytes = new TextEncoder().encode(stableJson(value));
  const result = await cryptoApi.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(result)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

function sourcePuzzleDigest(puzzle) {
  const value = puzzle?.puzzleManifest?.integrity?.value;
  return typeof value === 'string' && DIGEST_PATTERN.test(value) ? value.toLowerCase() : null;
}

function puzzleDimensions(puzzle) {
  const width = Number(puzzle?.metadata?.width);
  const height = Number(puzzle?.metadata?.height);
  return Number.isInteger(width) && width > 0 && width <= 21 &&
    Number.isInteger(height) && height > 0 && height <= 21
    ? { width, height }
    : null;
}

function cellId(row, column) {
  return `r${row}c${column}`;
}

function entryCells(entry) {
  return entry.characters.map((_character, index) => ({
    row: entry.direction === 'across' ? entry.start_y : entry.start_y + index,
    column: entry.direction === 'across' ? entry.start_x + index : entry.start_x,
  }));
}

function tokenForCharacter(character, language) {
  const raw = character?.letters;
  const result = describeLanguageToken(raw, { language });
  if (!result.accepted || !result.metadata) return null;
  return {
    displayToken: result.display,
    fillToken: result.fill,
    displayUnits: [...result.metadata.displayUnits],
    fillUnits: [...result.metadata.fillUnits],
    rebus: result.metadata.multiCharacter,
  };
}

function entryId(entry) {
  return `${entry.direction}-${entry.clue_number}`;
}

function tokenHintCoordinates(puzzle, hint, language) {
  if (
    !exactKeys(hint, PRODUCER_HINT_KEYS) ||
    !nonEmptyString(hint.entryId, 120) ||
    !Number.isInteger(hint.cellIndex) ||
    hint.cellIndex < 0 ||
    !nonEmptyString(hint.displayToken, 32)
  ) {
    throw new Error('Token producer hint shape is invalid');
  }
  const entry = puzzle.entries.find((candidate) => entryId(candidate) === hint.entryId);
  if (!entry || hint.cellIndex >= entry.characters.length) {
    throw new Error('Token producer hint does not identify an entry cell');
  }
  const coordinate = entryCells(entry)[hint.cellIndex];
  const described = describeLanguageToken(hint.displayToken, {
    language,
  });
  if (!described.accepted || !described.metadata) {
    throw new Error('Token producer hint uses an unsupported display token');
  }
  const existingFill = String(entry.characters[hint.cellIndex]?.letters || '').toUpperCase();
  if (existingFill !== described.fill) {
    throw new Error(
      `Token producer hint fill does not match ${hint.entryId}[${hint.cellIndex}]`,
    );
  }
  return {
    id: cellId(coordinate.row, coordinate.column),
    token: {
      displayToken: described.display,
      fillToken: described.fill,
      displayUnits: [...described.metadata.displayUnits],
      fillUnits: [...described.metadata.fillUnits],
      rebus: described.metadata.multiCharacter,
    },
  };
}

/**
 * Apply explicit language/rebus hints to a native ASCII answer grid.
 *
 * Native xfill remains ASCII-only.  A caller that has an independently
 * selected language task can point at the exact answer cell whose fill is
 * equivalent to a display grapheme (for example `STRASSE` cell 5 -> `ß`).
 * The fill must already match; this function never invents or replaces an
 * answer, changes geometry, or heuristically accent-strips arbitrary words.
 * Crossings receive the same display token by coordinate, so the result can
 * be sealed by the ordinary manifest validator.
 *
 * @param {any} puzzle
 * @param {{language?: string, tokenHints?: Array<{entryId: string, cellIndex: number, displayToken: string}>}} options
 */
export function createFutureTokenPuzzleDraft(puzzle, options = {}) {
  const language = options.language;
  if (!isRecord(puzzle) || !Array.isArray(puzzle.entries) || puzzle.entries.length === 0) {
    throw new Error('Token producer requires a solver puzzle with entries');
  }
  if (!resolveLanguagePack(language)) {
    throw new Error('Token producer requires a supported language pack');
  }
  if (!Array.isArray(options.tokenHints) || options.tokenHints.length === 0) {
    throw new Error('Token producer requires at least one explicit token hint');
  }
  const tokenByCell = new Map();
  for (const hint of options.tokenHints) {
    const resolved = tokenHintCoordinates(puzzle, hint, language);
    const prior = tokenByCell.get(resolved.id);
    if (prior && stableJson(prior) !== stableJson(resolved.token)) {
      throw new Error(`Token producer crossing mismatch at ${resolved.id}`);
    }
    tokenByCell.set(resolved.id, resolved.token);
  }
  const entries = puzzle.entries.map((entry) => ({
    ...entry,
    characters: entry.characters.map((character, index) => {
      const coordinate = entryCells(entry)[index];
      const token = tokenByCell.get(cellId(coordinate.row, coordinate.column));
      return token
        ? { ...character, letters: token.displayToken }
        : { ...character };
    }),
  }));
  return {
    ...puzzle,
    entries,
    tokenProducer: {
      version: FUTURE_TOKEN_PRODUCER_VERSION,
      language: resolveLanguagePack(language).code,
      hintCount: tokenByCell.size,
      status: 'explicit-fill-equivalence',
      uncertainty: 'semantic-content-unverified',
    },
  };
}

/**
 * Seal and adapt an explicit producer result for the existing future solver.
 * The returned crossword keeps canonical fill strings in the controller and
 * carries display metadata for the token-aware UI.
 */
export async function produceFutureTokenPuzzle(
  puzzle,
  options = {},
  cryptoApi = globalThis.crypto,
) {
  const draft = createFutureTokenPuzzleDraft(puzzle, options);
  const tokenManifest = await sealFutureTokenManifest(draft, options, cryptoApi);
  return adaptFutureTokenPuzzle({ ...draft, tokenManifest });
}

/**
 * Build an unsealed private token manifest from legacy solver entries.
 * `letters` may be a declared display token such as `ß`; no generic Unicode
 * folding is attempted because the language pack is the source of policy.
 */
/** @param {any} puzzle @param {{language?: string}} options */
export function createFutureTokenManifestDraft(puzzle, options = {}) {
  const { language } = options;
  const dimensions = puzzleDimensions(puzzle);
  const pack = resolveLanguagePack(language);
  const puzzleDigest = sourcePuzzleDigest(puzzle);
  if (!dimensions) throw new Error('Token manifest requires a bounded puzzle size');
  if (!pack) throw new Error('Token manifest requires a supported language pack');
  if (!puzzleDigest) throw new Error('Token manifest requires a bound puzzle manifest digest');
  if (!Array.isArray(puzzle?.entries) || puzzle.entries.length === 0) {
    throw new Error('Token manifest requires solver entries');
  }

  const cellMap = new Map();
  const entryDrafts = [];
  for (const entry of puzzle.entries) {
    if (
      !isRecord(entry) ||
      (entry.direction !== 'across' && entry.direction !== 'down') ||
      !Number.isInteger(entry.clue_number) ||
      !Array.isArray(entry.characters) ||
      entry.characters.length === 0
    ) throw new Error('Token manifest entry shape is invalid');
    const cells = entryCells(entry);
    const cellTokens = [];
    for (const [index, coordinate] of cells.entries()) {
      if (
        coordinate.row < 0 || coordinate.row >= dimensions.height ||
        coordinate.column < 0 || coordinate.column >= dimensions.width
      ) throw new Error('Token manifest entry leaves the puzzle bounds');
      const token = tokenForCharacter(entry.characters[index], pack.code);
      if (!token) throw new Error('Entry contains a token outside its language pack');
      const id = cellId(coordinate.row, coordinate.column);
      const prior = cellMap.get(id);
      if (prior && stableJson(prior) !== stableJson(token)) {
        throw new Error(`Crossing token mismatch at ${id}`);
      }
      cellMap.set(id, token);
      cellTokens.push(token.fillToken);
    }
    entryDrafts.push({
      id: `${entry.direction}-${entry.clue_number}`,
      number: entry.clue_number,
      direction: entry.direction,
      cellIds: cells.map(({ row, column }) => cellId(row, column)),
      cellTokens,
      answerDisplay: cells.map((_coordinate, index) => tokenForCharacter(entry.characters[index], pack.code).displayToken).join(''),
      answerFill: cellTokens.join(''),
    });
  }

  const cells = [...cellMap.entries()]
    .map(([id, token]) => {
      const match = /^r(\d+)c(\d+)$/.exec(id);
      return {
        id,
        row: Number(match[1]),
        column: Number(match[2]),
        ...token,
      };
    })
    .sort((left, right) => left.row - right.row || left.column - right.column);

  return {
    schemaVersion: FUTURE_TOKEN_MANIFEST_VERSION,
    puzzleManifestDigest: puzzleDigest,
    width: dimensions.width,
    height: dimensions.height,
    languagePolicy: {
      version: FUTURE_TOKEN_POLICY_VERSION,
      packVersion: LANGUAGE_INPUT_PACK_VERSION,
      language: pack.code,
      cellTokenPolicy: FUTURE_TOKEN_CELL_POLICY,
      fillUnitPolicy: FUTURE_TOKEN_FILL_POLICY,
    },
    cells,
    entries: entryDrafts,
  };
}

/** Seal the sidecar independently; the strict V2 publication digest is untouched. */
export async function sealFutureTokenManifest(puzzle, options = {}, cryptoApi = globalThis.crypto) {
  const draft = createFutureTokenManifestDraft(puzzle, options);
  return {
    ...draft,
    integrity: {
      algorithm: 'sha256',
      value: await digest(draft, cryptoApi),
    },
  };
}

function validateBase(value, path, issues) {
  if (!exactKeys(value, ROOT_KEYS)) {
    issues.push(issue('root-shape', path, 'Token manifest root keys are invalid'));
    return false;
  }
  if (value.schemaVersion !== FUTURE_TOKEN_MANIFEST_VERSION) {
    issues.push(issue('schema-version', `${path}.schemaVersion`, 'Unsupported token manifest version'));
  }
  if (!Number.isInteger(value.width) || value.width < 1 || value.width > 21 || !Number.isInteger(value.height) || value.height < 1 || value.height > 21) {
    issues.push(issue('dimensions', `${path}.width`, 'Token manifest dimensions must be bounded positive integers'));
  }
  if (!DIGEST_PATTERN.test(value.puzzleManifestDigest || '')) {
    issues.push(issue('puzzle-binding', `${path}.puzzleManifestDigest`, 'Token manifest must bind a legacy puzzle digest'));
  }
  const policy = value.languagePolicy;
  if (!exactKeys(policy, POLICY_KEYS) || !resolveLanguagePack(policy.language) || policy.version !== FUTURE_TOKEN_POLICY_VERSION || policy.packVersion !== LANGUAGE_INPUT_PACK_VERSION || policy.cellTokenPolicy !== FUTURE_TOKEN_CELL_POLICY || policy.fillUnitPolicy !== FUTURE_TOKEN_FILL_POLICY) {
    issues.push(issue('language-policy', `${path}.languagePolicy`, 'Token language policy is unsupported or incomplete'));
  }
  const integrity = value.integrity;
  if (!exactKeys(integrity, ['algorithm', 'value']) || integrity.algorithm !== 'sha256' || !DIGEST_PATTERN.test(integrity.value || '')) {
    issues.push(issue('integrity', `${path}.integrity`, 'Token manifest integrity is malformed'));
  }
  return true;
}

/** Structural validation is synchronous so storage restore can fail closed. */
export function validateFutureTokenManifest(value, puzzle = null) {
  const issues = [];
  if (!validateBase(value, 'tokenManifest', issues)) return { valid: false, issues };
  const cells = Array.isArray(value.cells) ? value.cells : [];
  const cellMap = new Map();
  for (const [index, cell] of cells.entries()) {
    const path = `tokenManifest.cells[${index}]`;
    if (!exactKeys(cell, CELL_KEYS)) {
      issues.push(issue('cell-shape', path, 'Token cell keys are invalid'));
      continue;
    }
    if (!nonEmptyString(cell.id, 80) || !Number.isInteger(cell.row) || !Number.isInteger(cell.column) || cell.row < 0 || cell.row >= value.height || cell.column < 0 || cell.column >= value.width || cell.id !== cellId(cell.row, cell.column) || cellMap.has(cell.id)) {
      issues.push(issue('cell-identity', path, 'Token cell identity or coordinates are invalid'));
    }
    // eslint-disable-next-line no-control-regex -- reject C0/control characters in display tokens
    if (!nonEmptyString(cell.displayToken, 32) || /[\u0000-\u0020\u007f]/u.test(cell.displayToken)) {
      issues.push(issue('display-token', `${path}.displayToken`, 'Display token contains unsupported whitespace or controls'));
    }
    if (!nonEmptyString(cell.fillToken, 32) || !Array.isArray(cell.displayUnits) || !Array.isArray(cell.fillUnits) || cell.fillToken !== cell.fillUnits.join('') || !cell.fillUnits.every((unit) => typeof unit === 'string' && /^[A-Z]$/.test(unit)) || cell.displayToken !== cell.displayUnits.join('') || !cell.displayUnits.every((unit) => typeof unit === 'string' && unit.length > 0) || typeof cell.rebus !== 'boolean' || cell.rebus !== (cell.fillUnits.length > 1)) {
      issues.push(issue('token-units', path, 'Display and fill units do not describe an explicit token'));
    }
    cellMap.set(cell.id, cell);
  }

  const entries = Array.isArray(value.entries) ? value.entries : [];
  const entryIds = new Set();
  for (const [index, entry] of entries.entries()) {
    const path = `tokenManifest.entries[${index}]`;
    if (!exactKeys(entry, ENTRY_KEYS)) {
      issues.push(issue('entry-shape', path, 'Token entry keys are invalid'));
      continue;
    }
    const expectedDisplay = Array.isArray(entry.cellIds)
      ? entry.cellIds.map((id) => cellMap.get(id)?.displayToken || '').join('')
      : '';
    if (!nonEmptyString(entry.id, 120) || entryIds.has(entry.id) || !Number.isInteger(entry.number) || entry.number < 1 || !['across', 'down'].includes(entry.direction) || !Array.isArray(entry.cellIds) || !Array.isArray(entry.cellTokens) || entry.cellIds.length === 0 || entry.cellIds.length !== entry.cellTokens.length || entry.cellIds.some((id) => !cellMap.has(id)) || entry.cellTokens.some((token, tokenIndex) => token !== cellMap.get(entry.cellIds[tokenIndex])?.fillToken) || typeof entry.answerDisplay !== 'string' || entry.answerDisplay !== expectedDisplay || typeof entry.answerFill !== 'string' || entry.answerFill !== entry.cellTokens.join('')) {
      issues.push(issue('entry-link', path, 'Token entry cells or answer reconstruction are invalid'));
    }
    entryIds.add(entry.id);
  }
  if (entries.length === 0) issues.push(issue('entries-empty', 'tokenManifest.entries', 'Token manifest must contain entries'));

  if (puzzle) {
    const dimensions = puzzleDimensions(puzzle);
    if (!dimensions || dimensions.width !== value.width || dimensions.height !== value.height) {
      issues.push(issue('puzzle-dimensions', 'tokenManifest', 'Token manifest dimensions do not match the solver puzzle'));
    }
    const digestValue = sourcePuzzleDigest(puzzle);
    if (!digestValue || digestValue !== value.puzzleManifestDigest) {
      issues.push(issue('puzzle-digest-mismatch', 'tokenManifest.puzzleManifestDigest', 'Token manifest is bound to another puzzle'));
    }
    const expectedIds = new Set();
    for (const entry of puzzle.entries || []) {
      const id = `${entry.direction}-${entry.clue_number}`;
      const tokenEntry = entries.find((candidate) => candidate.id === id);
      const coordinates = entryCells(entry).map(({ row, column }) => cellId(row, column));
      coordinates.forEach((coordinate) => expectedIds.add(coordinate));
      if (!tokenEntry || stableJson(tokenEntry.cellIds) !== stableJson(coordinates)) {
        issues.push(issue('puzzle-entry-mismatch', `tokenManifest.entries.${id}`, 'Token entry geometry does not match the solver puzzle'));
        continue;
      }
      for (const [index, character] of entry.characters.entries()) {
        const token = cellMap.get(coordinates[index]);
        const letters = String(character?.letters || '').toUpperCase();
        if (!token || (letters !== token.fillToken && letters !== token.displayToken)) {
          issues.push(issue('puzzle-token-mismatch', `tokenManifest.entries.${id}`, 'Solver character is outside the declared display/fill token'));
        }
      }
    }
    if (expectedIds.size !== cellMap.size || [...expectedIds].some((id) => !cellMap.has(id))) {
      issues.push(issue('puzzle-cell-coverage', 'tokenManifest.cells', 'Token cells do not exactly cover solver entry geometry'));
    }
  }
  return { valid: issues.length === 0, issues };
}

export class FutureTokenManifestError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'FutureTokenManifestError';
    this.code = code;
  }
}

/**
 * Adapt a validated sidecar into the existing future solver model. The
 * controller still stores one string per geometric cell; for a multi-token
 * cell that string is the declared fill token (for example `SS`).
 */
export function adaptFutureTokenPuzzle(puzzle) {
  const manifest = puzzle?.tokenManifest;
  if (manifest === undefined || manifest === null) return puzzle;
  const validation = validateFutureTokenManifest(manifest, puzzle);
  if (!validation.valid) {
    const first = validation.issues[0];
    throw new FutureTokenManifestError(first?.code || 'invalid-token-manifest', first?.message || 'Invalid future token manifest');
  }
  const cells = new Map(manifest.cells.map((cell) => [cell.id, cell]));
  const entries = puzzle.entries.map((entry) => ({
    ...entry,
    characters: entry.characters.map((character, index) => {
      const coordinate = entryCells(entry)[index];
      const token = cells.get(cellId(coordinate.row, coordinate.column));
      return {
        ...character,
        letters: token.fillToken,
        tokenMetadata: {
          version: FUTURE_TOKEN_MANIFEST_VERSION,
          language: manifest.languagePolicy.language,
          displayToken: token.displayToken,
          fillToken: token.fillToken,
          displayUnits: [...token.displayUnits],
          fillUnits: [...token.fillUnits],
          rebus: token.rebus,
        },
      };
    }),
  }));
  return { ...puzzle, entries, tokenManifest: manifest };
}

export async function verifyFutureTokenManifestIntegrity(value, cryptoApi = globalThis.crypto) {
  const { integrity, ...draft } = value || {};
  if (!integrity || integrity.algorithm !== 'sha256') return false;
  return integrity.value.toLowerCase() === (await digest(draft, cryptoApi)).toLowerCase();
}
