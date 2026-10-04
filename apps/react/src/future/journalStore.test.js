import 'fake-indexeddb/auto';
import { afterEach, describe, expect, it } from 'vitest';
import { createFutureJournalStore, FutureJournalStorageError } from './journalStore';

const openedStores = [];

function makeRecord(sessionId = crypto.randomUUID(), profileId = 'profile-1') {
  return {
    schemaVersion: 2,
    sessionId,
    profileId,
    puzzleHash: 'a'.repeat(64),
    initialGrid: [{ cellId: 'r0c0', token: null, origin: 'unknown' }],
    writerToken: '0123456789abcdef0123456789abcdef',
    events: [
      { schemaVersion: 2, seq: 1, type: 'session-started' },
      { schemaVersion: 2, seq: 2, type: 'cell-written' },
      { schemaVersion: 2, seq: 3, type: 'entry-focused' }
    ],
    acknowledgedSeq: 0,
    status: 'active',
    createdAt: '2026-09-26T08:00:00.000Z',
    updatedAt: '2026-09-26T08:00:00.000Z'
  };
}

function makeStore() {
  const databaseName = `future-journal-${crypto.randomUUID()}`;
  const repository = createFutureJournalStore(databaseName);
  openedStores.push(repository);
  return repository;
}

function createV3DatabaseWithRows(databaseName, rows) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(databaseName, 3);
    request.onupgradeneeded = () => {
      request.result.createObjectStore('solve-events', { keyPath: 'id' });
    };
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const database = request.result;
      const transaction = database.transaction('solve-events', 'readwrite');
      const store = transaction.objectStore('solve-events');
      rows.forEach((row) => store.put(row));
      transaction.oncomplete = () => {
        database.close();
        resolve();
      };
      transaction.onerror = () => reject(transaction.error);
    };
  });
}

afterEach(async () => {
  await Promise.all(openedStores.splice(0).map((store) => store.close()));
});

describe('future solve journal store', () => {
  it('saves, loads, and lists bounded v2 records per session', async () => {
    const store = makeStore();
    const first = makeRecord();
    const second = makeRecord(crypto.randomUUID(), 'profile-2');

    await store.save(first);
    await store.save(second);

    expect(await store.load(first.sessionId)).toEqual(first);
    expect(await store.list()).toEqual([first, second].sort((left, right) => left.sessionId.localeCompare(right.sessionId)));
    expect(await store.list('profile-2')).toEqual([second]);
    expect(await store.load('missing-session')).toBeUndefined();
  });

  it('updates acknowledgements atomically and a stale save cannot roll them back', async () => {
    const store = makeStore();
    const record = makeRecord();
    await store.save(record);

    const acknowledgements = await Promise.all([
      store.updateAcknowledgedSeq(record.sessionId, 2),
      store.updateAcknowledgedSeq(record.sessionId, 3)
    ]);
    expect(acknowledgements.map((item) => item.acknowledgedSeq)).toEqual([2, 3]);

    const staleCopy = { ...record, events: [...record.events, { schemaVersion: 2, seq: 4, type: 'cell-cleared' }] };
    const saved = await store.save(staleCopy);
    expect(saved.acknowledgedSeq).toBe(3);
    expect((await store.updateAcknowledgedSeq(record.sessionId, 1)).acknowledgedSeq).toBe(3);
    expect((await store.load(record.sessionId)).acknowledgedSeq).toBe(3);
  });

  it('rejects a concurrent writer that changes an already stored event prefix', async () => {
    const store = makeStore();
    const record = makeRecord();
    await store.save(record);
    const first = structuredClone(record);
    const second = structuredClone(record);
    first.events.push({ schemaVersion: 2, seq: 4, eventId: 'first-writer', type: 'cell-written' });
    second.events.push({ schemaVersion: 2, seq: 4, eventId: 'second-writer', type: 'cell-cleared' });

    await store.save(first);
    await expect(store.save(second)).rejects.toMatchObject({ code: 'write_conflict' });
    expect((await store.load(record.sessionId)).events.at(-1)).toMatchObject({ eventId: 'first-writer' });
  });

  it('does not allow a stale active copy to reopen a finished journal', async () => {
    const store = makeStore();
    const record = makeRecord();
    await store.save(record);
    await store.save({ ...record, status: 'finished' });

    await expect(store.save({ ...record, events: [...record.events, { schemaVersion: 2, seq: 4, type: 'cell-written' }] }))
      .rejects.toMatchObject({ code: 'write_conflict' });
    expect((await store.load(record.sessionId)).status).toBe('finished');
  });

  it('preserves preexisting rows in the shared solve-events object store', async () => {
    const databaseName = `future-journal-shared-${crypto.randomUUID()}`;
    const legacyRow = { id: 'legacy-event-1', sessionId: 'old-session', seq: 1, type: 'cell-written' };
    await createV3DatabaseWithRows(databaseName, [legacyRow]);
    const store = createFutureJournalStore(databaseName);
    openedStores.push(store);
    const record = makeRecord();

    await store.save(record);

    const loaded = await store.load(record.sessionId);
    expect(loaded).toEqual(record);
    const rawDatabase = await new Promise((resolve, reject) => {
      const request = indexedDB.open(databaseName, 3);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    expect(rawDatabase.version).toBe(3);
    const transaction = rawDatabase.transaction('solve-events', 'readonly');
    const rows = await new Promise((resolve, reject) => {
      const request = transaction.objectStore('solve-events').getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    rawDatabase.close();
    expect(rows).toContainEqual(legacyRow);
    expect(rows).toHaveLength(2);
  });

  it('surfaces missing IndexedDB instead of silently switching to memory', async () => {
    const store = createFutureJournalStore('no-memory-fallback', null);

    await expect(store.load('session')).rejects.toMatchObject({
      name: 'FutureJournalStorageError',
      code: 'unavailable'
    });
  });

  it('rejects invalid records and events beyond the bounded storage limit', async () => {
    const store = makeStore();
    const record = makeRecord();

    await expect(store.save({ ...record, acknowledgedSeq: 4 })).rejects.toBeInstanceOf(FutureJournalStorageError);
    await expect(store.save({ ...record, events: [{ payload: 'x'.repeat(1_100_000) }] })).rejects.toMatchObject({
      code: 'record_too_large'
    });
    await expect(store.updateAcknowledgedSeq(record.sessionId, 1)).rejects.toMatchObject({ code: 'session_not_found' });
  });
});
