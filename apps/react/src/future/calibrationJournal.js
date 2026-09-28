import { validateCalibrationSession } from '@crossword/domain';

const DATABASE_NAME = 'crossword-calibration';
const DATABASE_VERSION = 1;
const STORE_NAME = 'calibration-sessions';
const RECORD_KIND = 'calibration-session-journal-v1';

export class CalibrationJournalStorageError extends Error {
  /** @param {string} code @param {string} message @param {unknown} [cause] @param {CalibrationJournalRecord} [current] */
  constructor(code, message, cause, current) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = 'CalibrationJournalStorageError';
    this.code = code;
    if (current !== undefined) this.current = current;
  }
}

/** @typedef {{session: import('@crossword/domain').CalibrationSessionV1, revision:number, hostRevision:number, etag:string|null, syncStatus:'pending'|'saved'|'conflict'}} CalibrationJournalRecord */

/** @param {IDBRequest<T>} request @returns {Promise<T>} @template T */
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
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

/** @param {unknown} value @returns {CalibrationJournalRecord} */
function validateRecord(value) {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(',') !== 'etag,hostRevision,kind,revision,session,syncStatus' ||
    value.kind !== RECORD_KIND ||
    !Number.isSafeInteger(value.revision) ||
    Number(value.revision) < 1 ||
    !Number.isSafeInteger(value.hostRevision) ||
    Number(value.hostRevision) < 0 ||
    Number(value.hostRevision) > Number(value.revision) ||
    !(value.etag === null || (typeof value.etag === 'string' && value.etag.length <= 512)) ||
    !['pending', 'saved', 'conflict'].includes(String(value.syncStatus)) ||
    !validateCalibrationSession(value.session)
  ) {
    throw new CalibrationJournalStorageError(
      'invalid_record',
      'The local calibration journal is corrupt or has an unsupported shape.',
    );
  }
  return /** @type {CalibrationJournalRecord} */ ({
    session: clone(value.session),
    revision: Number(value.revision),
    hostRevision: Number(value.hostRevision),
    etag: /** @type {string|null} */ (value.etag),
    syncStatus: /** @type {'pending'|'saved'|'conflict'} */ (value.syncStatus),
  });
}

/** @param {unknown} value */
function clone(value) {
  let serialized;
  try {
    serialized = JSON.stringify(value);
  } catch (error) {
    throw new CalibrationJournalStorageError(
      'invalid_session',
      'Calibration session must contain only JSON-serializable data.',
      error,
    );
  }
  if (typeof serialized !== 'string') {
    throw new CalibrationJournalStorageError(
      'invalid_session',
      'Calibration session must contain only JSON-serializable data.',
    );
  }
  return JSON.parse(serialized);
}

/** @param {unknown} value */
function validateSession(value) {
  if (!validateCalibrationSession(value)) {
    throw new CalibrationJournalStorageError(
      'invalid_session',
      'Calibration session does not satisfy the shared calibration contract.',
    );
  }
  return /** @type {import('@crossword/domain').CalibrationSessionV1} */ (clone(value));
}

/** @param {IDBFactory | null | undefined} factory @param {string} databaseName */
function openDatabase(factory, databaseName) {
  if (!factory) {
    return Promise.reject(
      new CalibrationJournalStorageError(
        'unavailable',
        'IndexedDB is unavailable; calibration was not saved.',
      ),
    );
  }
  return new Promise((resolve, reject) => {
    let request;
    try {
      request = factory.open(databaseName, DATABASE_VERSION);
    } catch (error) {
      reject(
        new CalibrationJournalStorageError(
          'open_failed',
          'Could not open local calibration storage.',
          error,
        ),
      );
      return;
    }
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'calibrationId' });
      }
    };
    request.onsuccess = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.close();
        reject(
          new CalibrationJournalStorageError(
            'missing_store',
            'The local calibration database has no session store.',
          ),
        );
        return;
      }
      database.onversionchange = () => database.close();
      resolve(database);
    };
    request.onerror = () =>
      reject(
        new CalibrationJournalStorageError(
          'open_failed',
          'Could not open local calibration storage.',
          request.error,
        ),
      );
    request.onblocked = () =>
      reject(
        new CalibrationJournalStorageError(
          'open_blocked',
          'Local calibration storage is waiting for another tab to close.',
        ),
      );
  });
}

/** @param {import('@crossword/domain').CalibrationSessionV1} session @param {import('@crossword/domain').CalibrationSessionV1} prior */
function assertMonotonicSession(session, prior) {
  const immutableFields = [
    'schemaVersion',
    'calibrationId',
    'scope',
    'bankVersion',
    'selectorVersion',
    'seed',
    'presentationMode',
    'createdAt',
  ];
  if (
    immutableFields.some(
      (key) => canonicalJson(session[key]) !== canonicalJson(prior[key]),
    )
  ) {
    throw new CalibrationJournalStorageError(
      'write_conflict',
      'Calibration identity is immutable; this local edit was not saved.',
    );
  }
  if (
    session.observations.length < prior.observations.length ||
    session.actions.length < prior.actions.length ||
    prior.observations.some(
      (observation, index) =>
        canonicalJson(session.observations[index]) !== canonicalJson(observation),
    ) ||
    prior.actions.some(
      (action, index) => canonicalJson(session.actions[index]) !== canonicalJson(action),
    )
  ) {
    throw new CalibrationJournalStorageError(
      'write_conflict',
      'Calibration evidence is append-only; this branch conflicts with the saved journal.',
    );
  }
  if (
    Date.parse(session.updatedAt) < Date.parse(prior.updatedAt) ||
    (prior.status !== 'in-progress' &&
      canonicalJson(session) !== canonicalJson(prior))
  ) {
    throw new CalibrationJournalStorageError(
      'write_conflict',
      'Terminal calibration sessions are immutable and progress timestamps cannot move backwards.',
    );
  }
}

/**
 * Dedicated IndexedDB calibration storage. Writes commit before resolving and
 * never fall back to memory or perform network requests.
 *
 * @param {string} [databaseName]
 * @param {IDBFactory | null | undefined} [factory]
 */
export function createCalibrationJournalStore(
  databaseName = DATABASE_NAME,
  factory = typeof indexedDB === 'undefined' ? undefined : indexedDB,
) {
  /** @type {Promise<IDBDatabase> | undefined} */
  let databasePromise;
  const getDatabase = () => {
    databasePromise ??= openDatabase(factory, databaseName);
    return databasePromise;
  };

  /** @param {unknown} row */
  function unpack(row) {
    if (row === undefined) return undefined;
    if (!isRecord(row) || typeof row.calibrationId !== 'string') {
      throw new CalibrationJournalStorageError(
        'invalid_record',
        'The local calibration journal key is corrupt.',
      );
    }
    const { calibrationId, ...value } = row;
    const record = validateRecord(value);
    if (record.session.calibrationId !== calibrationId) {
      throw new CalibrationJournalStorageError(
        'invalid_record',
        'The local calibration journal key does not match its session.',
      );
    }
    return record;
  }

  /** @param {string} calibrationId */
  async function read(calibrationId) {
    const database = await getDatabase();
    const transaction = database.transaction(STORE_NAME, 'readonly');
    const complete = transactionResult(transaction);
    const row = await requestResult(
      transaction.objectStore(STORE_NAME).get(calibrationId),
    );
    await complete;
    return unpack(row);
  }

  return {
    /** @param {string} calibrationId */
    async load(calibrationId) {
      if (!calibrationId) {
        throw new CalibrationJournalStorageError(
          'invalid_id',
          'Calibration ID must be a non-empty string.',
        );
      }
      return (await read(calibrationId)) ?? null;
    },

    /** Remove every locally cached calibration journal owned by a profile. */
    async removeProfile(profileId) {
      if (typeof profileId !== 'string' || !profileId) return;
      const database = await getDatabase();
      const transaction = database.transaction(STORE_NAME, 'readwrite');
      const complete = transactionResult(transaction);
      const store = transaction.objectStore(STORE_NAME);
      const rows = await requestResult(store.getAll());
      for (const row of rows) {
        try {
          const record = unpack(row);
          if (record?.session?.scope?.kind === 'profile' && record.session.scope.profileId === profileId) {
            store.delete(row.calibrationId);
          }
        } catch {
          // A corrupt unrelated row should not prevent this profile's local
          // records from being removed; the host remains the canonical delete.
        }
      }
      await complete;
    },

    /**
     * Restore a host-owned snapshot only when this device has no record yet.
     * The server revision becomes the local CAS revision, so later writes keep
     * using the host ETag that was actually read.
     * @param {import('@crossword/domain').CalibrationSessionV1} input
     * @param {{etag:string, revision:number}} metadata
     */
    async restoreHost(input, metadata) {
      const session = validateSession(input);
      if (
        !metadata ||
        typeof metadata.etag !== 'string' ||
        metadata.etag.length > 512 ||
        !Number.isSafeInteger(metadata.revision) ||
        metadata.revision < 1
      ) {
        throw new CalibrationJournalStorageError(
          'invalid_sync_metadata',
          'A restored calibration requires its host ETag and positive revision.',
        );
      }
      const database = await getDatabase();
      const transaction = database.transaction(STORE_NAME, 'readwrite');
      const complete = transactionResult(transaction);
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(session.calibrationId);
      let restored;
      /** @type {Error|DOMException|undefined} */
      let writeError;
      request.onsuccess = () => {
        try {
          const current = unpack(request.result);
          if (current) {
            restored = current;
            return;
          }
          restored = {
            session,
            revision: metadata.revision,
            hostRevision: metadata.revision,
            etag: metadata.etag,
            syncStatus: 'saved',
          };
          store.put({
            calibrationId: session.calibrationId,
            kind: RECORD_KIND,
            ...restored,
          });
        } catch (error) {
          writeError = error instanceof Error ? error : new Error(String(error));
          transaction.abort();
        }
      };
      request.onerror = () => {
        writeError = request.error ?? new Error('Could not read local calibration progress.');
        transaction.abort();
      };
      try {
        await complete;
      } catch (error) {
        if (writeError instanceof CalibrationJournalStorageError) throw writeError;
        throw new CalibrationJournalStorageError(
          'transaction_failed',
          'Could not restore the host calibration locally.',
          writeError ?? error,
        );
      }
      return /** @type {CalibrationJournalRecord} */ (restored);
    },

    /**
     * Create with expectedRevision 0; every update must include the revision
     * returned by load/save. Conflicting branches are rejected with `.current`.
     * @param {import('@crossword/domain').CalibrationSessionV1} input
     * @param {{expectedRevision:number}} options
     */
    async save(input, options) {
      const session = validateSession(input);
      const expectedRevision = options?.expectedRevision;
      if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 0) {
        throw new CalibrationJournalStorageError(
          'revision_required',
          'Saving calibration requires the expected local revision (0 for a new session).',
        );
      }
      const database = await getDatabase();
      const transaction = database.transaction(STORE_NAME, 'readwrite');
      const complete = transactionResult(transaction);
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(session.calibrationId);
      let saved;
      /** @type {Error|DOMException|undefined} */
      let writeError;
      request.onsuccess = () => {
        let current;
        try {
          current = unpack(request.result);
          const currentRevision = current?.revision ?? 0;
          if (currentRevision !== expectedRevision) {
            writeError = new CalibrationJournalStorageError(
              'write_conflict',
              'Another tab or calibration branch has advanced local progress. This edit was not saved.',
              undefined,
              current,
            );
            transaction.abort();
            return;
          }
          if (current) assertMonotonicSession(session, current.session);
          const sessionChanged =
            !current || canonicalJson(session) !== canonicalJson(current.session);
          saved = {
            session,
            revision: currentRevision + (sessionChanged ? 1 : 0),
            hostRevision: current?.hostRevision ?? 0,
            etag: current?.etag ?? null,
            syncStatus:
              current?.syncStatus === 'conflict'
                ? 'conflict'
                : sessionChanged
                  ? 'pending'
                  : current?.syncStatus ?? 'pending',
          };
          try {
            store.put({
              calibrationId: session.calibrationId,
              kind: RECORD_KIND,
              ...saved,
            });
          } catch (error) {
            writeError = new CalibrationJournalStorageError(
              'write_failed',
              'Could not save local calibration progress.',
              error,
            );
            transaction.abort();
          }
        } catch (error) {
          writeError = error instanceof Error ? error : new Error(String(error));
          transaction.abort();
        }
      };
      request.onerror = () => {
        writeError = request.error ?? new Error('Could not read local calibration progress.');
        transaction.abort();
      };
      try {
        await complete;
      } catch (error) {
        if (writeError instanceof CalibrationJournalStorageError) throw writeError;
        throw new CalibrationJournalStorageError(
          'transaction_failed',
          'Could not commit local calibration progress.',
          writeError ?? error,
        );
      }
      return /** @type {CalibrationJournalRecord} */ (saved);
    },

    /**
     * Update host acknowledgement metadata without changing the local revision.
     * A late acknowledgement cannot mark newer local edits as fully saved.
     * @param {string} calibrationId
     * @param {{etag:string|null, expectedEtag:string|null, syncedRevision:number}} metadata
     */
    async markHostSynced(calibrationId, metadata) {
      if (
        !metadata ||
        !(metadata.etag === null || (typeof metadata.etag === 'string' && metadata.etag.length <= 512)) ||
        !(metadata.expectedEtag === null || (typeof metadata.expectedEtag === 'string' && metadata.expectedEtag.length <= 512)) ||
        !Number.isSafeInteger(metadata.syncedRevision) ||
        metadata.syncedRevision < 1
      ) {
        throw new CalibrationJournalStorageError(
          'invalid_sync_metadata',
          'Host sync metadata must include a bounded ETag and positive synced revision.',
        );
      }
      return updateRecord(calibrationId, (current) => {
        if (current.etag !== metadata.expectedEtag) return current;
        if (metadata.syncedRevision > current.revision) {
          throw new CalibrationJournalStorageError(
            'invalid_sync_metadata',
            'Host acknowledgement cannot exceed the current local revision.',
          );
        }
        if (metadata.syncedRevision < current.hostRevision) return current;
        return {
          ...current,
          etag: metadata.etag,
          hostRevision: metadata.syncedRevision,
          syncStatus:
            current.revision === metadata.syncedRevision ? 'saved' : 'pending',
        };
      });
    },

    /** @param {string} calibrationId @param {{etag:string|null,expectedEtag:string|null}} metadata */
    async markHostConflict(calibrationId, metadata) {
      if (
        !metadata ||
        !(metadata.etag === null || (typeof metadata.etag === 'string' && metadata.etag.length <= 512)) ||
        !(metadata.expectedEtag === null || (typeof metadata.expectedEtag === 'string' && metadata.expectedEtag.length <= 512))
      ) {
        throw new CalibrationJournalStorageError(
          'invalid_sync_metadata',
          'Host ETag must be null or at most 512 characters.',
        );
      }
      return updateRecord(calibrationId, (current) =>
        current.etag !== metadata.expectedEtag
          ? current
          : { ...current, etag: metadata.etag, syncStatus: 'conflict' },
      );
    },

    async close() {
      if (databasePromise) (await databasePromise).close();
    },
  };

  /** @param {string} calibrationId @param {(current:CalibrationJournalRecord)=>CalibrationJournalRecord} mutate */
  async function updateRecord(calibrationId, mutate) {
    if (!calibrationId) {
      throw new CalibrationJournalStorageError(
        'invalid_id',
        'Calibration ID must be a non-empty string.',
      );
    }
    const database = await getDatabase();
    const transaction = database.transaction(STORE_NAME, 'readwrite');
    const complete = transactionResult(transaction);
    const store = transaction.objectStore(STORE_NAME);
    const request = store.get(calibrationId);
    let updated;
    /** @type {Error|DOMException|undefined} */
    let writeError;
    request.onsuccess = () => {
      try {
        const current = unpack(request.result);
        if (!current) {
          writeError = new CalibrationJournalStorageError(
            'session_not_found',
            `No calibration journal exists for ${calibrationId}.`,
          );
          transaction.abort();
          return;
        }
        updated = mutate(current);
        try {
          store.put({ calibrationId, kind: RECORD_KIND, ...updated });
        } catch (error) {
          writeError = new CalibrationJournalStorageError(
            'write_failed',
            'Could not update local calibration sync metadata.',
            error,
          );
          transaction.abort();
        }
      } catch (error) {
        writeError = error instanceof Error ? error : new Error(String(error));
        transaction.abort();
      }
    };
    request.onerror = () => {
      writeError = request.error ?? new Error('Could not read local calibration sync metadata.');
      transaction.abort();
    };
    try {
      await complete;
    } catch (error) {
      if (writeError instanceof CalibrationJournalStorageError) throw writeError;
      throw new CalibrationJournalStorageError(
        'transaction_failed',
        'Could not commit local calibration sync metadata.',
        writeError ?? error,
      );
    }
    return /** @type {CalibrationJournalRecord} */ (updated);
  }
}
