import { createFutureJournalStore } from './journalStore';

const JOURNAL_VERSION = 2;
const FLUSH_DELAY_MS = 700;
const RETRY_DELAY_MS = 5000;
const MAX_HOST_EVENTS = 200;
const MAX_HOST_BODY_BYTES = 240 * 1024;

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

export async function sha256(value, cryptoApi = globalThis.crypto) {
  if (!cryptoApi?.subtle)
    throw new Error('Secure puzzle hashing is unavailable in this browser');
  const bytes = new TextEncoder().encode(stableJson(value));
  const digest = await cryptoApi.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

function randomUuid(cryptoApi = globalThis.crypto) {
  if (cryptoApi?.randomUUID) return cryptoApi.randomUUID();
  if (!cryptoApi?.getRandomValues)
    throw new Error('Secure session identifiers are unavailable');
  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function randomCapability(cryptoApi = globalThis.crypto) {
  if (!cryptoApi?.getRandomValues)
    throw new Error('Secure session storage is unavailable');
  return [...cryptoApi.getRandomValues(new Uint8Array(32))]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

function entryCells(entry) {
  return entry.characters.map((character, index) => ({
    cellId:
      entry.direction === 'across'
        ? `r${entry.start_y}c${entry.start_x + index}`
        : `r${entry.start_y + index}c${entry.start_x}`,
    token: String(character.letters || '').toLocaleUpperCase('en-US'),
  }));
}

function supportedManifest(app, legacyEntries) {
  const manifest = app.currentPuzzleManifest;
  const digest =
    manifest?.integrity?.algorithm === 'sha256' &&
    typeof manifest.integrity.value === 'string' &&
    /^[a-f0-9]{64}$/i.test(manifest.integrity.value)
      ? manifest.integrity.value
      : null;
  if (
    !digest ||
    manifest.schemaVersion !== 1 ||
    !Array.isArray(manifest.cells) ||
    !Array.isArray(manifest.entries)
  )
    return null;
  if (
    manifest.width !== (app.grid?.[0]?.length || 0) ||
    manifest.height !== (app.grid?.length || 0) ||
    manifest.cells.length !== manifest.width * manifest.height
  )
    return null;

  const cellIdByGeometry = new Map();
  const geometryByCellId = new Map();
  const cellIdsByGeometry = new Set();
  for (const cell of manifest.cells) {
    if (
      !cell ||
      typeof cell.id !== 'string' ||
      !cell.id ||
      !Number.isInteger(cell.row) ||
      !Number.isInteger(cell.column) ||
      typeof cell.block !== 'boolean'
    )
      return null;
    const geometryId = `r${cell.row}c${cell.column}`;
    if (cellIdsByGeometry.has(geometryId)) return null;
    cellIdsByGeometry.add(geometryId);
    if (cell.block) {
      if (app.grid?.[cell.row]?.[cell.column] !== null) return null;
      continue;
    }
    if (
      app.grid?.[cell.row]?.[cell.column] === null ||
      typeof app.grid?.[cell.row]?.[cell.column] === 'undefined'
    )
      return null;
    if (cellIdByGeometry.has(geometryId) || geometryByCellId.has(cell.id))
      return null;
    cellIdByGeometry.set(geometryId, cell.id);
    geometryByCellId.set(cell.id, [cell.row, cell.column]);
  }
  const openCellCount = (app.grid || []).reduce(
    (count, row) =>
      count +
      row.filter((value) => value !== null && typeof value !== 'undefined')
        .length,
    0,
  );
  if (cellIdByGeometry.size !== openCellCount) return null;

  const entriesByLegacyId = {};
  const mappedManifestIds = new Set();
  for (const legacy of legacyEntries) {
    const candidate = manifest.entries.find(
      (entry) =>
        entry.direction === legacy.direction && entry.number === legacy.number,
    );
    if (
      !candidate ||
      typeof candidate.id !== 'string' ||
      !candidate.id ||
      !Array.isArray(candidate.cellIds) ||
      typeof candidate.answer !== 'string'
    )
      return null;
    const canonicalCells = legacy.cells.map((cell) =>
      cellIdByGeometry.get(cell.cellId),
    );
    const answerTokens = Array.isArray(candidate.answerTokens)
      ? candidate.answerTokens
      : Array.from(candidate.answer.normalize('NFC'));
    if (
      canonicalCells.some((cellId) => !cellId) ||
      candidate.cellIds.length !== canonicalCells.length ||
      candidate.cellIds.some(
        (cellId, index) => cellId !== canonicalCells[index],
      ) ||
      answerTokens.length !== canonicalCells.length ||
      answerTokens.some(
        (token) => typeof token !== 'string' || !/^[A-Z]{1,8}$/.test(token),
      ) ||
      mappedManifestIds.has(candidate.id)
    )
      return null;
    mappedManifestIds.add(candidate.id);
    entriesByLegacyId[legacy.id] = { id: candidate.id, answerTokens };
  }
  if (mappedManifestIds.size !== manifest.entries.length) return null;
  return { digest, cellIdByGeometry, geometryByCellId, entriesByLegacyId };
}

/**
 * Stable, answer-bearing local descriptor used only to hash an edition.
 * @returns {{edition: object, cells: Array<object>, entries: Array<object>, puzzleHash?: string, syncSupported?: boolean, cellIdByGeometry?: Map<string, string>, geometryByCellId?: Map<string, [number, number]>}}
 */
export function describeLegacyPuzzle(app) {
  const metadata = app.currentPuzzleMetadata || {};
  const legacyEntries = (app.crossword || [])
    .map((entry) => ({
      id: `${entry.direction}-${entry.clue_number}`,
      direction: entry.direction,
      number: Number(entry.clue_number),
      clue: String(entry.clue_text || ''),
      cells: entryCells(entry),
    }))
    .sort(
      (left, right) =>
        left.number - right.number ||
        left.direction.localeCompare(right.direction),
    );
  const manifest = supportedManifest(app, legacyEntries);
  const cells = [];
  const legacyTopology = [];
  for (const [row, values] of (app.grid || []).entries()) {
    for (const [column, value] of values.entries()) {
      if (value !== null) {
        const geometryId = `r${row}c${column}`;
        legacyTopology.push(geometryId);
        cells.push({
          cellId: manifest?.cellIdByGeometry.get(geometryId) || geometryId,
          token: value ? String(value) : null,
          origin: 'unknown',
        });
      }
    }
  }
  const edition = {
    source: 'legacy-import',
    date: String(metadata.date || ''),
    width: app.grid?.[0]?.length || 0,
    height: app.grid?.length || 0,
    topology: legacyTopology,
    entries: legacyEntries,
  };
  if (!manifest) return { edition, cells, entries: legacyEntries };
  const entries = legacyEntries.map((entry) => ({
    ...entry,
    id: manifest.entriesByLegacyId[entry.id].id,
    legacyId: entry.id,
    cells: entry.cells.map((cell) => ({
      ...cell,
      cellId: manifest.cellIdByGeometry.get(cell.cellId),
    })),
    answerTokens: manifest.entriesByLegacyId[entry.id].answerTokens,
  }));
  return {
    edition,
    cells,
    entries,
    puzzleHash: manifest.digest,
    syncSupported: true,
    cellIdByGeometry: manifest.cellIdByGeometry,
    geometryByCellId: manifest.geometryByCellId,
  };
}

function activeEntryId(app) {
  if (!app.activeClueNumber || !app.activeDirection) return null;
  return `${app.activeDirection}-${app.activeClueNumber}`;
}

function httpStatus(error) {
  return error &&
    typeof error === 'object' &&
    'status' in error &&
    typeof error.status === 'number'
    ? error.status
    : undefined;
}

function byteLength(value) {
  return new TextEncoder().encode(JSON.stringify(value)).byteLength;
}

function valuesByCell(app) {
  const result = new Map();
  for (let row = 0; row < (app.grid || []).length; row++) {
    for (let column = 0; column < (app.grid[row] || []).length; column++) {
      if (app.grid[row][column] !== null) {
        result.set(
          `r${row}c${column}`,
          app.grid[row][column] ? String(app.grid[row][column]) : null,
        );
      }
    }
  }
  return result;
}

function cellPosition(cellId) {
  const match = /^r(\d+)c(\d+)$/.exec(cellId);
  return match ? [Number(match[1]), Number(match[2])] : null;
}

function appPuzzleIdentity(app) {
  if (!app) return null;
  const descriptor = describeLegacyPuzzle(app);
  return stableJson({
    edition: descriptor.edition,
    puzzleHash: descriptor.puzzleHash || null,
  });
}

function eventCellChanges(event) {
  if (event.type === 'cell-written')
    return [
      {
        cellId: event.cellId,
        token: event.afterToken,
        source: event.activeEntryId,
        known: event.source !== 'unknown',
      },
    ];
  if (event.type === 'cell-cleared')
    return [{ cellId: event.cellId, token: null, source: null, known: false }];
  if (event.type === 'batch-entered')
    return event.edits.map((edit) => ({
      cellId: edit.cellId,
      token: edit.afterToken,
      source: event.activeEntryId,
      known: event.source !== 'unknown',
    }));
  if (event.type === 'answer-revealed')
    return event.cells.map((cell) => ({
      cellId: cell.cellId,
      token: cell.token,
      source: null,
      known: false,
      revealed: true,
    }));
  return [];
}

export class FutureSessionRecorder {
  /** @param {{profileId:string,puzzle:{edition:object,cells:Array<object>,entries:Array<object>,puzzleHash?:string,syncSupported?:boolean,cellIdByGeometry?:Map<string,string>,geometryByCellId?:Map<string,[number,number]>},repository?:ReturnType<typeof createFutureJournalStore>,fetchImpl?:typeof fetch,cryptoApi?:Crypto,now?:()=>Date,performanceApi?:Performance,onStatus?:(state:string)=>void}} options */
  constructor({
    profileId,
    puzzle,
    repository = createFutureJournalStore(),
    fetchImpl = globalThis.fetch?.bind(globalThis),
    cryptoApi = globalThis.crypto,
    now = () => new Date(),
    performanceApi = globalThis.performance,
    onStatus = () => {},
  }) {
    this.profileId = profileId;
    this.puzzle = puzzle;
    this.puzzleIdentity = stableJson({
      edition: puzzle.edition,
      puzzleHash: puzzle.puzzleHash || null,
    });
    this.syncSupported =
      puzzle.syncSupported === true &&
      /^[a-f0-9]{64}$/i.test(puzzle.puzzleHash || '');
    this.repository = repository;
    this.fetchImpl = fetchImpl;
    this.cryptoApi = cryptoApi;
    this.now = now;
    this.performanceApi = performanceApi;
    this.onStatus = onStatus;
    this.session = null;
    this.ready = false;
    this.startPromise = null;
    this.startFailed = false;
    this.generation = 0;
    this.pendingEvents = [];
    this.segmentId = randomUuid(cryptoApi);
    this.segmentStart = performanceApi?.now?.() ?? 0;
    this.lastEntryId = null;
    this.lastFocusReason = null;
    this.lastWriteSourceByCell = new Map();
    this.revealedCells = new Set();
    this.flushTimer = null;
    this.flushChain = Promise.resolve();
    this.eventChain = Promise.resolve();
    this.ending = false;
    this.finishPromise = null;
    this.destroyed = false;
  }

  canonicalEntryId(entryId) {
    return (
      this.puzzle.entries.find(
        (entry) => entry.legacyId === entryId || entry.id === entryId,
      )?.id || entryId
    );
  }

  canonicalCellId(geometryId) {
    return this.puzzle.cellIdByGeometry?.get(geometryId) || geometryId;
  }

  start(app = undefined) {
    if (this.destroyed) return Promise.resolve(this);
    if (!this.startPromise) {
      this.startPromise = this.initialize(
        app,
        this.generation,
        appPuzzleIdentity(app),
      );
    }
    return this.startPromise;
  }

  isCurrentStart(generation) {
    return !this.destroyed && this.generation === generation;
  }

  async initialize(app, generation, identity) {
    try {
      // Unsupported legacy descriptors may still be keyed locally, but that
      // local hash is never sent to the host as if it identified a manifest.
      const puzzleHash = this.syncSupported
        ? this.puzzle.puzzleHash
        : await sha256(this.puzzle.edition, this.cryptoApi);
      if (!this.isCurrentStart(generation)) return this;
      const records = (await this.repository.list(this.profileId)).filter(
        (item) =>
          item.schemaVersion === JOURNAL_VERSION &&
          item.puzzleHash === puzzleHash,
      );
      if (!this.isCurrentStart(generation)) return this;
      const active = records.filter((item) => item.status === 'active');
      const unfinishedUploads = records.filter(
        (item) =>
          item.status === 'finished' &&
          item.acknowledgedSeq < item.events.length,
      );
      const candidates = [...active, ...unfinishedUploads].sort((left, right) =>
        String(right.updatedAt || '').localeCompare(
          String(left.updatedAt || ''),
        ),
      );
      this.session = candidates[0] || {
        schemaVersion: JOURNAL_VERSION,
        sessionId: randomUuid(this.cryptoApi),
        profileId: this.profileId,
        puzzleHash,
        initialGrid: this.puzzle.cells,
        writerToken: randomCapability(this.cryptoApi),
        events: [],
        acknowledgedSeq: 0,
        status: 'active',
        createdAt: this.now().toISOString(),
        updatedAt: this.now().toISOString(),
      };
      Object.assign(this.session, {
        syncStatus: this.syncSupported
          ? 'manifest-backed'
          : 'unsupported-local',
      });
      this.fresh = this.session.events.length === 0;
      this.rebuildProvenance();
      this.startupTokens = this.sessionGrid();
      // A puzzle may change while IndexedDB is opening. Keep the old session,
      // but never restore its grid over the replacement puzzle.
      const restoreIntoApp =
        app &&
        identity === this.puzzleIdentity &&
        appPuzzleIdentity(app) === identity;
      if (!this.fresh && restoreIntoApp) this.restoreGrid(app);
      await this.repository.save(this.session);
      if (!this.isCurrentStart(generation)) return this;
      if (this.fresh) {
        await this.writeEvent({ type: 'session-started', reason: 'fresh' });
      } else if (this.session.status === 'active') {
        // This is the last host-acknowledged sequence, not the longer local
        // outbox sequence. Offline events before this one may still be pending.
        await this.writeEvent({
          type: 'session-resumed',
          reason: 'reload',
          snapshotSeq: this.session.acknowledgedSeq,
        });
      }
      if (!this.isCurrentStart(generation)) return this;

      // Keep the gate closed while draining; events from the UI append behind
      // older queued actions until the queue is empty.
      while (this.pendingEvents.length && this.isCurrentStart(generation)) {
        const pending = this.pendingEvents.shift();
        try {
          const payload = this.applyPendingEvent(
            pending.payload,
            app,
            restoreIntoApp,
          );
          const event = await this.writeEvent(payload);
          pending.resolve(event);
          if (pending.payload.type === 'session-finished' && this.finishPromise)
            await this.finishPromise;
        } catch {
          pending.resolve(null);
          this.onStatus('storage-error');
        }
      }
      if (!this.isCurrentStart(generation)) return this;
      this.ready = true;
      if (!this.syncSupported) this.onStatus('unsupported');
      else if (!this.fetchImpl) this.onStatus('offline');
      else this.onStatus(this.session.acknowledgedSeq ? 'syncing' : 'local');
      if (this.syncSupported && this.fetchImpl) this.scheduleFlush(0);
      return this;
    } catch (error) {
      if (this.isCurrentStart(generation)) {
        this.startFailed = true;
        this.onStatus('storage-error');
        this.pendingEvents
          .splice(0)
          .forEach((pending) => pending.resolve(null));
      }
      throw error;
    }
  }

  rebuildProvenance() {
    this.lastWriteSourceByCell.clear();
    this.revealedCells.clear();
    for (const event of this.session.events) {
      for (const change of eventCellChanges(event)) {
        if (change.revealed) {
          this.lastWriteSourceByCell.delete(change.cellId);
          this.revealedCells.add(change.cellId);
        } else {
          this.revealedCells.delete(change.cellId);
          const sourceEntry = this.puzzle.entries.find(
            (entry) => entry.id === change.source,
          );
          if (
            change.known &&
            sourceEntry?.cells.some((cell) => cell.cellId === change.cellId)
          ) {
            this.lastWriteSourceByCell.set(change.cellId, change.source);
          } else {
            this.lastWriteSourceByCell.delete(change.cellId);
          }
        }
      }
    }
  }

  sessionGrid() {
    /** @type {Map<string, string | null>} */
    const tokens = new Map();
    for (const cell of this.session.initialGrid)
      tokens.set(cell.cellId, cell.token);
    for (const event of this.session.events) {
      for (const change of eventCellChanges(event))
        tokens.set(change.cellId, change.token);
    }
    return tokens;
  }

  restoreGrid(app) {
    if (!app?.grid) return;
    const tokens = this.sessionGrid();
    this.startupTokens = new Map(tokens);
    for (const [cellId, token] of tokens) {
      const position =
        this.puzzle.geometryByCellId?.get(cellId) || cellPosition(cellId);
      if (!position) continue;
      const [row, column] = position;
      if (
        app.grid[row] &&
        app.grid[row][column] !== null &&
        typeof app.grid[row][column] !== 'undefined'
      ) {
        app.grid[row][column] = token || '';
      }
    }
    this.restoreCompletedWords(app);
  }

  updateAppCell(app, cellId, token, enabled) {
    if (!enabled || !app?.grid) return;
    const position =
      this.puzzle.geometryByCellId?.get(cellId) || cellPosition(cellId);
    if (!position) return;
    const [row, column] = position;
    if (
      app.grid[row] &&
      app.grid[row][column] !== null &&
      typeof app.grid[row][column] !== 'undefined'
    ) {
      app.grid[row][column] = token || '';
    }
  }

  answerToken(entry, cellId) {
    const index = entry.cells.findIndex((cell) => cell.cellId === cellId);
    if (index < 0) return null;
    return entry.answerTokens?.[index] ?? entry.cells[index].token ?? null;
  }

  correctForEntry(entry, cellId, token) {
    const answer = this.answerToken(entry, cellId);
    return (
      token !== null &&
      answer !== null &&
      token.normalize('NFC').toLocaleUpperCase('en-US') ===
        answer.normalize('NFC').toLocaleUpperCase('en-US')
    );
  }

  canonicalRevealToken(cellId, token, app) {
    if (token === null || token === undefined || token === '') return token;
    const normalized = String(token).normalize('NFC');
    const position =
      this.puzzle.geometryByCellId?.get(cellId) || cellPosition(cellId);
    if (!position || !Array.isArray(app?.crossword)) return token;
    const [row, column] = position;
    const entry = app.crossword.find((candidate) =>
      candidate.characters?.some((_character, index) => {
        const cellRow =
          candidate.direction === 'across'
            ? candidate.start_y
            : candidate.start_y + index;
        const cellColumn =
          candidate.direction === 'across'
            ? candidate.start_x + index
            : candidate.start_x;
        return cellRow === row && cellColumn === column;
      }),
    );
    if (!entry) return token;
    const index = entry.characters.findIndex((_character, candidateIndex) => {
      const cellRow =
        entry.direction === 'across'
          ? entry.start_y
          : entry.start_y + candidateIndex;
      const cellColumn =
        entry.direction === 'across'
          ? entry.start_x + candidateIndex
          : entry.start_x;
      return cellRow === row && cellColumn === column;
    });
    if (index < 0) return token;
    const character = entry.characters[index];
    const display = character?.tokenMetadata?.displayToken;
    const answer = String(character?.letters || '');
    if (
      display &&
      normalized.toLocaleUpperCase('en-US') ===
        String(display).normalize('NFC').toLocaleUpperCase('en-US') &&
      answer
    ) {
      return answer;
    }
    return token;
  }

  applyPendingEvent(payload, app, updateApp) {
    const tokens = this.startupTokens || new Map();
    const currentToken = (cellId) =>
      tokens.has(cellId) ? tokens.get(cellId) : null;
    const setToken = (
      cellId,
      token,
      sourceEntryId = null,
      sourceKnown = false,
      revealed = false,
    ) => {
      tokens.set(cellId, token);
      this.revealedCells.delete(cellId);
      if (revealed) {
        this.lastWriteSourceByCell.delete(cellId);
        this.revealedCells.add(cellId);
      } else if (
        sourceKnown &&
        sourceEntryId &&
        this.puzzle.entries.some(
          (entry) =>
            entry.id === sourceEntryId &&
            entry.cells.some((cell) => cell.cellId === cellId),
        )
      ) {
        this.lastWriteSourceByCell.set(cellId, sourceEntryId);
      } else {
        this.lastWriteSourceByCell.delete(cellId);
      }
      this.updateAppCell(app, cellId, token, updateApp);
    };

    if (payload.type === 'cell-written') {
      const beforeToken = currentToken(payload.cellId);
      payload = { ...payload, beforeToken };
      setToken(
        payload.cellId,
        payload.afterToken,
        payload.activeEntryId,
        payload.source !== 'unknown',
      );
    } else if (payload.type === 'cell-cleared') {
      const beforeToken = currentToken(payload.cellId);
      payload = { ...payload, beforeToken };
      setToken(payload.cellId, null);
    } else if (payload.type === 'batch-entered') {
      const edits = payload.edits.map((edit) => {
        const beforeToken = currentToken(edit.cellId);
        setToken(
          edit.cellId,
          edit.afterToken,
          payload.activeEntryId,
          payload.source !== 'unknown',
        );
        return { ...edit, beforeToken };
      });
      payload = { ...payload, edits };
    } else if (payload.type === 'answer-revealed') {
      const cells = payload.cells.map((cell) => {
        const beforeToken = currentToken(cell.cellId);
        setToken(cell.cellId, cell.token, null, false, true);
        return { ...cell, beforeToken };
      });
      payload = { ...payload, cells };
    } else if (payload.type === 'entry-focused') {
      const entry = this.puzzle.entries.find(
        (candidate) => candidate.id === payload.entryId,
      );
      if (entry) {
        payload = {
          ...payload,
          visiblePattern: entry.cells.map((cell) => {
            const token = currentToken(cell.cellId);
            if (this.revealedCells.has(cell.cellId))
              return {
                cellId: cell.cellId,
                token,
                origin: 'reveal',
                sourceEntryId: null,
              };
            const written = this.lastWriteSourceByCell.get(cell.cellId);
            if (written === entry.id)
              return {
                cellId: cell.cellId,
                token,
                origin: 'player',
                sourceEntryId: written,
              };
            if (
              written &&
              this.puzzle.entries.some(
                (candidate) =>
                  candidate.id === written &&
                  candidate.cells.some(
                    (sourceCell) => sourceCell.cellId === cell.cellId,
                  ),
              )
            ) {
              return {
                cellId: cell.cellId,
                token,
                origin: 'crossing',
                sourceEntryId: written,
              };
            }
            return {
              cellId: cell.cellId,
              token,
              origin: 'unknown',
              sourceEntryId: null,
            };
          }),
        };
      }
    } else if (payload.type === 'check-result-shown') {
      const entry = payload.entryId
        ? this.puzzle.entries.find(
            (candidate) => candidate.id === payload.entryId,
          )
        : null;
      const results = payload.results.map((result) => {
        const token = currentToken(result.cellId);
        if (entry) {
          return {
            ...result,
            token,
            classification:
              token === null
                ? 'blank'
                : this.correctForEntry(entry, result.cellId, token)
                  ? 'correct'
                  : 'incorrect',
          };
        }
        const answerEntry = this.puzzle.entries.find(
          (candidate) => this.answerToken(candidate, result.cellId) !== null,
        );
        return {
          ...result,
          token,
          classification:
            token === null
              ? 'blank'
              : answerEntry &&
                  this.correctForEntry(answerEntry, result.cellId, token)
                ? 'correct'
                : 'incorrect',
        };
      });
      payload = { ...payload, results };
      if (app?.completedWords instanceof Set) {
        const checkedEntries = entry ? [entry] : this.puzzle.entries;
        for (const checkedEntry of checkedEntries) {
          const isCorrect = checkedEntry.cells.every((cell) =>
            results.some(
              (result) =>
                result.cellId === cell.cellId &&
                result.classification === 'correct',
            ),
          );
          const matchingClue = (app.crossword || []).find(
            (candidate) =>
              this.canonicalEntryId(
                `${candidate.direction}-${candidate.clue_number}`,
              ) === checkedEntry.id,
          );
          if (matchingClue) {
            if (isCorrect) app.completedWords.add(matchingClue.clue_text);
            else app.completedWords.delete(matchingClue.clue_text);
          }
        }
      }
    }
    this.startupTokens = tokens;
    return payload;
  }

  restoreCompletedWords(app) {
    if (!(app.completedWords instanceof Set)) return;
    app.completedWords.clear();
    const checked = new Map();
    for (const event of this.session.events) {
      if (event.type !== 'check-result-shown') continue;
      if (event.scope === 'entry' && event.entryId) {
        checked.set(
          event.entryId,
          event.results.every((result) => result.classification === 'correct'),
        );
      } else if (event.scope === 'puzzle') {
        const resultsByCell = new Map(
          event.results.map((result) => [result.cellId, result.classification]),
        );
        for (const entry of this.puzzle.entries) {
          if (
            entry.cells.every(
              (cell) => resultsByCell.get(cell.cellId) === 'correct',
            )
          )
            checked.set(entry.id, true);
          else checked.set(entry.id, false);
        }
      }
    }
    for (const entry of app.crossword || []) {
      const id = this.canonicalEntryId(
        `${entry.direction}-${entry.clue_number}`,
      );
      if (checked.get(id) === true) app.completedWords.add(entry.clue_text);
    }
  }

  emit(payload) {
    if (
      this.destroyed ||
      this.startFailed ||
      (this.ending && payload.type !== 'session-finished')
    )
      return Promise.resolve(null);
    if (!this.ready)
      return new Promise((resolve) =>
        this.pendingEvents.push({ payload, resolve }),
      );
    return this.writeEvent(payload);
  }

  async writeEvent(payload) {
    if (!this.session || this.session.status !== 'active') return null;
    const write = this.eventChain.then(async () => {
      const elapsedMs = Math.max(
        0,
        Math.floor(
          (this.performanceApi?.now?.() ?? this.segmentStart) -
            this.segmentStart,
        ),
      );
      const event = {
        schemaVersion: JOURNAL_VERSION,
        eventId: randomUuid(this.cryptoApi),
        sessionId: this.session.sessionId,
        profileId: this.profileId,
        segmentId: this.segmentId,
        seq: (this.session.events.at(-1)?.seq || 0) + 1,
        elapsedMs,
        recordedAt: this.now().toISOString(),
        puzzleHash: this.session.puzzleHash,
        ...payload,
      };
      this.session.events.push(event);
      this.session.updatedAt = this.now().toISOString();
      try {
        await this.repository.save(this.session);
      } catch (error) {
        this.session.events.pop();
        const writeConflict =
          typeof error === 'object' &&
          error !== null &&
          'code' in error &&
          error.code === 'write_conflict';
        this.onStatus(writeConflict ? 'conflict' : 'storage-error');
        throw error;
      }
      this.onStatus(
        !this.syncSupported
          ? 'unsupported'
          : this.fetchImpl
            ? 'local'
            : 'offline',
      );
      if (this.ready && this.syncSupported && this.fetchImpl)
        this.scheduleFlush();
      return event;
    });
    this.eventChain = write.catch(() => undefined);
    return write;
  }

  focus(entry, app, reason = 'pointer') {
    const entryId = this.canonicalEntryId(
      `${entry.direction}-${entry.clue_number}`,
    );
    if (
      entryId === this.lastEntryId &&
      !(this.lastFocusReason === 'programmatic' && reason !== 'programmatic')
    )
      return;
    this.lastEntryId = entryId;
    this.lastFocusReason = reason;
    const values = valuesByCell(app);
    const visiblePattern = entryCells(entry).map(({ cellId: geometryId }) => {
      const cellId = this.canonicalCellId(geometryId);
      const token = values.get(geometryId) ?? null;
      if (this.revealedCells.has(cellId))
        return { cellId, token, origin: 'reveal', sourceEntryId: null };
      const written = this.lastWriteSourceByCell.get(cellId);
      if (written === entryId)
        return { cellId, token, origin: 'player', sourceEntryId: written };
      if (
        written &&
        this.puzzle.entries.some(
          (candidate) =>
            candidate.id === written &&
            candidate.cells.some((cell) => cell.cellId === cellId),
        ) &&
        entryCells(entry).some(
          (cell) => this.canonicalCellId(cell.cellId) === cellId,
        )
      ) {
        return { cellId, token, origin: 'crossing', sourceEntryId: written };
      }
      return { cellId, token, origin: 'unknown', sourceEntryId: null };
    });
    void this.emit({
      type: 'entry-focused',
      entryId,
      variantId: null,
      reason,
      visiblePattern,
    });
  }

  cellChanged(
    {
      row,
      column,
      beforeToken,
      afterToken,
      source,
      activeEntryId: sourceEntryId,
    },
    app,
  ) {
    const cellId = this.canonicalCellId(`r${row}c${column}`);
    const entryId = this.canonicalEntryId(
      sourceEntryId === undefined ? activeEntryId(app) : sourceEntryId,
    );
    this.lastEntryId = entryId;
    if (beforeToken === afterToken) return;
    // A fresh edit supersedes any earlier write or answer disclosure. Unknown
    // input remains unknown in replay; it must not be promoted to player origin.
    this.revealedCells.delete(cellId);
    const entry = this.puzzle.entries.find(
      (candidate) => candidate.id === entryId,
    );
    if (
      source !== 'unknown' &&
      entry?.cells.some((cell) => cell.cellId === cellId)
    ) {
      this.lastWriteSourceByCell.set(cellId, entryId);
    } else {
      this.lastWriteSourceByCell.delete(cellId);
    }
    if (source === 'paste') {
      void this.emit({
        type: 'batch-entered',
        activeEntryId: entryId,
        actionId: randomUuid(this.cryptoApi),
        source: 'paste',
        edits: [{ cellId, beforeToken: beforeToken || null, afterToken }],
      });
      return;
    }
    if (afterToken) {
      void this.emit({
        type: 'cell-written',
        cellId,
        beforeToken: beforeToken || null,
        afterToken,
        activeEntryId: entryId,
        actionId: randomUuid(this.cryptoApi),
        source: source || 'unknown',
      });
    } else if (beforeToken) {
      this.lastWriteSourceByCell.delete(cellId);
      void this.emit({
        type: 'cell-cleared',
        cellId,
        beforeToken,
        activeEntryId: entryId,
        actionId: randomUuid(this.cryptoApi),
        source: source || 'unknown',
      });
    }
  }

  checked(app) {
    const allResults = [];
    for (const entry of app.crossword || []) {
      const geometryEntryId = `${entry.direction}-${entry.clue_number}`;
      const id = this.canonicalEntryId(geometryEntryId);
      const descriptorEntry = this.puzzle.entries.find(
        (candidate) => candidate.id === id,
      );
      const cells = entryCells(entry);
      const answerTokens =
        descriptorEntry?.answerTokens || cells.map((cell) => cell.token);
      const results = cells.map(({ cellId: geometryId }, index) => {
        const cellId = this.canonicalCellId(geometryId);
        const row = Number(geometryId.match(/^r(\d+)/)?.[1]);
        const column = Number(geometryId.match(/c(\d+)$/)?.[1]);
        const current = app.grid[row]?.[column]
          ? String(app.grid[row][column])
          : null;
        const answer = answerTokens[index];
        const classification =
          current === null
            ? 'blank'
            : current.normalize('NFC').toLocaleUpperCase('en-US') ===
                answer?.normalize('NFC').toLocaleUpperCase('en-US')
              ? 'correct'
              : 'incorrect';
        const result = { cellId, token: current, classification };
        allResults.push(result);
        return result;
      });
      void this.emit({
        type: 'check-result-shown',
        scope: 'entry',
        entryId: id,
        results,
      });
    }
    const unique = [
      ...new Map(allResults.map((result) => [result.cellId, result])).values(),
    ];
    if (
      unique.length &&
      unique.every((item) => item.classification === 'correct')
    )
      void this.finish('complete');
  }

  revealed(before, after) {
    const cells = [];
    for (const [cellId, token] of after) {
      // Reveal-all discloses every answer, including letters the player had
      // already entered correctly. Record the disclosure itself so replay
      // cannot mistake those unchanged cells for unaided retrieval.
      if (token) {
        const prior = before.get(cellId) ?? null;
        const journalCellId = this.canonicalCellId(cellId);
        cells.push({
          cellId: journalCellId,
          beforeToken: prior,
          token: token.toLocaleUpperCase('en-US'),
        });
        this.revealedCells.add(journalCellId);
        this.lastWriteSourceByCell.delete(journalCellId);
      }
    }
    if (cells.length)
      void this.emit({
        type: 'answer-revealed',
        scope: 'puzzle',
        entryId: null,
        cells,
      });
    if (cells.length && [...after.values()].every(Boolean))
      void this.finish('complete');
  }

  revealCell({ row, column, beforeToken, token }, app) {
    if (!token || token === beforeToken) return;
    const cellId = this.canonicalCellId(`r${row}c${column}`);
    const canonicalToken = this.canonicalRevealToken(cellId, token, app);
    this.revealedCells.add(cellId);
    this.lastWriteSourceByCell.delete(cellId);
    const crossingEntries = this.puzzle.entries.filter((entry) =>
      entry.cells.some((cell) => cell.cellId === cellId),
    );
    const focusedEntryId = this.canonicalEntryId(activeEntryId(app));
    const entryId =
      crossingEntries.find((entry) => entry.id === focusedEntryId)?.id ||
      crossingEntries[0]?.id ||
      null;
    void this.emit({
      type: 'answer-revealed',
      scope: entryId ? 'cell' : 'puzzle',
      entryId,
      cells: [
        {
          cellId,
          beforeToken: beforeToken || null,
          token: String(canonicalToken).toLocaleUpperCase('en-US'),
        },
      ],
    });
  }

  /**
   * Record a prepared, non-answer hint without changing the board.  The host
   * validates the entry, tier, and affected cells against the frozen
   * manifest; the text itself stays in the immutable puzzle/variant bundle.
   */
  hintShown({ entryId, hintId, assistanceTier, affectedCellIds = [] }) {
    const canonicalId = this.canonicalEntryId(entryId);
    const canonicalCells = affectedCellIds.map((cellId) =>
      this.canonicalCellId(cellId),
    );
    void this.emit({
      type: 'hint-shown',
      entryId: canonicalId,
      hintId,
      assistanceTier,
      affectedCellIds: canonicalCells,
    });
  }

  async finish(reason) {
    if (
      this.destroyed ||
      (this.session && this.session.status !== 'active') ||
      this.ending
    )
      return this.finishPromise;
    this.ending = true;
    this.finishPromise = this.emit({ type: 'session-finished', reason }).then(
      async (event) => {
        if (!event || !this.session) return;
        this.session.status = 'finished';
        this.session.updatedAt = this.now().toISOString();
        await this.repository.save(this.session);
        if (this.ready && this.syncSupported && this.fetchImpl) {
          // Let a confirmed manual completion reach host replay before the
          // compatibility solver advances to another puzzle. Offline or slow
          // hosts remain non-blocking after a short best-effort window.
          let timeout;
          await Promise.race([
            this.flush(),
            new Promise((resolve) => {
              timeout = setTimeout(resolve, 4000);
            }),
          ]);
          clearTimeout(timeout);
        }
      },
    );
    return this.finishPromise;
  }

  visibilityChanged(visible) {
    void this.emit({
      type: 'visibility-changed',
      visibility: visible ? 'visible' : 'hidden',
    });
    void this.emit({
      type: visible ? 'resumed' : 'paused',
      reason: 'background',
    });
  }

  scheduleFlush(delay = FLUSH_DELAY_MS) {
    clearTimeout(this.flushTimer);
    if (!this.destroyed)
      this.flushTimer = setTimeout(() => this.flush(), delay);
  }

  flush() {
    this.flushChain = this.flushChain
      .then(() => this.flushNow())
      .catch(() => undefined);
    return this.flushChain;
  }

  async acknowledgeThrough(sessionId, sequence) {
    await this.repository.updateAcknowledgedSeq(sessionId, sequence);
    const current = /** @type {any} */ (this.session);
    if (!current || current.sessionId !== sessionId) return current;

    // The IndexedDB transaction may have read an older snapshot before a
    // concurrent event save. Merge only the monotonic acknowledgement and
    // retain the live event history instead of replacing `this.session`.
    current.acknowledgedSeq = Math.max(
      current.acknowledgedSeq,
      sequence,
    );
    return current;
  }

  async flushNow() {
    if (!this.session || this.destroyed || !this.ready) return;
    if (!this.syncSupported) {
      this.onStatus('unsupported');
      return;
    }
    if (!this.fetchImpl) {
      this.onStatus('offline');
      return;
    }
    this.onStatus('syncing');
    try {
      const startResponse = await this.fetchImpl('/api/future/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: this.session.sessionId,
          profileId: this.profileId,
          puzzleHash: this.session.puzzleHash,
          initialGrid: this.session.initialGrid,
          writerToken: this.session.writerToken,
        }),
      });
      const server = await startResponse.json();
      if (!startResponse.ok)
        throw Object.assign(new Error(server.error || 'Session sync failed'), {
          status: startResponse.status,
          retryable: server.retryable === true,
        });
      if (server.acceptedSeq > this.session.events.length)
        throw Object.assign(
          new Error('The server journal is ahead of this device'),
          { status: 409 },
        );
      if (server.acceptedSeq < this.session.acknowledgedSeq)
        throw Object.assign(
          new Error('The local acknowledgement is ahead of the server journal'),
          { status: 409 },
      );
      if (server.acceptedSeq > this.session.acknowledgedSeq) {
        await this.acknowledgeThrough(
          this.session.sessionId,
          server.acceptedSeq,
        );
      }
      while (this.session.acknowledgedSeq < this.session.events.length) {
        const pending = this.session.events.filter(
          (event) => event.seq > this.session.acknowledgedSeq,
        );
        const batch = [];
        for (const event of pending) {
          const candidate = [...batch, event];
          const body = {
            expectedSeq: this.session.acknowledgedSeq,
            writerToken: this.session.writerToken,
            events: candidate,
          };
          if (
            candidate.length > MAX_HOST_EVENTS ||
            byteLength(body) > MAX_HOST_BODY_BYTES
          )
            break;
          batch.push(event);
        }
        if (!batch.length)
          throw Object.assign(
            new Error(
              'A single event is larger than the local journal host limit',
            ),
            { status: 413 },
          );
        const body = {
          expectedSeq: this.session.acknowledgedSeq,
          writerToken: this.session.writerToken,
          events: batch,
        };
        const response = await this.fetchImpl(
          `/api/future/sessions/${this.session.sessionId}/events`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          },
        );
        const result = await response.json();
        if (!response.ok)
          throw Object.assign(new Error(result.error || 'Event sync failed'), {
            status: response.status,
            retryable: result.retryable === true,
          });
        const returnedIds = new Set([
          ...(result.acceptedEventIds || []),
          ...(result.duplicateEventIds || []),
        ]);
        if (
          batch.some((event) => !returnedIds.has(event.eventId)) ||
          result.acceptedSeq < batch.at(-1).seq ||
          result.acceptedSeq > this.session.events.length
        ) {
          throw Object.assign(
            new Error(
              'The host acknowledgement does not match this event batch',
            ),
            { status: 409 },
          );
        }
        await this.acknowledgeThrough(
          this.session.sessionId,
          result.acceptedSeq,
        );
      }
      this.onStatus(this.session.status === 'finished' ? 'finished' : 'saved');
      if (this.session.acknowledgedSeq < this.session.events.length)
        this.scheduleFlush(RETRY_DELAY_MS);
    } catch (error) {
      const status = httpStatus(error);
      const retryable =
        typeof error === 'object' &&
        error !== null &&
        'retryable' in error &&
        error.retryable === true;
      this.onStatus(
        retryable ? 'syncing' : status === 409 ? 'conflict' : status ? 'rejected' : 'offline',
      );
      if (retryable || !status || status >= 500)
        this.scheduleFlush(RETRY_DELAY_MS);
    }
  }

  dispose() {
    this.destroyed = true;
    this.generation += 1;
    this.ready = false;
    this.pendingEvents.splice(0).forEach((pending) => pending.resolve(null));
    clearTimeout(this.flushTimer);
    void this.repository.close?.().catch(() => undefined);
  }
}

export function cellIdAt(row, column) {
  return `r${row}c${column}`;
}
