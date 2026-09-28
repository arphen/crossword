// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { describe, expect, it, vi } from 'vitest';
import {
  describeLegacyPuzzle,
  FutureSessionRecorder,
  sha256,
} from './sessionJournal';

function puzzleApp() {
  return {
    currentPuzzleMetadata: { date: '260926' },
    completedWords: new Set(),
    grid: [
      ['', '', ''],
      ['', null, null],
      ['', null, null],
    ],
    crossword: [
      {
        direction: 'across',
        clue_number: 1,
        clue_text: 'Feline',
        start_x: 0,
        start_y: 0,
        characters: [{ letters: 'C' }, { letters: 'A' }, { letters: 'T' }],
      },
      {
        direction: 'down',
        clue_number: 1,
        clue_text: 'Vehicle',
        start_x: 0,
        start_y: 0,
        characters: [{ letters: 'C' }, { letters: 'A' }, { letters: 'R' }],
      },
    ],
    activeDirection: 'across',
    activeClueNumber: 1,
  };
}

function manifestFor(app, digest = 'ab'.repeat(32), answerOverrides = {}) {
  const cells = [];
  const cellIdByGeometry = new Map();
  app.grid.forEach((row, rowIndex) =>
    row.forEach((value, columnIndex) => {
      const id = `server-r${rowIndex}-c${columnIndex}`;
      cells.push({
        id,
        row: rowIndex,
        column: columnIndex,
        block: value === null,
        circled: false,
        shaded: false,
      });
      if (value !== null)
        cellIdByGeometry.set(`r${rowIndex}c${columnIndex}`, id);
    }),
  );
  return {
    schemaVersion: 1,
    id: 'puzzle:manifest-fixture',
    width: app.grid[0].length,
    height: app.grid.length,
    integrity: { algorithm: 'sha256', value: digest },
    cells,
    entries: app.crossword.map((entry) => {
      const geometry =
        entry.direction === 'across'
          ? entry.characters.map(
              (_, index) => `r${entry.start_y}c${entry.start_x + index}`,
            )
          : entry.characters.map(
              (_, index) => `r${entry.start_y + index}c${entry.start_x}`,
            );
      const legacyId = `${entry.direction}-${entry.clue_number}`;
      return {
        id: `server-${legacyId}`,
        number: entry.clue_number,
        direction: entry.direction,
        cellIds: geometry.map((cellId) => cellIdByGeometry.get(cellId)),
        answer:
          answerOverrides[legacyId] ||
          entry.characters.map((character) => character.letters).join(''),
        clue: entry.clue_text,
      };
    }),
  };
}

function repository() {
  const records = new Map();
  return {
    records,
    async list(profileId) {
      return [...records.values()]
        .filter((record) => !profileId || record.profileId === profileId)
        .map((record) => structuredClone(record));
    },
    async save(record) {
      const prior = records.get(record.sessionId);
      const saved = structuredClone({
        ...record,
        acknowledgedSeq: Math.max(
          record.acknowledgedSeq,
          prior?.acknowledgedSeq || 0,
        ),
      });
      records.set(record.sessionId, saved);
      return structuredClone(saved);
    },
    async updateAcknowledgedSeq(sessionId, seq) {
      const saved = await this.save({
        ...records.get(sessionId),
        acknowledgedSeq: seq,
      });
      return saved;
    },
    async close() {},
  };
}

function host() {
  const sessions = new Map();
  const calls = [];
  const fetchImpl = vi.fn(async (url, request) => {
    const body = JSON.parse(request.body);
    calls.push({ url, body });
    if (url === '/api/future/sessions') {
      const current = sessions.get(body.sessionId) || {
        acceptedSeq: 0,
        events: [],
        idsBySeq: new Map(),
      };
      sessions.set(body.sessionId, current);
      return {
        ok: true,
        status: 200,
        json: async () => ({ acceptedSeq: current.acceptedSeq }),
      };
    }
    const sessionId = url.match(/\/sessions\/([^/]+)\/events$/)?.[1];
    const current = sessions.get(sessionId) || [...sessions.values()][0];
    const acceptedEventIds = [];
    const duplicateEventIds = [];
    for (const event of body.events) {
      if (current.idsBySeq.has(event.seq))
        duplicateEventIds.push(event.eventId);
      else {
        current.idsBySeq.set(event.seq, event.eventId);
        current.events.push(event);
        current.acceptedSeq = event.seq;
        acceptedEventIds.push(event.eventId);
      }
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({
        acceptedSeq: current.acceptedSeq,
        acceptedEventIds,
        duplicateEventIds,
      }),
    };
  });
  return { sessions, calls, fetchImpl };
}

describe('future event journal', () => {
  it('hashes clue editions independently of the player grid', async () => {
    const app = puzzleApp();
    const before = describeLegacyPuzzle(app);
    expect(Object.hasOwn(before, 'puzzleHash')).toBe(false);
    app.grid[0][0] = 'X';
    const after = describeLegacyPuzzle(app);

    expect(after.edition).toEqual(before.edition);
    expect(after.cells.find((cell) => cell.cellId === 'r0c0')).toEqual({
      cellId: 'r0c0',
      token: 'X',
      origin: 'unknown',
    });
  });

  it('uses a supported manifest digest as the journal hash without replacing legacy geometry', async () => {
    const app = puzzleApp();
    const legacy = describeLegacyPuzzle(app);
    const digest = 'ab'.repeat(32);
    app.currentPuzzleManifest = manifestFor(app, digest);
    const puzzle = describeLegacyPuzzle(app);

    expect(puzzle.puzzleHash).toBe(digest);
    expect(puzzle.edition).toEqual(legacy.edition);
    expect(puzzle.entries.map((entry) => entry.id)).toEqual([
      'server-across-1',
      'server-down-1',
    ]);
    expect(puzzle.cells.map((cell) => cell.cellId)).toContain('server-r0-c0');
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repository(),
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    recorder.scheduleFlush = vi.fn();
    await recorder.start();
    expect(recorder.session.puzzleHash).toBe(digest);
    recorder.dispose();
  });

  it('uses a private manifest answerTokens sequence for a multi-unit cell', async () => {
    const app = puzzleApp();
    app.crossword[0].characters[1] = { letters: 'SS' };
    app.crossword[1].characters[0] = { letters: 'SS' };
    const manifest = manifestFor(app, 'ef'.repeat(32));
    manifest.entries[0].answer = 'CSST';
    manifest.entries[0].answerTokens = ['C', 'SS', 'T'];
    manifest.entries[1].answer = 'SSR';
    manifest.entries[1].answerTokens = ['SS', 'A', 'R'];
    app.currentPuzzleManifest = manifest;

    const puzzle = describeLegacyPuzzle(app);

    expect(puzzle.entries.find((entry) => entry.id === 'server-across-1')).toMatchObject({
      answerTokens: ['C', 'SS', 'T'],
    });
    expect(puzzle.entries.find((entry) => entry.id === 'server-down-1')).toMatchObject({
      answerTokens: ['SS', 'A', 'R'],
    });
  });

  it('canonicalizes a display-token reveal before journaling it', async () => {
    const app = puzzleApp();
    app.crossword[0].characters[1] = {
      letters: 'SS',
      tokenMetadata: { displayToken: 'ß', fillToken: 'SS' },
    };
    app.crossword[1].characters[0] = {
      letters: 'SS',
      tokenMetadata: { displayToken: 'ß', fillToken: 'SS' },
    };
    const manifest = manifestFor(app, 'ef'.repeat(32));
    manifest.entries[0].answer = 'CSST';
    manifest.entries[0].answerTokens = ['C', 'SS', 'T'];
    manifest.entries[1].answer = 'SSR';
    manifest.entries[1].answerTokens = ['SS', 'A', 'R'];
    app.currentPuzzleManifest = manifest;
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(app),
      repository: repository(),
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    recorder.scheduleFlush = vi.fn();
    await recorder.start(app);

    recorder.revealCell(
      { row: 0, column: 1, beforeToken: null, token: 'ß' },
      app,
    );
    await recorder.eventChain;

    expect(recorder.session.events.at(-1)).toMatchObject({
      type: 'answer-revealed',
      cells: [{ token: 'SS' }],
    });
    recorder.dispose();
  });

  it('ignores an unsupported manifest integrity format and retains the legacy hash path', async () => {
    const app = puzzleApp();
    app.currentPuzzleManifest = {
      ...manifestFor(app),
      integrity: { algorithm: 'sha512', value: 'not-a-sha256-digest' },
    };
    const puzzle = describeLegacyPuzzle(app);
    const expected = await sha256(puzzle.edition, webcrypto);
    expect(Object.hasOwn(puzzle, 'puzzleHash')).toBe(false);
    const fetchImpl = vi.fn();
    const statuses = [];

    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repository(),
      fetchImpl,
      cryptoApi: webcrypto,
      onStatus: (status) => statuses.push(status),
    });
    recorder.scheduleFlush = vi.fn();
    await recorder.start();
    await recorder.flush();
    expect(recorder.session.puzzleHash).toBe(expected);
    expect(recorder.session.syncStatus).toBe('unsupported-local');
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(statuses).toContain('unsupported');
    recorder.dispose();
  });

  it('buffers events until IndexedDB startup finishes and preserves their sequence', async () => {
    let releaseList;
    const listGate = new Promise((resolve) => {
      releaseList = resolve;
    });
    const base = repository();
    const repo = { ...base, list: vi.fn(() => listGate) };
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app);
    const puzzle = describeLegacyPuzzle(app);
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repo,
      fetchImpl: vi.fn(),
      cryptoApi: webcrypto,
    });
    recorder.scheduleFlush = vi.fn();
    const starting = recorder.start(app);
    expect(recorder.ready).toBe(false);
    app.grid[0][0] = 'C';
    recorder.cellChanged(
      {
        row: 0,
        column: 0,
        beforeToken: null,
        afterToken: 'C',
        source: 'keyboard',
        activeEntryId: 'across-1',
      },
      app,
    );
    const queued = recorder.emit({
      type: 'visibility-changed',
      visibility: 'hidden',
    });
    expect(recorder.pendingEvents).toHaveLength(2);
    releaseList([]);
    await starting;
    await queued;

    expect(recorder.ready).toBe(true);
    expect(recorder.session.events.map((event) => event.type)).toEqual([
      'session-started',
      'cell-written',
      'visibility-changed',
    ]);
    expect(recorder.session.events[1]).toMatchObject({
      cellId: 'server-r0-c0',
      beforeToken: null,
      afterToken: 'C',
      activeEntryId: 'server-across-1',
      seq: 2,
    });
    recorder.dispose();
  });

  it('merges queued edits over a resumed grid with replay-correct before tokens', async () => {
    const baseApp = puzzleApp();
    baseApp.currentPuzzleManifest = manifestFor(baseApp);
    const puzzle = describeLegacyPuzzle(baseApp);
    const repo = repository();
    const previous = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repo,
      fetchImpl: vi.fn(),
      cryptoApi: webcrypto,
    });
    previous.scheduleFlush = vi.fn();
    await previous.start(baseApp);
    baseApp.grid[0][0] = 'C';
    previous.cellChanged(
      {
        row: 0,
        column: 0,
        beforeToken: null,
        afterToken: 'C',
        source: 'keyboard',
        activeEntryId: 'across-1',
      },
      baseApp,
    );
    await previous.eventChain;
    previous.dispose();

    let releaseList;
    const listGate = new Promise((resolve) => {
      releaseList = resolve;
    });
    const delayedRepository = { ...repo, list: vi.fn(() => listGate) };
    const resumedApp = puzzleApp();
    resumedApp.currentPuzzleManifest = manifestFor(resumedApp);
    const resumed = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(resumedApp),
      repository: delayedRepository,
      fetchImpl: vi.fn(),
      cryptoApi: webcrypto,
    });
    resumed.scheduleFlush = vi.fn();
    const starting = resumed.start(resumedApp);
    resumedApp.grid[0][0] = 'X';
    resumed.cellChanged(
      {
        row: 0,
        column: 0,
        beforeToken: null,
        afterToken: 'X',
        source: 'keyboard',
        activeEntryId: 'across-1',
      },
      resumedApp,
    );
    resumedApp.activeDirection = 'down';
    resumed.focus(resumedApp.crossword[1], resumedApp, 'pointer');
    releaseList(await repo.list('profile-1'));
    await starting;

    const latestWrite = resumed.session.events
      .filter((event) => event.type === 'cell-written')
      .at(-1);
    expect(latestWrite).toMatchObject({
      cellId: 'server-r0-c0',
      beforeToken: 'C',
      afterToken: 'X',
      activeEntryId: 'server-across-1',
    });
    expect(resumedApp.grid[0][0]).toBe('X');
    expect(resumed.session.events.at(-1).visiblePattern[0]).toMatchObject({
      token: 'X',
      origin: 'crossing',
      sourceEntryId: 'server-across-1',
    });
    resumed.dispose();
  });

  it('records puzzle-wide checks as clue-scoped evidence using server answers and names a containing clue on reveal', async () => {
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app, 'cd'.repeat(32), {
      'across-1': 'COT',
    });
    const puzzle = describeLegacyPuzzle(app);
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repository(),
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    recorder.scheduleFlush = vi.fn();
    await recorder.start(app);
    app.grid[0][0] = 'C';
    recorder.cellChanged(
      {
        row: 0,
        column: 0,
        beforeToken: null,
        afterToken: 'C',
        source: 'keyboard',
        activeEntryId: 'across-1',
      },
      app,
    );
    await recorder.eventChain;
    app.activeDirection = 'down';
    recorder.focus(app.crossword[1], app, 'pointer');
    await recorder.eventChain;
    expect(recorder.session.events.at(-1).visiblePattern[0]).toMatchObject({
      cellId: 'server-r0-c0',
      origin: 'crossing',
      sourceEntryId: 'server-across-1',
    });

    app.grid[0][1] = 'A';
    recorder.checked(app);
    await recorder.eventChain;
    const checks = recorder.session.events.filter(
      (event) => event.type === 'check-result-shown',
    );
    expect(checks).toHaveLength(2);
    expect(checks.map((event) => [event.scope, event.entryId])).toEqual([
      ['entry', 'server-across-1'],
      ['entry', 'server-down-1'],
    ]);
    expect(
      checks[0].results.find((result) => result.cellId === 'server-r0-c1'),
    ).toMatchObject({
      token: 'A',
      classification: 'incorrect',
    });

    recorder.revealCell(
      { row: 0, column: 1, beforeToken: 'A', token: 'O' },
      app,
    );
    await recorder.eventChain;
    expect(recorder.session.events.at(-1)).toMatchObject({
      type: 'answer-revealed',
      scope: 'cell',
      entryId: 'server-across-1',
      cells: [{ cellId: 'server-r0-c1', beforeToken: 'A', token: 'O' }],
    });
    recorder.dispose();
  });

  it('journals a prepared assistance tier without changing the board', async () => {
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app);
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(app),
      repository: repository(),
      cryptoApi: webcrypto,
    });
    await recorder.start();
    recorder.hintShown({
      entryId: 'across-1',
      hintId: 'prepared-clue-reading-v1',
      assistanceTier: 'clue-reading',
      affectedCellIds: [],
    });
    await recorder.eventChain;
    expect(recorder.session.events.at(-1)).toMatchObject({
      type: 'hint-shown',
      entryId: 'server-across-1',
      hintId: 'prepared-clue-reading-v1',
      assistanceTier: 'clue-reading',
      affectedCellIds: [],
    });
    expect(recorder.sessionGrid().get('server-r0-c0')).toBe(null);
    recorder.dispose();
  });

  it('journals focus support, actual check feedback, reveals, and an honest finish', async () => {
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app);
    const puzzle = describeLegacyPuzzle(app);
    const repo = repository();
    const server = host();
    const statuses = [];
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repo,
      fetchImpl: server.fetchImpl,
      cryptoApi: webcrypto,
      onStatus: (status) => statuses.push(status),
    });
    recorder.scheduleFlush = vi.fn();
    await recorder.start();
    await recorder.flush();
    expect(recorder.session.acknowledgedSeq).toBe(1);

    recorder.focus(app.crossword[0], app, 'pointer');
    app.grid[0][0] = 'C';
    recorder.cellChanged(
      {
        row: 0,
        column: 0,
        beforeToken: null,
        afterToken: 'C',
        source: 'keyboard',
      },
      app,
    );
    app.grid[0][1] = 'A';
    recorder.cellChanged(
      {
        row: 0,
        column: 1,
        beforeToken: null,
        afterToken: 'A',
        source: 'keyboard',
      },
      app,
    );
    app.grid[0][2] = 'T';
    recorder.cellChanged(
      {
        row: 0,
        column: 2,
        beforeToken: null,
        afterToken: 'T',
        source: 'keyboard',
      },
      app,
    );
    await recorder.eventChain;
    recorder.checked(app);
    await recorder.eventChain;
    recorder.focus(app.crossword[1], app, 'keyboard');
    await recorder.eventChain;

    const downFocus = recorder.session.events.at(-1);
    expect(downFocus.type).toBe('entry-focused');
    expect(downFocus.visiblePattern[0]).toMatchObject({
      cellId: 'server-r0-c0',
      token: 'C',
      origin: 'crossing',
      sourceEntryId: 'server-across-1',
    });
    const check = recorder.session.events.find(
      (event) => event.type === 'check-result-shown',
    );
    expect(
      check.results.find((item) => item.cellId === 'server-r0-c1'),
    ).toMatchObject({ token: 'A', classification: 'correct' });

    const beforeReveal = new Map([
      ['r0c0', 'C'],
      ['r0c1', 'A'],
      ['r0c2', 'T'],
      ['r1c0', null],
      ['r2c0', null],
    ]);
    const afterReveal = new Map([
      ['r0c0', 'C'],
      ['r0c1', 'A'],
      ['r0c2', 'T'],
      ['r1c0', 'A'],
      ['r2c0', 'R'],
    ]);
    recorder.revealed(beforeReveal, afterReveal);
    await recorder.eventChain;
    await recorder.finishPromise;
    await recorder.flush();

    expect(recorder.session.status).toBe('finished');
    expect(recorder.session.events.at(-1)).toMatchObject({
      type: 'session-finished',
      reason: 'complete',
    });
    const reveal = recorder.session.events.find(
      (event) => event.type === 'answer-revealed',
    );
    expect(reveal.cells).toHaveLength(afterReveal.size);
    expect(
      reveal.cells.filter((cell) => cell.beforeToken === cell.token),
    ).toHaveLength(3);
    expect(recorder.session.acknowledgedSeq).toBe(
      recorder.session.events.length,
    );
    expect(server.calls.some((call) => call.url.endsWith('/events'))).toBe(
      true,
    );
    expect(statuses).toContain('saved');
    recorder.dispose();
  });

  it('keeps each event locally when the host is unavailable', async () => {
    const repo = repository();
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app);
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(app),
      repository: repo,
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    recorder.scheduleFlush = vi.fn();
    await recorder.start();
    await recorder.emit({
      type: 'cell-written',
      cellId: 'server-r0-c0',
      beforeToken: null,
      afterToken: 'C',
      activeEntryId: 'server-across-1',
      actionId: 'action-1',
      source: 'keyboard',
    });
    await recorder.flush();

    const saved = await repo.records.get(recorder.session.sessionId);
    expect(saved.events.map((event) => event.type)).toEqual([
      'session-started',
      'cell-written',
    ]);
    expect(saved.acknowledgedSeq).toBe(0);
    recorder.dispose();
  });

  it('retries a host-marked profile CAS conflict and finishes without reload', async () => {
    vi.useFakeTimers();
    try {
      const app = puzzleApp();
      app.currentPuzzleManifest = manifestFor(app);
      const eventPosts = [];
      const fetchImpl = vi.fn(async (url, request) => {
        if (url === '/api/future/sessions')
          return {
            ok: true,
            status: 200,
            json: async () => ({ acceptedSeq: 0 }),
          };
        const events = JSON.parse(request.body).events;
        eventPosts.push(events);
        if (eventPosts.length === 1)
          return {
            ok: false,
            status: 409,
            json: async () => ({
              error: 'Stale profile revision: another update won the commit',
              retryable: true,
            }),
          };
        return {
          ok: true,
          status: 200,
          json: async () => ({
            acceptedSeq: events.at(-1).seq,
            acceptedEventIds: events.map((event) => event.eventId),
            duplicateEventIds: [],
          }),
        };
      });
      const statuses = [];
      const recorder = new FutureSessionRecorder({
        profileId: 'profile-1',
        puzzle: describeLegacyPuzzle(app),
        repository: repository(),
        fetchImpl,
        cryptoApi: webcrypto,
        onStatus: (status) => statuses.push(status),
      });
      const schedule = recorder.scheduleFlush.bind(recorder);
      recorder.scheduleFlush = (delay = 700) => {
        if (delay === 5000) schedule(delay);
      };
      await recorder.start();
      await recorder.finish('stopped');

      expect(recorder.session.events.map((event) => event.type)).toEqual([
        'session-started',
        'session-finished',
      ]);
      expect(eventPosts).toHaveLength(1);
      expect(statuses).toContain('syncing');
      expect(statuses).not.toContain('conflict');

      await vi.advanceTimersByTimeAsync(5000);
      await recorder.flushChain;

      expect(eventPosts).toHaveLength(2);
      expect(eventPosts[1].map((event) => event.eventId)).toEqual(
        eventPosts[0].map((event) => event.eventId),
      );
      expect(recorder.session.acknowledgedSeq).toBe(2);
      expect(statuses.at(-1)).toBe('finished');
      recorder.dispose();
    } finally {
      vi.useRealTimers();
    }
  });

  it('keeps edits appended during an IndexedDB acknowledgement transaction', async () => {
    const records = new Map();
    let heldSave = null;
    const repo = {
      async list(profileId) {
        return [...records.values()]
          .filter((record) => !profileId || record.profileId === profileId)
          .map((record) => structuredClone(record));
      },
      async save(record) {
        // IndexedDB validates the candidate before awaiting its open database
        // and transaction. Hold that candidate so a host acknowledgement can
        // commit an older snapshot before this write reaches the store.
        const candidate = structuredClone(record);
        if (heldSave && candidate.events.length === heldSave.eventCount) {
          const pending = heldSave;
          heldSave = null;
          pending.started();
          await pending.gate;
        }
        const prior = records.get(candidate.sessionId);
        if (
          prior &&
          (candidate.events.length < prior.events.length ||
            prior.events.some(
              (event, index) =>
                JSON.stringify(candidate.events[index]) !==
                JSON.stringify(event),
            ))
        )
          throw Object.assign(
            new Error('Another open crossword session has advanced this local journal.'),
            { code: 'write_conflict' },
          );
        const saved = structuredClone({
          ...candidate,
          acknowledgedSeq: Math.max(
            candidate.acknowledgedSeq,
            prior?.acknowledgedSeq || 0,
          ),
        });
        records.set(saved.sessionId, saved);
        return structuredClone(saved);
      },
      async updateAcknowledgedSeq(sessionId, sequence) {
        const current = records.get(sessionId);
        if (!current || sequence > current.events.length)
          throw new Error('Acknowledgement is outside the persisted journal.');
        const updated = structuredClone({
          ...current,
          acknowledgedSeq: Math.max(current.acknowledgedSeq, sequence),
        });
        records.set(sessionId, updated);
        return structuredClone(updated);
      },
      async close() {},
    };
    const saveStarted = {};
    saveStarted.promise = new Promise((resolve) => {
      saveStarted.resolve = resolve;
    });
    let releaseCapturedSave = () => {};
    const capturedSaveGate = new Promise((resolve) => {
      releaseCapturedSave = resolve;
    });
    const eventBatchStarted = {};
    eventBatchStarted.promise = new Promise((resolve) => {
      eventBatchStarted.resolve = resolve;
    });
    let releaseHostBatch;
    const hostBatchGate = new Promise((resolve) => {
      releaseHostBatch = resolve;
    });
    const fetchImpl = vi.fn(async (url, request) => {
      if (url === '/api/future/sessions')
        return {
          ok: true,
          status: 201,
          json: async () => ({ acceptedSeq: 0 }),
        };
      const body = JSON.parse(request.body);
      eventBatchStarted.resolve();
      await hostBatchGate;
      return {
        ok: true,
        status: 200,
        json: async () => ({
          acceptedSeq: body.expectedSeq + body.events.length,
          acceptedEventIds: body.events.map((event) => event.eventId),
          duplicateEventIds: [],
        }),
      };
    });
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app);
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(app),
      repository: repo,
      fetchImpl,
      cryptoApi: webcrypto,
    });
    recorder.scheduleFlush = vi.fn();
    try {
      await recorder.start();
      await recorder.emit({
        type: 'cell-written',
        cellId: 'server-r0-c0',
        beforeToken: null,
        afterToken: 'C',
        activeEntryId: 'server-across-1',
        actionId: 'first-edit',
        source: 'keyboard',
      });

      const flushing = recorder.flush();
      await eventBatchStarted.promise;
      heldSave = {
        eventCount: 3,
        gate: capturedSaveGate,
        started: saveStarted.resolve,
      };
      const thirdEvent = recorder.emit({
        type: 'cell-written',
        cellId: 'server-r0-c1',
        beforeToken: null,
        afterToken: 'A',
        activeEntryId: 'server-across-1',
        actionId: 'second-edit',
        source: 'keyboard',
      });
      await saveStarted.promise;

      // The server acknowledges the first two events while the third event's
      // local write is in flight. Its acknowledgement snapshot is therefore
      // older than the event array currently held by the recorder.
      releaseHostBatch();
      await flushing;
      releaseCapturedSave();
      await thirdEvent;

      await recorder.emit({
        type: 'cell-written',
        cellId: 'server-r0-c2',
        beforeToken: null,
        afterToken: 'T',
        activeEntryId: 'server-across-1',
        actionId: 'third-edit',
        source: 'keyboard',
      });

      expect(recorder.session.events.map((event) => event.seq)).toEqual([
        1, 2, 3, 4,
      ]);
      expect(records.get(recorder.session.sessionId).events).toHaveLength(4);
      expect(recorder.session.acknowledgedSeq).toBe(2);
    } finally {
      releaseHostBatch();
      releaseCapturedSave();
      recorder.dispose();
    }
  });

  it('labels a pre-check letter from another clue as crossing support', async () => {
    const app = puzzleApp();
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(app),
      repository: repository(),
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    recorder.scheduleFlush = vi.fn();
    await recorder.start();
    app.grid[0][0] = 'C';
    recorder.cellChanged(
      {
        row: 0,
        column: 0,
        beforeToken: null,
        afterToken: 'C',
        source: 'keyboard',
        activeEntryId: 'across-1',
      },
      app,
    );
    await recorder.eventChain;
    app.activeDirection = 'down';
    recorder.focus(app.crossword[1], app, 'pointer');
    await recorder.eventChain;

    expect(recorder.session.events.at(-1).visiblePattern[0]).toMatchObject({
      cellId: 'r0c0',
      token: 'C',
      origin: 'crossing',
      sourceEntryId: 'across-1',
    });
    recorder.dispose();
  });

  it('keeps unknown input unknown and uses the pre-move source clue', async () => {
    const app = puzzleApp();
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(app),
      repository: repository(),
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    recorder.scheduleFlush = vi.fn();
    await recorder.start();
    app.activeDirection = 'down';
    app.activeClueNumber = 1;
    app.grid[0][0] = 'X';
    recorder.cellChanged(
      {
        row: 0,
        column: 0,
        beforeToken: null,
        afterToken: 'X',
        source: 'unknown',
        activeEntryId: 'across-1',
      },
      app,
    );
    await recorder.eventChain;
    recorder.focus(app.crossword[1], app, 'pointer');
    await recorder.eventChain;

    expect(
      recorder.session.events.find((event) => event.type === 'cell-written'),
    ).toMatchObject({ activeEntryId: 'across-1' });
    expect(recorder.session.events.at(-1).visiblePattern[0]).toMatchObject({
      origin: 'unknown',
      sourceEntryId: null,
    });
    recorder.dispose();
  });

  it('restores an active offline journal before adding resume events', async () => {
    const repo = repository();
    const firstApp = puzzleApp();
    const first = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(firstApp),
      repository: repo,
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    first.scheduleFlush = vi.fn();
    await first.start(firstApp);
    firstApp.grid[0][0] = 'C';
    first.cellChanged(
      {
        row: 0,
        column: 0,
        beforeToken: null,
        afterToken: 'C',
        source: 'keyboard',
        activeEntryId: 'across-1',
      },
      firstApp,
    );
    firstApp.grid[0][1] = 'A';
    first.cellChanged(
      {
        row: 0,
        column: 1,
        beforeToken: null,
        afterToken: 'A',
        source: 'keyboard',
        activeEntryId: 'across-1',
      },
      firstApp,
    );
    firstApp.grid[0][2] = 'T';
    first.cellChanged(
      {
        row: 0,
        column: 2,
        beforeToken: null,
        afterToken: 'T',
        source: 'keyboard',
        activeEntryId: 'across-1',
      },
      firstApp,
    );
    await first.eventChain;
    first.checked(firstApp);
    await first.eventChain;
    firstApp.completedWords.add('Feline');
    const oldSessionId = first.session.sessionId;
    first.dispose();

    const resumedApp = puzzleApp();
    const resumed = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(resumedApp),
      repository: repo,
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    resumed.scheduleFlush = vi.fn();
    await resumed.start(resumedApp);
    expect(resumed.session.sessionId).toBe(oldSessionId);
    expect(resumedApp.grid[0]).toEqual(['C', 'A', 'T']);
    expect(resumedApp.completedWords.has('Feline')).toBe(true);
    expect(resumed.session.events.at(-1)).toMatchObject({
      type: 'session-resumed',
      snapshotSeq: 0,
    });
    resumedApp.activeDirection = 'down';
    resumed.focus(resumedApp.crossword[1], resumedApp, 'pointer');
    await resumed.eventChain;
    expect(resumed.session.events.at(-1).visiblePattern[0]).toMatchObject({
      origin: 'crossing',
      sourceEntryId: 'across-1',
    });
    resumed.dispose();
  });

  it('does not restore a pending old session into a replacement puzzle', async () => {
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app, 'ef'.repeat(32));
    const puzzle = describeLegacyPuzzle(app);
    const repo = repository();
    const first = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repo,
      fetchImpl: vi.fn(),
      cryptoApi: webcrypto,
    });
    first.scheduleFlush = vi.fn();
    await first.start(app);
    app.grid[0][0] = 'C';
    first.cellChanged(
      {
        row: 0,
        column: 0,
        beforeToken: null,
        afterToken: 'C',
        source: 'keyboard',
        activeEntryId: 'across-1',
      },
      app,
    );
    await first.eventChain;
    first.dispose();

    let releaseList;
    const listGate = new Promise((resolve) => {
      releaseList = resolve;
    });
    const delayedRepo = { ...repo, list: vi.fn(() => listGate) };
    const replacement = puzzleApp();
    replacement.currentPuzzleManifest = manifestFor(
      replacement,
      '12'.repeat(32),
    );
    const stale = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: delayedRepo,
      fetchImpl: vi.fn(),
      cryptoApi: webcrypto,
    });
    stale.scheduleFlush = vi.fn();
    const starting = stale.start(replacement);
    replacement.currentPuzzleMetadata.date = '260927';
    replacement.grid[0][0] = 'Z';
    releaseList(await repo.list('profile-1'));
    await starting;

    expect(stale.session.events.at(-1).type).toBe('session-resumed');
    expect(replacement.grid[0][0]).toBe('Z');
    stale.dispose();
  });

  it('cancels startup after dispose and makes later event callbacks inert', async () => {
    let releaseList;
    const listGate = new Promise((resolve) => {
      releaseList = resolve;
    });
    const base = repository();
    const repo = { ...base, list: vi.fn(() => listGate) };
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app);
    const puzzle = describeLegacyPuzzle(app);
    const fetchImpl = vi.fn();
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repo,
      fetchImpl,
      cryptoApi: webcrypto,
    });
    const starting = recorder.start(app);
    const queued = recorder.emit({
      type: 'visibility-changed',
      visibility: 'hidden',
    });
    recorder.dispose();
    releaseList([]);
    await starting;
    expect(await queued).toBeNull();
    expect(
      await recorder.emit({
        type: 'visibility-changed',
        visibility: 'visible',
      }),
    ).toBeNull();
    expect(recorder.session).toBeNull();
    expect(base.records.size).toBe(0);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it('uploads a completed offline journal after reload', async () => {
    const repo = repository();
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app);
    const puzzle = describeLegacyPuzzle(app);
    const offline = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repo,
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    offline.scheduleFlush = vi.fn();
    await offline.start();
    await offline.finish('complete');
    const finishedSeq = offline.session.events.length;
    offline.dispose();

    const server = host();
    const restored = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repo,
      fetchImpl: server.fetchImpl,
      cryptoApi: webcrypto,
    });
    restored.scheduleFlush = vi.fn();
    await restored.start();
    await restored.flush();
    expect(restored.session.status).toBe('finished');
    expect(restored.session.events.at(-1).type).toBe('session-finished');
    expect(restored.session.acknowledgedSeq).toBe(finishedSeq);
    restored.dispose();
  });

  it('starts a fresh journal for an explicit replacement with the same puzzle hash', async () => {
    const repo = repository();
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app, 'ab'.repeat(32));
    const puzzle = describeLegacyPuzzle(app);
    const first = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle,
      repository: repo,
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    first.scheduleFlush = vi.fn();
    await first.start(app);
    await first.finish('complete');
    const finishedId = first.session.sessionId;
    first.dispose();

    const replacementApp = puzzleApp();
    replacementApp.currentPuzzleManifest = manifestFor(replacementApp, 'ab'.repeat(32));
    const replacement = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(replacementApp),
      repository: repo,
      forceNewSession: true,
      fetchImpl: async () => {
        throw new Error('offline');
      },
      cryptoApi: webcrypto,
    });
    replacement.scheduleFlush = vi.fn();
    await replacement.start();

    expect(replacement.session.sessionId).not.toBe(finishedId);
    expect(replacement.session.status).toBe('active');
    expect(replacement.session.events.at(-1).type).toBe('session-started');
    replacement.dispose();
  });

  it('splits large offline backlogs into host-sized event batches', async () => {
    const app = puzzleApp();
    app.currentPuzzleManifest = manifestFor(app);
    const recorder = new FutureSessionRecorder({
      profileId: 'profile-1',
      puzzle: describeLegacyPuzzle(app),
      repository: repository(),
      fetchImpl: host().fetchImpl,
      cryptoApi: webcrypto,
    });
    const server = host();
    recorder.fetchImpl = server.fetchImpl;
    recorder.scheduleFlush = vi.fn();
    await recorder.start();
    for (let index = 0; index < 205; index++) {
      await recorder.emit({
        type: 'visibility-changed',
        visibility: index % 2 ? 'hidden' : 'visible',
      });
    }
    await recorder.flush();
    const batches = server.calls.filter((call) => call.url.endsWith('/events'));
    expect(batches.map((call) => call.body.events.length)).toEqual([200, 6]);
    expect(recorder.session.acknowledgedSeq).toBe(206);
    recorder.dispose();
  });
});
