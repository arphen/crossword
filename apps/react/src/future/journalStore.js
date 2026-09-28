const DATABASE_NAME = 'crossword';
const DATABASE_VERSION = 3;
const EVENT_STORE_NAME = 'solve-events';
const RECORD_KIND = 'future-session-journal-v1';
const RECORD_ID_PREFIX = 'future-session:';
export const FUTURE_JOURNAL_MAX_BYTES = 1024 * 1024;
export const FUTURE_JOURNAL_MAX_EVENTS = 10_000;

/** @typedef {{schemaVersion:2,sessionId:string,profileId?:string|null,puzzleHash:string,initialGrid:Array<unknown>,writerToken:string,events:Array<Record<string, unknown>>,acknowledgedSeq:number,status:string,createdAt?:string,updatedAt?:string}} FutureJournalRecord */

export class FutureJournalStorageError extends Error {
  /** @param {string} code @param {string} message @param {unknown} [cause] */
  constructor(code, message, cause) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = 'FutureJournalStorageError';
    this.code = code;
  }
}

/** @template T @param {IDBRequest<T>} request @returns {Promise<T>} */
function requestResult(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('IndexedDB request failed'));
  });
}

/** @param {IDBTransaction} transaction */
function transactionResult(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed'));
    transaction.onabort = () => reject(transaction.error ?? new Error('IndexedDB transaction aborted'));
  });
}

/** @param {unknown} value @returns {value is Record<string, unknown>} */
function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

/** @param {unknown} value */
function validateRecord(value) {
  if (!isRecord(value)) throw new FutureJournalStorageError('invalid_record', 'Future journal must be an object.');
  const record = /** @type {Partial<FutureJournalRecord>} */ (value);
  if (record.schemaVersion !== 2) throw new FutureJournalStorageError('invalid_record', 'Future journal schemaVersion must be 2.');
  if (typeof record.sessionId !== 'string' || record.sessionId.length < 1 || record.sessionId.length > 128) {
    throw new FutureJournalStorageError('invalid_record', 'Future journal sessionId must contain 1–128 characters.');
  }
  if (record.profileId !== undefined && record.profileId !== null && (typeof record.profileId !== 'string' || record.profileId.length > 128)) {
    throw new FutureJournalStorageError('invalid_record', 'Future journal profileId must be null or at most 128 characters.');
  }
  if (typeof record.puzzleHash !== 'string' || !/^[a-f0-9]{64}$/i.test(record.puzzleHash)) {
    throw new FutureJournalStorageError('invalid_record', 'Future journal puzzleHash must be a 64-character hexadecimal digest.');
  }
  if (!Array.isArray(record.initialGrid) || record.initialGrid.length > 2_000) {
    throw new FutureJournalStorageError('invalid_record', 'Future journal initialGrid must be an array of at most 2,000 cells.');
  }
  if (typeof record.writerToken !== 'string' || record.writerToken.length < 16 || record.writerToken.length > 512) {
    throw new FutureJournalStorageError('invalid_record', 'Future journal writerToken must contain 16–512 characters.');
  }
  if (!Array.isArray(record.events) || record.events.length > FUTURE_JOURNAL_MAX_EVENTS || !record.events.every(isRecord)) {
    throw new FutureJournalStorageError('invalid_record', `Future journal events must be an array of at most ${FUTURE_JOURNAL_MAX_EVENTS} objects.`);
  }
  if (!Number.isSafeInteger(record.acknowledgedSeq) || record.acknowledgedSeq < 0 || record.acknowledgedSeq > record.events.length) {
    throw new FutureJournalStorageError('invalid_record', 'Future journal acknowledgedSeq must be a whole sequence within the event list.');
  }
  if (typeof record.status !== 'string' || record.status.length < 1 || record.status.length > 32) {
    throw new FutureJournalStorageError('invalid_record', 'Future journal status must contain 1–32 characters.');
  }
  for (const key of ['createdAt', 'updatedAt']) {
    const value = record[key];
    if (value !== undefined && (typeof value !== 'string' || value.length > 64)) {
      throw new FutureJournalStorageError('invalid_record', `Future journal ${key} must be a timestamp string of at most 64 characters.`);
    }
  }

  let serialized;
  try {
    serialized = JSON.stringify(record);
  } catch (error) {
    throw new FutureJournalStorageError('invalid_record', 'Future journal must contain only JSON-serializable data.', error);
  }
  if (typeof serialized !== 'string') {
    throw new FutureJournalStorageError('invalid_record', 'Future journal must contain only JSON-serializable data.');
  }
  const byteLength = new TextEncoder().encode(serialized).byteLength;
  if (byteLength > FUTURE_JOURNAL_MAX_BYTES) {
    throw new FutureJournalStorageError('record_too_large', `Future journal exceeds the ${FUTURE_JOURNAL_MAX_BYTES}-byte storage limit.`);
  }
  try {
    return /** @type {FutureJournalRecord} */ (JSON.parse(serialized));
  } catch (error) {
    throw new FutureJournalStorageError('invalid_record', 'Future journal could not be copied safely.', error);
  }
}

/** @param {IDBFactory | null | undefined} factory @param {string} databaseName */
function openDatabase(factory, databaseName) {
  if (!factory) {
    return Promise.reject(new FutureJournalStorageError('unavailable', 'IndexedDB is unavailable; the solve journal was not saved.'));
  }

  return new Promise((resolve, reject) => {
    let request;
    try {
      request = factory.open(databaseName, DATABASE_VERSION);
    } catch (error) {
      reject(new FutureJournalStorageError('open_failed', 'Could not open the local solve journal.', error));
      return;
    }
    request.onupgradeneeded = () => {
      const database = request.result;
      // This is the existing v3 store. Add it only during an already-required
      // upgrade (including a new database); never request a schema bump later.
      if (!database.objectStoreNames.contains(EVENT_STORE_NAME)) {
        database.createObjectStore(EVENT_STORE_NAME, { keyPath: 'id' });
      }
    };
    request.onsuccess = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(EVENT_STORE_NAME)) {
        database.close();
        reject(new FutureJournalStorageError('missing_store', 'The crossword database v3 has no solve-events store.'));
        return;
      }
      database.onversionchange = () => database.close();
      resolve(database);
    };
    request.onerror = () => reject(new FutureJournalStorageError('open_failed', 'Could not open the local solve journal.', request.error));
    request.onblocked = () => reject(new FutureJournalStorageError('open_blocked', 'The local solve journal is waiting for another tab to close.'));
  });
}

/** @param {string} sessionId */
function recordId(sessionId) {
  return `${RECORD_ID_PREFIX}${sessionId}`;
}

/**
 * Stores one bounded, resumable /future solve journal in the existing v3
 * `solve-events` object store. Storage failures are surfaced to the caller;
 * this adapter never substitutes an in-memory store.
 *
 * @param {string} [databaseName]
 * @param {IDBFactory | null | undefined} [factory]
 */
export function createFutureJournalStore(
  databaseName = DATABASE_NAME,
  factory = typeof indexedDB === 'undefined' ? undefined : indexedDB
) {
  /** @type {Promise<IDBDatabase> | undefined} */
  let databasePromise;
  function getDatabase() {
    databasePromise ??= openDatabase(factory, databaseName);
    return databasePromise;
  }

  /** @param {unknown} row */
  function unpack(row) {
    if (!isRecord(row) || row.kind !== RECORD_KIND) return undefined;
    const { id: _id, kind: _kind, ...value } = row;
    return validateRecord(value);
  }

  return {
    /** @param {string} sessionId */
    async load(sessionId) {
      const database = await getDatabase();
      const transaction = database.transaction(EVENT_STORE_NAME, 'readonly');
      const complete = transactionResult(transaction);
      const row = await requestResult(transaction.objectStore(EVENT_STORE_NAME).get(recordId(sessionId)));
      await complete;
      return unpack(row);
    },

    /** @param {string} [profileId] */
    async list(profileId) {
      const database = await getDatabase();
      const transaction = database.transaction(EVENT_STORE_NAME, 'readonly');
      const complete = transactionResult(transaction);
      const rows = await requestResult(/** @type {IDBRequest<unknown[]>} */ (transaction.objectStore(EVENT_STORE_NAME).getAll()));
      await complete;
      return rows
        .filter((row) => isRecord(row) && row.kind === RECORD_KIND)
        .map(unpack)
        .filter((record) => record !== undefined && (profileId === undefined || record.profileId === profileId))
        .sort((left, right) => left.sessionId.localeCompare(right.sessionId));
    },

    /** Remove every locally cached solve journal owned by a profile. */
    async removeProfile(profileId) {
      if (typeof profileId !== 'string' || !profileId) return;
      const database = await getDatabase();
      const transaction = database.transaction(EVENT_STORE_NAME, 'readwrite');
      const complete = transactionResult(transaction);
      const store = transaction.objectStore(EVENT_STORE_NAME);
      const rows = await requestResult(store.getAll());
      for (const row of rows) {
        const record = unpack(row);
        if (record?.profileId === profileId) store.delete(row.id);
      }
      await complete;
    },

    /** @param {FutureJournalRecord} value */
    async save(value) {
      const candidate = validateRecord(value);
      const id = recordId(candidate.sessionId);
      const database = await getDatabase();
      const transaction = database.transaction(EVENT_STORE_NAME, 'readwrite');
      const complete = transactionResult(transaction);
      const store = transaction.objectStore(EVENT_STORE_NAME);
      const read = store.get(id);
      let saved;
      /** @type {Error | DOMException | undefined} */
      let writeError;
      read.onsuccess = () => {
        const current = read.result;
        if (current !== undefined && (!isRecord(current) || current.kind !== RECORD_KIND)) {
          writeError = new FutureJournalStorageError('id_collision', 'The solve-events store already uses this future journal key.');
          transaction.abort();
          return;
        }
        let currentRecord;
        try {
          currentRecord = current === undefined ? undefined : unpack(current);
        } catch (error) {
          writeError = error instanceof Error ? error : new Error(String(error));
          transaction.abort();
          return;
        }
        if (currentRecord && (
          candidate.puzzleHash !== currentRecord.puzzleHash
          || candidate.profileId !== currentRecord.profileId
          || candidate.writerToken !== currentRecord.writerToken
          || canonicalJson(candidate.initialGrid) !== canonicalJson(currentRecord.initialGrid)
          || candidate.events.length < currentRecord.events.length
          || currentRecord.events.some((event, index) => canonicalJson(candidate.events[index]) !== canonicalJson(event))
          || (currentRecord.status === 'finished' && candidate.status !== 'finished')
        )) {
          writeError = new FutureJournalStorageError('write_conflict', 'Another open crossword session has advanced this local journal. This edit was not added to its record.');
          transaction.abort();
          return;
        }
        const acknowledgedSeq = Math.max(candidate.acknowledgedSeq, currentRecord?.acknowledgedSeq ?? 0);
        if (acknowledgedSeq > candidate.events.length) {
          writeError = new FutureJournalStorageError('ack_out_of_range', 'The saved journal cannot contain fewer events than its acknowledged sequence.');
          transaction.abort();
          return;
        }
        saved = { ...candidate, acknowledgedSeq };
        try {
          store.put({ id, kind: RECORD_KIND, ...saved });
        } catch (error) {
          writeError = new FutureJournalStorageError('write_failed', 'Could not write the local solve journal.', error);
          transaction.abort();
        }
      };
      read.onerror = () => {
        writeError = read.error ?? new Error('Could not read the existing solve journal.');
        transaction.abort();
      };
      try {
        await complete;
      } catch (error) {
        if (writeError instanceof FutureJournalStorageError) throw writeError;
        throw new FutureJournalStorageError('transaction_failed', 'Could not save the local solve journal.', writeError ?? error);
      }
      return saved;
    },

    /**
     * Atomically raises the server-acknowledged sequence. Out-of-order older
     * acknowledgements are harmless and leave the stored high-water mark intact.
     * @param {string} sessionId
     * @param {number} sequence
     */
    async updateAcknowledgedSeq(sessionId, sequence) {
      if (!Number.isSafeInteger(sequence) || sequence < 0) {
        throw new FutureJournalStorageError('ack_invalid', 'Acknowledged sequence must be a non-negative whole number.');
      }
      const database = await getDatabase();
      const transaction = database.transaction(EVENT_STORE_NAME, 'readwrite');
      const complete = transactionResult(transaction);
      const store = transaction.objectStore(EVENT_STORE_NAME);
      const read = store.get(recordId(sessionId));
      let updated;
      /** @type {Error | DOMException | undefined} */
      let writeError;
      read.onsuccess = () => {
        let current;
        try {
          current = unpack(read.result);
        } catch (error) {
          writeError = error instanceof Error ? error : new Error(String(error));
          transaction.abort();
          return;
        }
        if (!current) {
          writeError = new FutureJournalStorageError('session_not_found', `No future solve journal exists for session ${sessionId}.`);
          transaction.abort();
          return;
        }
        if (sequence > current.events.length) {
          writeError = new FutureJournalStorageError('ack_out_of_range', 'Acknowledged sequence cannot exceed the number of stored events.');
          transaction.abort();
          return;
        }
        updated = { ...current, acknowledgedSeq: Math.max(current.acknowledgedSeq, sequence) };
        try {
          store.put({ id: recordId(sessionId), kind: RECORD_KIND, ...updated });
        } catch (error) {
          writeError = new FutureJournalStorageError('write_failed', 'Could not update the solve journal acknowledgement.', error);
          transaction.abort();
        }
      };
      read.onerror = () => {
        writeError = read.error ?? new Error('Could not read the solve journal acknowledgement.');
        transaction.abort();
      };
      try {
        await complete;
      } catch (error) {
        if (writeError instanceof FutureJournalStorageError) throw writeError;
        throw new FutureJournalStorageError('transaction_failed', 'Could not update the solve journal acknowledgement.', writeError ?? error);
      }
      return updated;
    },

    async close() {
      if (databasePromise) (await databasePromise).close();
    }
  };
}
