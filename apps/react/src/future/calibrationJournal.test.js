// @vitest-environment jsdom
import { IDBFactory } from 'fake-indexeddb';
import { describe, expect, it } from 'vitest';
import {
  CalibrationJournalStorageError,
  createCalibrationJournalStore,
} from './calibrationJournal';

const CREATED = '2026-09-01T10:00:00.000Z';

function session(overrides = {}) {
  return {
    schemaVersion: 1,
    calibrationId: 'calibration:test-1',
    scope: { kind: 'guest', guestId: 'guest:test-1' },
    bankVersion: 'association-bank-1',
    selectorVersion: 'selector-1',
    seed: 17,
    presentationMode: 'visual',
    currentMovement: 1,
    observations: [],
    actions: [],
    status: 'in-progress',
    createdAt: CREATED,
    updatedAt: CREATED,
    ...overrides,
  };
}

function observation(sequence = 1, response = { kind: 'pass' }) {
  const at = new Date(Date.parse(CREATED) + sequence * 1_000).toISOString();
  return {
    sequence,
    observationId: `observation-${sequence}`,
    trialId: `trial-${sequence}`,
    movement: 1,
    offered: [
      { stimulusId: 'shape-circle', stimulusVersion: '1', position: 0 },
      { stimulusId: 'word-rain', stimulusVersion: '1', position: 1 },
    ],
    response,
    presentedAt: at,
    recordedAt: at,
  };
}

function isolatedStore(options = {}) {
  return createCalibrationJournalStore(
    `calibration-test-${crypto.randomUUID()}`,
    options.factory || new IDBFactory(),
  );
}

async function rawDatabase(name, factory) {
  return new Promise((resolve, reject) => {
    const request = factory.open(name, 1);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

describe('calibration local journal', () => {
  it('creates with a write-through save and reloads from a fresh store instance', async () => {
    const databaseName = `calibration-test-${crypto.randomUUID()}`;
    const factory = new IDBFactory();
    const first = createCalibrationJournalStore(databaseName, factory);
    expect(await first.load('missing')).toBeNull();
    const saved = await first.save(session(), { expectedRevision: 0 });

    expect(saved).toMatchObject({
      revision: 1,
      hostRevision: 0,
      etag: null,
      syncStatus: 'pending',
    });
    expect(await first.load('calibration:test-1')).toEqual(saved);
    await first.close();

    const reloaded = createCalibrationJournalStore(databaseName, factory);
    expect(await reloaded.load('calibration:test-1')).toEqual(saved);
    await reloaded.close();
  });

  it('restores a host revision before accepting further local events', async () => {
    const store = isolatedStore();
    const restored = await store.restoreHost(session(), {
      etag: '"calibration-7"',
      revision: 7,
    });
    expect(restored).toMatchObject({
      revision: 7,
      hostRevision: 7,
      etag: '"calibration-7"',
      syncStatus: 'saved',
    });

    const next = await store.save(
      session({ currentMovement: 2, updatedAt: '2026-09-01T10:00:01.000Z' }),
      { expectedRevision: restored.revision },
    );
    expect(next).toMatchObject({
      revision: 8,
      hostRevision: 7,
      etag: '"calibration-7"',
      syncStatus: 'pending',
    });
    await store.close();
  });

  it('keeps an explicit host conflict parked while local evidence is retained', async () => {
    const store = isolatedStore();
    const created = await store.save(session(), { expectedRevision: 0 });
    await store.markHostConflict('calibration:test-1', {
      etag: '"calibration-2"',
      expectedEtag: null,
    });
    const updated = await store.save(
      session({ currentMovement: 2, updatedAt: '2026-09-01T10:00:01.000Z' }),
      { expectedRevision: created.revision },
    );
    expect(updated).toMatchObject({
      revision: 2,
      etag: '"calibration-2"',
      syncStatus: 'conflict',
    });
    expect((await store.load('calibration:test-1')).session.currentMovement).toBe(2);
    await store.close();
  });

  it('accepts append-only observations and retract/restore action revisions', async () => {
    const store = isolatedStore();
    const created = await store.save(session(), { expectedRevision: 0 });
    const firstObservation = observation(1, {
      kind: 'choose',
      chosenIds: ['shape-circle'],
    });
    const withObservation = await store.save(
      session({
        currentMovement: 2,
        observations: [firstObservation],
        updatedAt: firstObservation.recordedAt,
      }),
      { expectedRevision: created.revision },
    );
    const retraction = {
      sequence: 2,
      actionId: 'action-retract-1',
      targetObservationId: firstObservation.observationId,
      action: 'retract',
      recordedAt: '2026-09-01T10:00:03.000Z',
    };
    const retracted = await store.save(
      session({
        currentMovement: 2,
        observations: [firstObservation],
        actions: [retraction],
        updatedAt: '2026-09-01T10:00:03.000Z',
      }),
      { expectedRevision: withObservation.revision },
    );
    const restoration = {
      sequence: 3,
      actionId: 'action-restore-1',
      targetObservationId: firstObservation.observationId,
      action: 'restore',
      recordedAt: '2026-09-01T10:00:04.000Z',
    };
    const restored = await store.save(
      session({
        currentMovement: 2,
        observations: [firstObservation],
        actions: [retraction, restoration],
        updatedAt: '2026-09-01T10:00:04.000Z',
      }),
      { expectedRevision: retracted.revision },
    );

    expect(restored.revision).toBe(4);
    expect(restored.session.actions.map((item) => item.action)).toEqual([
      'retract',
      'restore',
    ]);
    expect((await store.load(restored.session.calibrationId)).session).toEqual(
      restored.session,
    );
    await store.close();
  });

  it('rejects corrupt records rather than silently treating them as absent', async () => {
    const databaseName = `calibration-test-${crypto.randomUUID()}`;
    const factory = new IDBFactory();
    const store = createCalibrationJournalStore(databaseName, factory);
    expect(await store.load('missing')).toBeNull();
    const database = await rawDatabase(databaseName, factory);
    const transaction = database.transaction('calibration-sessions', 'readwrite');
    transaction.objectStore('calibration-sessions').put({
      calibrationId: 'corrupt',
      kind: 'calibration-session-journal-v1',
      revision: 1,
      hostRevision: 0,
      etag: null,
      syncStatus: 'pending',
      session: { calibrationId: 'corrupt' },
    });
    await new Promise((resolve, reject) => {
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });

    await expect(store.load('corrupt')).rejects.toMatchObject({
      name: 'CalibrationJournalStorageError',
      code: 'invalid_record',
    });
    database.close();
    await store.close();
  });

  it('surfaces stale revisions, rewritten evidence, immutable identity changes, and event forks', async () => {
    const store = isolatedStore();
    const created = await store.save(session(), { expectedRevision: 0 });
    const withSetup = await store.save(
      session({
        setup: { weekday: 'Wednesday', language: 'en' },
        updatedAt: '2026-09-01T10:00:01.000Z',
      }),
      { expectedRevision: created.revision },
    );
    const stale = await store
      .save(
        session({ setup: { weekday: 'Thursday', language: 'en' } }),
        { expectedRevision: created.revision },
      )
      .catch((error) => error);
    expect(stale).toBeInstanceOf(CalibrationJournalStorageError);
    expect(stale).toMatchObject({ code: 'write_conflict' });
    expect(stale.current).toEqual(withSetup);

    const chosen = observation(1, { kind: 'choose', chosenIds: ['shape-circle'] });
    const appended = await store.save(
      session({ observations: [chosen], updatedAt: chosen.recordedAt }),
      { expectedRevision: withSetup.revision },
    );
    await expect(
      store.save(
        session({
          observations: [observation(1)],
          updatedAt: '2026-09-01T10:00:01.000Z',
        }),
        { expectedRevision: appended.revision },
      ),
    ).rejects.toMatchObject({ code: 'write_conflict' });
    await expect(
      store.save(
        session({ bankVersion: 'different-bank' }),
        { expectedRevision: appended.revision },
      ),
    ).rejects.toMatchObject({ code: 'write_conflict' });
    expect((await store.load('calibration:test-1')).session).toEqual(
      appended.session,
    );
    await store.close();
  });

  it('allows cursor reversal while keeping terminal sessions immutable', async () => {
    const store = isolatedStore();
    const created = await store.save(session(), { expectedRevision: 0 });
    const advanced = await store.save(
      session({
        currentMovement: 3,
        updatedAt: '2026-09-01T10:00:01.000Z',
      }),
      { expectedRevision: created.revision },
    );
    const movedBack = await store.save(
      session({
        currentMovement: 1,
        updatedAt: '2026-09-01T10:00:02.000Z',
      }),
      { expectedRevision: advanced.revision },
    );
    expect(movedBack.session.currentMovement).toBe(1);

    const completionResponses = [1, 2, 3, 4].map((movement) => {
      const response = observation(movement, { kind: 'pass' });
      return {
        ...response,
        observationId: `completion-observation-${movement}`,
        trialId: `completion-trial-${movement}`,
        movement,
        presentedAt: `2026-09-01T10:00:0${movement + 2}.000Z`,
        recordedAt: `2026-09-01T10:00:0${movement + 2}.000Z`,
      };
    });
    const completed = await store.save(
      session({
        currentMovement: 5,
        observations: completionResponses,
        setup: { weekday: 'Wednesday', language: 'en' },
        status: 'completed',
        updatedAt: '2026-09-01T10:00:07.000Z',
        completedAt: '2026-09-01T10:00:07.000Z',
      }),
      { expectedRevision: movedBack.revision },
    );
    await expect(
      store.save(
        session({
          currentMovement: 5,
          observations: completionResponses,
          setup: { weekday: 'Thursday', language: 'en' },
          status: 'completed',
          updatedAt: '2026-09-01T10:00:08.000Z',
          completedAt: '2026-09-01T10:00:08.000Z',
        }),
        { expectedRevision: completed.revision },
      ),
    ).rejects.toMatchObject({ code: 'write_conflict' });
    await store.close();
  });

  it('surfaces unavailable IndexedDB failures without falling back to memory', async () => {
    const store = createCalibrationJournalStore('unavailable-test', {
      open() {
        throw new Error('quota or disabled');
      },
    });

    await expect(
      store.save(session(), { expectedRevision: 0 }),
    ).rejects.toMatchObject({
      name: 'CalibrationJournalStorageError',
      code: 'open_failed',
    });
  });

  it('tracks host ETags, saved revisions, pending newer edits, and conflicts', async () => {
    const store = isolatedStore();
    const created = await store.save(session(), { expectedRevision: 0 });
    const synced = await store.markHostSynced('calibration:test-1', {
      etag: '"host-1"',
      expectedEtag: null,
      syncedRevision: created.revision,
    });
    expect(synced).toMatchObject({
      hostRevision: 1,
      etag: '"host-1"',
      syncStatus: 'saved',
    });

    const progressed = await store.save(
      session({
        setup: { weekday: 'Thursday', language: 'fr' },
        updatedAt: '2026-09-01T10:00:01.000Z',
      }),
      { expectedRevision: synced.revision },
    );
    expect(progressed).toMatchObject({
      revision: 2,
      hostRevision: 1,
      etag: '"host-1"',
      syncStatus: 'pending',
    });

    const lateAck = await store.markHostSynced('calibration:test-1', {
      etag: '"stale-host-1"',
      expectedEtag: null,
      syncedRevision: 1,
    });
    expect(lateAck.etag).toBe('"host-1"');
    expect(lateAck.syncStatus).toBe('pending');

    const caughtUp = await store.markHostSynced('calibration:test-1', {
      etag: '"host-2"',
      expectedEtag: '"host-1"',
      syncedRevision: progressed.revision,
    });
    expect(caughtUp).toMatchObject({ hostRevision: 2, etag: '"host-2"', syncStatus: 'saved' });
    expect(
      await store.markHostConflict('calibration:test-1', {
        etag: '"remote-newer"',
        expectedEtag: '"host-2"',
      }),
    ).toMatchObject({ etag: '"remote-newer"', syncStatus: 'conflict' });
    await store.close();
  });
});
