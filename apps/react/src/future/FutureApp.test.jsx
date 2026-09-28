// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const { journalRecords } = vi.hoisted(() => ({ journalRecords: new Map() }));

vi.mock('./calibrationJournal', () => {
  const copy = (value) => JSON.parse(JSON.stringify(value));
  return {
    CalibrationJournalStorageError: class CalibrationJournalStorageError extends Error {
      constructor(code, message, cause, current) {
        super(message, cause === undefined ? undefined : { cause });
        this.code = code;
        this.current = current;
      }
    },
    createCalibrationJournalStore: () => ({
      async load(id) {
        return journalRecords.get(id) ?? null;
      },
      async restoreHost(session, { etag, revision }) {
        const current = journalRecords.get(session.calibrationId);
        if (current) return current;
        const restored = {
          session: copy(session),
          revision,
          hostRevision: revision,
          etag,
          syncStatus: 'saved',
        };
        journalRecords.set(session.calibrationId, restored);
        return copy(restored);
      },
      async save(session, { expectedRevision }) {
        const prior = journalRecords.get(session.calibrationId);
        const revision = prior?.revision ?? 0;
        if (revision !== expectedRevision) {
          throw new Error('Unexpected in-memory journal revision in UI test.');
        }
        const saved = {
          session: copy(session),
          revision: revision + 1,
          hostRevision: prior?.hostRevision ?? 0,
          etag: prior?.etag ?? null,
          syncStatus: 'pending',
        };
        journalRecords.set(session.calibrationId, saved);
        return copy(saved);
      },
      async markHostSynced(id, metadata) {
        const prior = journalRecords.get(id);
        if (!prior || prior.etag !== metadata.expectedEtag) {
          throw new Error('Unexpected in-memory journal ETag in UI test.');
        }
        const saved = {
          ...prior,
          etag: metadata.etag,
          hostRevision: metadata.syncedRevision,
          syncStatus:
            prior.revision === metadata.syncedRevision ? 'saved' : 'pending',
        };
        journalRecords.set(id, saved);
        return copy(saved);
      },
      async markHostConflict(id, metadata) {
        const prior = journalRecords.get(id);
        const saved = { ...prior, etag: metadata.etag, syncStatus: 'conflict' };
        journalRecords.set(id, saved);
        return copy(saved);
      },
      async close() {},
    }),
  };
});

import FutureApp from './FutureApp';
import { catalog, freshDraft, STORAGE_KEY } from './episteme';
import {
  appendCalibrationObservation,
  createInitialCalibrationSession,
} from './calibrationRuntime';
import {
  CALIBRATION_SELECTOR_VERSION_V1,
  CALIBRATION_SELECTOR_VERSION_V2,
  seededShuffle,
} from './calibrationPresentation.js';

if (!HTMLDialogElement.prototype.showModal) {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
    configurable: true,
    value() {
      this.setAttribute('open', '');
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', {
    configurable: true,
    value() {
      this.removeAttribute('open');
    },
  });
}

vi.mock('./FutureSolver', () => ({
  default: ({ weekday }) => <div data-testid="solver">{weekday}</div>,
}));

let root;
let host;
let hostCalibrationWrites;
let hostRecoverySession;
let hostHypothesisDeck;
let hostHypothesisResponses;
let hostHypothesisGenerations;
const fixedUpdatedAt = '2026-09-26T12:00:00.000Z';
const hypothesisFixture = {
  deckId: 'deck-opening-1',
  items: [
    {
      proposalId: 'path-echo-door',
      phrase: 'An echo might open a door.',
      relation: 'Echo / reply',
      connection: 'A kept word and a chosen shape appeared near each other.',
      ambiguity: 'The overlap may be incidental; there is no single reading.',
      sourceObservationIds: ['observation-1'],
    },
  ],
};

function response({ ok = true, status = 200, body = {}, etag = null } = {}) {
  return {
    ok,
    status,
    json: async () => body,
    headers: { get: (name) => (name.toLowerCase() === 'etag' ? etag : null) },
  };
}

function mockDefaultFetch(url, options = {}) {
  const path = new URL(String(url), 'http://localhost').pathname;
  const hypothesisPath = path.match(
    /^\/api\/future\/calibrations\/([^/]+)\/hypotheses(?:\/([^/]+)(?:\/responses\/([^/]+)\/actions|\/response))?$/,
  );
  if (hypothesisPath) {
    if (options.method === 'POST' && path.endsWith('/hypotheses')) {
      hostHypothesisGenerations += 1;
      hostHypothesisDeck = hypothesisFixture;
      hostHypothesisResponses = {};
      return Promise.resolve(
        response({
          body: { deck: hostHypothesisDeck, responses: hostHypothesisResponses },
        }),
      );
    }
    if (options.method === 'POST' && path.endsWith('/response')) {
      const proposalId = decodeURIComponent(hypothesisPath[2]);
      const payload = JSON.parse(options.body);
      hostHypothesisResponses[proposalId] = {
        response: payload.response,
        responseId: payload.responseId,
        active: true,
      };
      return Promise.resolve(
        response({
          body: { deck: hostHypothesisDeck, responses: hostHypothesisResponses },
        }),
      );
    }
    if (options.method === 'POST' && path.endsWith('/actions')) {
      const proposalId = decodeURIComponent(hypothesisPath[2]);
      const responseId = decodeURIComponent(hypothesisPath[3]);
      const payload = JSON.parse(options.body);
      if (hostHypothesisResponses[proposalId]?.responseId === responseId) {
        hostHypothesisResponses[proposalId].active = payload.action === 'restore';
      }
      return Promise.resolve(
        response({
          body: { deck: hostHypothesisDeck, responses: hostHypothesisResponses },
        }),
      );
    }
    if (hostHypothesisDeck) {
      return Promise.resolve(
        response({
          body: { deck: hostHypothesisDeck, responses: hostHypothesisResponses },
        }),
      );
    }
    return Promise.resolve(response({ ok: false, status: 404 }));
  }
  if (path.startsWith('/api/future/calibrations/') && options.method === 'PUT') {
    hostCalibrationWrites.push(JSON.parse(options.body));
    return Promise.resolve(
      response({ etag: `"cal-${hostCalibrationWrites.length}"` }),
    );
  }
  if (path.startsWith('/api/future/calibrations/') && !options.method) {
    if (hostRecoverySession?.calibrationId === path.split('/').at(-1)) {
      return Promise.resolve(
        response({
          body: { calibration: hostRecoverySession, revision: 4 },
          etag: '"cal-4"',
        }),
      );
    }
    return Promise.resolve(response({ ok: false, status: 404 }));
  }
  if (path.startsWith('/api/future/profile/') && options.method === 'PUT') {
    return Promise.resolve(response({ body: { updatedAt: fixedUpdatedAt } }));
  }
  if (path.startsWith('/api/future/profile/') && options.method === 'GET') {
    return Promise.resolve(response({ body: { draft: null, updatedAt: fixedUpdatedAt } }));
  }
  return Promise.resolve(response({ body: { profile: {}, updatedAt: fixedUpdatedAt } }));
}

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  hostCalibrationWrites = [];
  hostRecoverySession = null;
  hostHypothesisDeck = null;
  hostHypothesisResponses = {};
  hostHypothesisGenerations = 0;
  journalRecords.clear();
  vi.stubGlobal('fetch', vi.fn(mockDefaultFetch));
  localStorage.clear();
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

const mount = () => act(async () => root.render(<FutureApp />));
const button = (text) =>
  [...host.querySelectorAll('button')].find(
    (item) => item.textContent.trim() === text,
  );
const byAccessibleName = (label) =>
  [...host.querySelectorAll('[aria-label]')].find(
    (item) => item.getAttribute('aria-label') === label,
  );
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const click = async (element) => {
  if (!element) throw new Error('The requested UI control was not found.');
  await act(async () => {
    element.click();
    await flush();
    await flush();
  });
};
async function waitFor(predicate, message = 'Expected UI state was not reached.') {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (predicate()) return;
    await act(flush);
  }
  throw new Error(
    `${message} Heading: ${host.querySelector('h1')?.textContent}; status: ${host.querySelector('.future-calibration-status')?.textContent}; alert: ${host.querySelector('[role="alert"]')?.textContent}`,
  );
}
const accessibleLabelForLegacyId = (legacyId) =>
  catalog.stimuli.items.find((item) => item.legacy_ids?.includes(legacyId))
    ?.accessible_label;

async function reachPreview() {
  await mount();
  await click(byAccessibleName(accessibleLabelForLegacyId('thread')));
  await click(button('Continue'));
  await waitFor(() => host.querySelector('h1')?.textContent.includes('What belongs beside it?'));
  await click(button('Let this one pass'));
  await click(button('Let this one pass'));
  await click(button('Let this one pass'));
  await click(button('See your beginning'));
  await waitFor(() => host.querySelector('h1')?.textContent.includes('A beginning,'));
  await waitFor(() => {
    const trace = host.querySelector('.future-hypotheses-invitation button');
    return trace && !trace.disabled;
  });
}

it('records all five calibration movements, restores progress, and keeps raw evidence separate from the profile', async () => {
  await mount();
  expect(button('Continue').disabled).toBe(true);
  expect(host.querySelectorAll('.future-object-grid .future-object')).toHaveLength(12);
  expect(
    [...host.querySelectorAll('.future-object-index')].map((node) =>
      node.textContent.trim(),
    ),
  ).toEqual([
    '01',
    '02',
    '03',
    '04',
    '05',
    '06',
    '07',
    '08',
    '09',
    '10',
    '11',
    '12',
  ]);

  await click(byAccessibleName(accessibleLabelForLegacyId('thread')));
  await click(button('Continue'));
  await waitFor(() => host.querySelector('h1')?.textContent.includes('What belongs beside it?'));
  expect(host.querySelector('h1').textContent).toContain('What belongs beside it?');
  await click(byAccessibleName(accessibleLabelForLegacyId('fork')));
  await click(button('Continue'));
  await waitFor(() => host.querySelector('h1')?.textContent.includes('One small change.'));
  expect(host.querySelector('h1').textContent).toContain('One small change.');
  await click(button('Keep the original'));
  await click(button('Continue'));
  await waitFor(() => host.querySelector('h1')?.textContent.includes('A little residue.'));

  await click(byAccessibleName(accessibleLabelForLegacyId('echo')));
  await click(byAccessibleName(accessibleLabelForLegacyId('moss')));
  expect(byAccessibleName(accessibleLabelForLegacyId('salt')).disabled).toBe(true);
  await click(button('Continue'));
  await waitFor(() => host.querySelector('h1')?.textContent.includes('Choose your rhythm.'));
  expect(host.querySelector('h1').textContent).toContain('Choose your rhythm.');
  await click(byAccessibleName('Thursday'));
  expect(JSON.parse(localStorage.getItem(STORAGE_KEY)).weekday).toBe('thursday');

  await act(async () => root.unmount());
  root = createRoot(host);
  await mount();
  expect(host.querySelector('h1').textContent).toContain('Choose your rhythm.');
  await click(button('See your beginning'));
  expect(host.querySelector('h1').textContent).toContain('A beginning,');
  await click(button('tension×'));
  expect(button('tension+').getAttribute('aria-pressed')).toBe('false');
  await click(button('Enter crossword'));
  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  expect(host.querySelector('[data-testid="solver"]').textContent).toBe('thursday');

  const profileWrites = fetch.mock.calls.filter(
    ([url, options]) =>
      new URL(String(url), 'http://localhost').pathname.startsWith('/api/future/profile/') &&
      options?.method === 'PUT',
  );
  const saved = JSON.parse(profileWrites.at(-1)[1].body);
  expect(saved).toMatchObject({
    object: 'thread',
    firstStimulus: expect.any(String),
    companion: 'fork',
    traces: ['echo', 'moss'],
    weekday: 'thursday',
    complete: true,
  });
  expect(saved).not.toHaveProperty('observations');
  expect(saved).not.toHaveProperty('actions');
  expect(saved).not.toHaveProperty('offered');

  const journal = journalRecords.get(saved.calibrationId).session;
  expect(journal).toMatchObject({
    status: 'completed',
    currentMovement: 5,
    selectorVersion: CALIBRATION_SELECTOR_VERSION_V2,
  });
  expect(journal.observations.map((event) => event.movement)).toEqual([1, 2, 3, 4]);
  expect(journal.observations[0].offered).toHaveLength(12);
  expect(journal.observations[3].response.kind).toBe('choose');
  expect(journal.observations[3].response.chosenIds).toEqual(
    expect.arrayContaining([
      catalog.stimuli.items.find((item) => item.legacy_ids?.includes('echo')).id,
      catalog.stimuli.items.find((item) => item.legacy_ids?.includes('moss')).id,
    ]),
  );
  expect(hostCalibrationWrites.at(-1).status).toBe('completed');
  expect(localStorage.getItem('selectedWeekday')).toBeNull();
});

it('creates hypotheses only after opt-in, saves a response, and restores it on reload and in the profile', async () => {
  await reachPreview();
  expect(hostHypothesisGenerations).toBe(0);
  expect(host.querySelector('.future-hypothesis-list')).toBeNull();

  await click(host.querySelector('.future-hypotheses-invitation button'));
  await waitFor(() => host.querySelector('.future-hypothesis-card'));
  expect(hostHypothesisGenerations).toBe(1);
  expect(host.querySelector('.future-hypothesis-phrase').textContent).toBe(
    hypothesisFixture.items[0].phrase,
  );
  expect(host.querySelector('.future-hypothesis-reading').textContent).toContain(
    'The overlap may be incidental; there is no single reading.',
  );
  expect(
    fetch.mock.calls.filter(
      ([url, options]) =>
        new URL(String(url), 'http://localhost').pathname.endsWith('/hypotheses') &&
        options?.method === 'POST',
    ),
  ).toHaveLength(1);

  await click(button('Keep this thread'));
  await waitFor(() =>
    host.querySelector('.future-hypothesis-state')?.textContent.includes('You kept this possible path'),
  );
  expect(hostHypothesisResponses['path-echo-door']).toMatchObject({
    response: 'keep',
    active: true,
  });
  const responseWrite = fetch.mock.calls.find(
    ([url, options]) =>
      new URL(String(url), 'http://localhost').pathname.endsWith('/path-echo-door/response') &&
      options?.method === 'POST',
  );
  expect(JSON.parse(responseWrite[1].body)).toMatchObject({
    response: 'keep',
    deckId: 'deck-opening-1',
  });

  await act(async () => root.unmount());
  root = createRoot(host);
  await mount();
  await waitFor(() =>
    host.querySelector('.future-hypothesis-state')?.textContent.includes('You kept this possible path'),
  );
  expect(hostHypothesisGenerations).toBe(1);
  expect(
    fetch.mock.calls.some(
      ([url, options]) =>
        new URL(String(url), 'http://localhost').pathname.endsWith('/hypotheses') &&
        !options?.method,
    ),
  ).toBe(true);

  await click(button('Enter crossword'));
  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  await click(host.querySelector('.future-header .future-text-button'));
  const profileDialog = host.querySelector('.future-profile-dialog');
  expect(profileDialog.textContent).toContain(hypothesisFixture.items[0].phrase);
  expect(profileDialog.textContent).toContain(
    'You kept this possible path for now.',
  );
});

it('keeps Preview playable when the local hypothesis model is unavailable', async () => {
  let generationRequests = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn((url, options = {}) => {
      const path = new URL(String(url), 'http://localhost').pathname;
      if (
        path.endsWith('/hypotheses') &&
        options.method === 'POST'
      ) {
        generationRequests += 1;
        return Promise.resolve(
          response({
            ok: false,
            status: 503,
            body: { error: 'The local model is unavailable.' },
          }),
        );
      }
      return mockDefaultFetch(url, options);
    }),
  );

  await reachPreview();
  await click(host.querySelector('.future-hypotheses-invitation button'));
  await waitFor(() =>
    host.querySelector('[role="alert"]')?.textContent.includes('The local model is unavailable.'),
  );
  expect(generationRequests).toBe(1);
  expect(host.querySelector('h1').textContent).toContain('A beginning,');
  expect(button('Enter crossword').disabled).toBe(false);
  await click(button('Enter crossword'));
  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  expect(host.querySelector('[data-testid="solver"]')).not.toBeNull();
});

it('keeps path generation unavailable when the opening was skipped', async () => {
  await mount();
  await click(button('Go straight to a puzzle'));
  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  await click(host.querySelector('.future-header .future-text-button'));

  const invitation = host.querySelector('.future-hypotheses-invitation');
  expect(invitation.textContent).toContain(
    'Choose at least one sign in the opening to trace a path.',
  );
  expect(invitation.querySelector('button').disabled).toBe(true);
  expect(hostHypothesisGenerations).toBe(0);
});

it('lets a playing profile steer the next personal crossword without restarting setup', async () => {
  await mount();
  await click(button('Go straight to a puzzle'));
  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  await click(host.querySelector('.future-header .future-text-button'));

  const difficulty = byAccessibleName('Next crossword difficulty');
  const language = byAccessibleName('Learning thread');
  const model = byAccessibleName('Saved local writing model');
  expect(difficulty).not.toBeNull();
  expect(language).not.toBeNull();
  expect(model).not.toBeNull();

  await act(async () => {
    difficulty.value = 'thursday';
    difficulty.dispatchEvent(new Event('change', { bubbles: true }));
    language.value = 'German';
    language.dispatchEvent(new Event('change', { bubbles: true }));
    model.value = 'qwen3.8:27b';
    model.dispatchEvent(new Event('change', { bubbles: true }));
    await flush();
  });
  await click(button('Save changes'));

  const profileWrites = fetch.mock.calls.filter(
    ([url, options]) =>
      new URL(String(url), 'http://localhost').pathname.startsWith('/api/future/profile/') &&
      options?.method === 'PUT',
  );
  const saved = JSON.parse(profileWrites.at(-1)[1].body);
  expect(saved).toMatchObject({
    weekday: 'thursday',
    learningLanguage: 'German',
    modelPreference: 'qwen3.8:27b',
    complete: true,
  });
  expect(host.textContent).toContain('Writing model · Qwen 3.8 27B');
  expect(host.querySelector('[data-testid="solver"]').textContent).toBe('thursday');
});

it('keeps the empty hypothesis state quiet when a skipped opening is reloaded', async () => {
  let emptyDeckReads = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn((url, options = {}) => {
      const path = new URL(String(url), 'http://localhost').pathname;
      if (path.endsWith('/hypotheses') && !options.method) {
        emptyDeckReads += 1;
        return Promise.resolve(
          response({
            ok: false,
            status: 409,
            body: { error: 'The calibration has no active choices.' },
          }),
        );
      }
      return mockDefaultFetch(url, options);
    }),
  );

  await mount();
  await click(button('Go straight to a puzzle'));
  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  expect(emptyDeckReads).toBe(0);

  await act(async () => root.unmount());
  root = createRoot(host);
  await mount();
  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  await click(host.querySelector('.future-header .future-text-button'));

  const invitation = host.querySelector('.future-hypotheses-invitation');
  expect(invitation.textContent).toContain(
    'Choose at least one sign in the opening to trace a path.',
  );
  expect(invitation.querySelector('button').disabled).toBe(true);
  expect(invitation.querySelector('[role="alert"]')).toBeNull();
  expect(emptyDeckReads).toBe(0);
});

it('recovers a calibration from the host when the local journal is empty', async () => {
  const profile = {
    ...freshDraft(),
    id: '4e1091f5-e7ea-48cd-8f99-b56151f8c20f',
    calibrationId: 'e4cab20a-c164-45c2-8d4e-c2fe07e75f7a',
  };
  const first = catalog.stimuli.items.find((item) =>
    item.legacy_ids?.includes('thread'),
  );
  const offered = catalog.stimuli.items.slice(0, 12).map((item, position) => ({
    stimulusId: item.id,
    stimulusVersion: String(item.version),
    position,
  }));
  const initial = {
    ...createInitialCalibrationSession({
      draft: profile,
      now: fixedUpdatedAt,
    }),
    selectorVersion: CALIBRATION_SELECTOR_VERSION_V1,
  };
  hostRecoverySession = appendCalibrationObservation(
    initial,
    {
      movement: 1,
      offered,
      response: { kind: 'choose', chosenIds: [first.id] },
      presentedAt: fixedUpdatedAt,
      nextMovement: 2,
    },
    { now: '2026-09-26T12:00:01.000Z' },
  );
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));

  await mount();
  await waitFor(() => host.querySelector('h1')?.textContent.includes('What belongs beside it?'));
  expect(byAccessibleName(accessibleLabelForLegacyId('fork'))).toBeTruthy();
  const thread = catalog.objects.find(({ id }) => id === 'thread');
  const companionStimuli = thread.companions
    .map((legacyId) =>
      catalog.stimuli.items.find((item) => item.legacy_ids?.includes(legacyId)),
    )
    .filter(Boolean);
  const movementSeed =
    (initial.seed + Math.imul(2, 0x9e3779b9)) >>> 0;
  expect(
    [...host.querySelectorAll('.future-companion-grid .future-object')].map(
      (choice) => choice.getAttribute('aria-label'),
    ),
  ).toEqual(
    seededShuffle(
      companionStimuli,
      movementSeed,
      CALIBRATION_SELECTOR_VERSION_V1,
    ).map((item) => item.accessible_label),
  );
  expect(journalRecords.get(profile.calibrationId)).toMatchObject({
    revision: 4,
    hostRevision: 4,
    etag: '"cal-4"',
    syncStatus: 'saved',
  });
  expect(journalRecords.get(profile.calibrationId).session.selectorVersion).toBe(
    CALIBRATION_SELECTOR_VERSION_V1,
  );
  expect(JSON.parse(localStorage.getItem(STORAGE_KEY))).toMatchObject({
    calibrationId: profile.calibrationId,
    firstStimulus: first.id,
    object: 'thread',
    step: 1,
  });
});

it('guides an incompatible calibration branch without rewriting its raw journal', async () => {
  const profile = {
    ...freshDraft(),
    id: '4e1091f5-e7ea-48cd-8f99-b56151f8c20f',
    calibrationId: 'e4cab20a-c164-45c2-8d4e-c2fe07e75f7a',
    weekday: 'thursday',
    learningLanguage: 'German',
  };
  const session = createInitialCalibrationSession({
    draft: profile,
    now: fixedUpdatedAt,
  });
  const conflictRecord = {
    session,
    revision: 4,
    hostRevision: 3,
    etag: '"cal-3"',
    syncStatus: 'conflict',
  };
  journalRecords.set(profile.calibrationId, conflictRecord);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));

  await mount();
  await waitFor(() => host.querySelector('.future-calibration-recovery'));
  expect(host.textContent).toContain('This opening has two branches.');
  expect(host.textContent).toContain('Your choices are still safe on this device.');

  await click(button('Keep this opening here'));
  expect(host.textContent).toContain('Its saved branch remains separate');
  expect(journalRecords.get(profile.calibrationId)).toEqual(conflictRecord);

  // The second action starts a new journal pointer, while the old append-only
  // record remains available for later review or explicit archival.
  await click(button('Start a fresh opening'));
  await waitFor(() => host.querySelector('h1')?.textContent.includes('Before the words'));
  const next = JSON.parse(localStorage.getItem(STORAGE_KEY));
  expect(next).toMatchObject({
    id: profile.id,
    weekday: 'thursday',
    learningLanguage: 'German',
    complete: false,
    step: 0,
  });
  expect(next.calibrationId).not.toBe(profile.calibrationId);
  expect(journalRecords.get(profile.calibrationId)).toEqual(conflictRecord);
});

it('reconciles a lost first sync response when the host has an append-only prefix', async () => {
  let remoteRevision = 0;
  const writes = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((url, options = {}) => {
      const path = new URL(String(url), 'http://localhost').pathname;
      if (path.startsWith('/api/future/calibrations/') && !options.method) {
        return Promise.resolve(
          hostRecoverySession
            ? response({
                body: {
                  calibration: hostRecoverySession,
                  revision: remoteRevision,
                },
                etag: `"cal-${remoteRevision}"`,
              })
            : response({ ok: false, status: 404 }),
        );
      }
      if (
        path.startsWith('/api/future/calibrations/') &&
        options.method === 'PUT'
      ) {
        const candidate = JSON.parse(options.body);
        writes.push({ candidate, headers: options.headers });
        if (writes.length === 1) {
          hostRecoverySession = candidate;
          remoteRevision = 1;
          return Promise.reject(new Error('The response was lost after commit.'));
        }
        if (options.headers['If-None-Match'] === '*')
          return Promise.resolve(
            response({ ok: false, status: 409, etag: '"cal-1"' }),
          );
        if (options.headers['If-Match'] === `"cal-${remoteRevision}"`) {
          hostRecoverySession = candidate;
          remoteRevision += 1;
          return Promise.resolve(response({ etag: `"cal-${remoteRevision}"` }));
        }
        return Promise.resolve(
          response({ ok: false, status: 409, etag: `"cal-${remoteRevision}"` }),
        );
      }
      return mockDefaultFetch(url, options);
    }),
  );
  await mount();
  await click(byAccessibleName(accessibleLabelForLegacyId('thread')));
  await click(button('Continue'));
  await waitFor(() => host.querySelector('h1')?.textContent.includes('What belongs beside it?'));
  await click(byAccessibleName(accessibleLabelForLegacyId('fork')));
  await click(button('Continue'));
  await waitFor(
    () =>
      host.querySelector('.future-calibration-status')?.dataset.state ===
      'synced',
  );

  expect(writes).toHaveLength(3);
  expect(writes[0].headers['If-None-Match']).toBe('*');
  expect(writes[1].headers['If-None-Match']).toBe('*');
  expect(writes[2].headers['If-Match']).toBe('"cal-1"');
  expect(hostRecoverySession.observations.map((item) => item.movement)).toEqual([
    1, 2,
  ]);
});

it('supports pass and revision, then enters with the local host unavailable', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url, options = {}) => {
      const path = new URL(String(url), 'http://localhost').pathname;
      if (path.startsWith('/api/future/')) return Promise.reject(new Error('offline'));
      return mockDefaultFetch(url, options);
    }),
  );
  await mount();
  await click(byAccessibleName(accessibleLabelForLegacyId('thread')));
  await click(button('Continue'));
  await click(button('Let this one pass'));
  await click(button('Back'));
  expect(host.querySelector('h1').textContent).toContain('What belongs beside it?');
  await click(byAccessibleName(accessibleLabelForLegacyId('fork')));
  await click(button('Continue'));
  await click(button('Keep the original'));
  await click(button('Continue'));
  await click(button('Let this one pass'));
  await click(byAccessibleName('Thursday'));
  await click(button('See your beginning'));
  await waitFor(() => host.querySelector('h1')?.textContent.includes('A beginning,'));
  await click(button('Enter crossword'));

  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  expect(JSON.parse(localStorage.getItem(STORAGE_KEY))).toMatchObject({
    complete: true,
    object: 'thread',
    companion: 'fork',
    traces: [],
    weekday: 'thursday',
  });
  const journal = journalRecords.get(
    JSON.parse(localStorage.getItem(STORAGE_KEY)).calibrationId,
  ).session;
  expect(journal.status).toBe('completed');
  expect(journal.observations.at(-1)).toMatchObject({
    movement: 4,
    response: { kind: 'pass' },
  });
  expect(host.textContent).toContain('thursday');
});

it('retries the starting profile when the local host comes back online', async () => {
  let profilePuts = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn((url, options = {}) => {
      const path = new URL(String(url), 'http://localhost').pathname;
      if (path.startsWith('/api/future/profile/') && options.method === 'PUT') {
        profilePuts += 1;
        if (profilePuts === 1) return Promise.reject(new Error('offline'));
        return Promise.resolve(response({ body: { updatedAt: fixedUpdatedAt } }));
      }
      return mockDefaultFetch(url, options);
    }),
  );
  await mount();
  await click(button('Go straight to a puzzle'));
  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  expect(profilePuts).toBe(1);
  expect(host.textContent).toContain('The local server is unavailable.');

  await act(async () => {
    window.dispatchEvent(new Event('online'));
    await flush();
    await flush();
  });

  await waitFor(() => profilePuts === 2);
  expect(host.textContent).toContain('Saved on this device and your local server.');
});

it('uses profile ETags and recovers from a stale save without leaving the puzzle', async () => {
  const firstVersion = '2026-09-26T12:00:00.000Z';
  const latestVersion = '2026-09-26T12:05:00.000Z';
  let profileDraft;
  let profilePuts = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn((url, options = {}) => {
      const path = new URL(String(url), 'http://localhost').pathname;
      if (path.startsWith('/api/future/calibrations/') && options.method === 'PUT') {
        hostCalibrationWrites.push(JSON.parse(options.body));
        return Promise.resolve(
          response({ etag: `"cal-${hostCalibrationWrites.length}"` }),
        );
      }
      if (path.startsWith('/api/future/profile/') && options.method === 'PUT') {
        profilePuts += 1;
        if (!profileDraft) profileDraft = JSON.parse(options.body);
        if (profilePuts === 2) {
          return Promise.resolve(
            response({ ok: false, status: 409, body: { error: 'Profile changed elsewhere.' } }),
          );
        }
        return Promise.resolve(
          response({ body: { updatedAt: profilePuts === 1 ? firstVersion : latestVersion } }),
        );
      }
      if (path.startsWith('/api/future/profile/') && options.method !== 'PUT') {
        return Promise.resolve(
          response({ body: { draft: profileDraft, updatedAt: latestVersion } }),
        );
      }
      return Promise.resolve(response({ body: { profile: {}, updatedAt: latestVersion } }));
    }),
  );

  await mount();
  await click(button('Go straight to a puzzle'));
  await waitFor(() => host.querySelector('[data-testid="solver"]'));
  expect(profilePuts).toBe(1);
  const firstProfileWrite = fetch.mock.calls.find(
    ([url, options]) =>
      new URL(String(url), 'http://localhost').pathname.startsWith('/api/future/profile/') &&
      options?.method === 'PUT',
  );
  expect(firstProfileWrite[1].headers).toMatchObject({ 'If-None-Match': '*' });

  await click(host.querySelector('.future-header .future-text-button'));
  await click(button('Save changes'));
  expect(host.textContent).toContain('changed on the local server');
  const profileWrites = fetch.mock.calls.filter(
    ([url, options]) =>
      new URL(String(url), 'http://localhost').pathname.startsWith('/api/future/profile/') &&
      options?.method === 'PUT',
  );
  expect(profileWrites[1][1].headers).toMatchObject({
    'If-Match': `"${firstVersion}"`,
  });

  await click(button('Load latest saved beginning'));
  await waitFor(() =>
    JSON.parse(localStorage.getItem(STORAGE_KEY)).profileUpdatedAt === latestVersion,
  );
  expect(host.querySelector('[data-testid="solver"]')).not.toBeNull();

  await click(button('Save changes'));
  await waitFor(() => profilePuts === 3);
  const finalProfileWrite = fetch.mock.calls.filter(
    ([url, options]) =>
      new URL(String(url), 'http://localhost').pathname.startsWith('/api/future/profile/') &&
      options?.method === 'PUT',
  )[2];
  expect(finalProfileWrite[1].headers).toMatchObject({
    'If-Match': `"${latestVersion}"`,
  });
  expect(host.textContent).toContain(
    'Saved on this device and your local server.',
  );
});
