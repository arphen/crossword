// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { webcrypto } from 'node:crypto';
import { afterEach, expect, it, vi } from 'vitest';
import PrivatePuzzleControls, {
  describeJobStage,
  describeStageElapsed,
  describePlayCalibration,
  describeThemeThread,
  describeLanguageTokenThread,
  describeLanguageRecurrence,
  describeLanguageTaskSources,
  describePersonalizationReceipt,
  personalizationReceiptFacts,
  describeWeekdayRecipe,
  idempotencyKey,
  random31BitSeed,
  loadPendingPrivateJob,
  savePendingPrivateJob,
  clearPendingPrivateJob,
} from './PrivatePuzzleControls';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root;
let host;

function mount(app, props = {}) {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  act(() => {
    root.render(
      <PrivatePuzzleControls app={app} profileId="profile-1" profileReady {...props} />,
    );
  });
}

function appState(overrides = {}) {
  return {
    selectedWeekday: 'thursday',
    currentPuzzleMetadata: { date: '260927', title: 'Daily' },
    currentPuzzleManifest: null,
    currentPuzzleProvenance: null,
    crossword: [{ clue_text: 'Old clue' }],
    grid: [[null]],
    isValidPuzzle: vi.fn(() => true),
    init: vi.fn(),
    ...overrides,
  };
}

function privatePuzzlePayload() {
  return {
    metadata: {
      date: '260928',
      title: 'A personal crossword',
      authors: ['Local puzzle maker'],
    },
    entries: [{ clue_text: 'A new clue' }],
    puzzleManifest: { schemaVersion: 1, id: 'manifest-1' },
    provenance: {
      source: 'local-ollama-xfill',
      model: 'ollama-local',
      themeAnswers: ['KOFFI', 'ACCRA'],
    },
  };
}

function privateJobPayload(state = 'ready') {
  const puzzle = privatePuzzlePayload();
  return {
    id: 'job-1',
    state,
    playable: state === 'ready',
    result:
      state === 'ready'
        ? {
            puzzle: {
              metadata: puzzle.metadata,
              entries: puzzle.entries,
            },
            puzzleManifest: puzzle.puzzleManifest,
            provenance: puzzle.provenance,
          }
        : null,
  };
}

function privateLanguageTokenPayload() {
  return {
    metadata: {
      date: '260928',
      title: 'A language thread',
      authors: ['Local puzzle maker'],
      width: 4,
      height: 1,
    },
    entries: [
      {
        clue_number: 1,
        clue_text: 'Coffee, in French',
        direction: 'across',
        start_x: 0,
        start_y: 0,
        characters: ['C', 'A', 'F', 'E'].map((letters) => ({ letters })),
      },
    ],
    puzzleManifest: {
      schemaVersion: 1,
      integrity: { algorithm: 'sha256', value: 'c'.repeat(64) },
    },
    provenance: {
      source: 'local-ollama-xfill',
      model: 'ollama-local',
      languageInterest: 'fr',
      languageLearning: {
        code: 'fr',
        tokenHints: [
          { entryId: 'across-1', cellIndex: 3, displayToken: 'É' },
        ],
      },
    },
  };
}

function clickButton() {
  const button = host.querySelector('button');
  act(() => button.dispatchEvent(new MouseEvent('click', { bubbles: true })));
  return button;
}

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it('uses a secure source when available and always returns a 31-bit seed', () => {
  const cryptoApi = {
    getRandomValues: vi.fn((value) => {
      value[0] = 0xffffffff;
      return value;
    }),
  };
  expect(random31BitSeed(cryptoApi)).toBe(0x7fffffff);
  expect(cryptoApi.getRandomValues).toHaveBeenCalledOnce();
  expect(random31BitSeed({})).toBeGreaterThanOrEqual(0);
  expect(random31BitSeed({})).toBeLessThan(0x80000000);
});

it('keeps the job idempotency fallback in the UUID shape required by Flask', () => {
  const cryptoApi = {
    getRandomValues: vi.fn((value) => {
      value.fill(0xab);
      return value;
    }),
  };
  expect(idempotencyKey(cryptoApi)).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
  );
  expect(cryptoApi.getRandomValues).toHaveBeenCalledOnce();
});

it('stores pending worker identity in a profile-scoped recovery record', () => {
  const storage = new Map();
  const adapter = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: (key) => storage.delete(key),
  };
  const pending = {
    profileId: 'profile-1',
    jobId: 'job-1',
    seed: 42,
    weekday: 'thursday',
  };
  expect(savePendingPrivateJob('profile-1', pending, adapter)).toBe(true);
  expect(loadPendingPrivateJob('profile-1', adapter)).toMatchObject(pending);
  expect(loadPendingPrivateJob('profile-2', adapter)).toBeNull();
  expect(clearPendingPrivateJob('profile-1', 'other-job', adapter)).toBe(false);
  expect(clearPendingPrivateJob('profile-1', 'job-1', adapter)).toBe(true);
  expect(loadPendingPrivateJob('profile-1', adapter)).toBeNull();
});

it('gives each real worker stage a distinct, honest wait message', () => {
  expect(describeJobStage('queued')).toContain('Queued');
  expect(describeJobStage('reconnecting')).toContain('Reconnecting');
  expect(describeJobStage('theme-proposal')).toContain('thread');
  expect(describeJobStage('native-xfill')).toContain('crossings');
  expect(describeJobStage('clue-generation')).toContain('clues');
  expect(describeJobStage('clue-challenge')).toContain('second local pass');
  expect(describeJobStage('finalizing')).toContain('finished board');
  expect(describeJobStage('unexpected-stage')).toContain('Building');
});

it('formats only measured stage time for the wait status', () => {
  expect(describeStageElapsed(0)).toBe('');
  expect(describeStageElapsed(0.9)).toBe('');
  expect(describeStageElapsed(1)).toBe('1 second in this step');
  expect(describeStageElapsed(12.8)).toBe('12 seconds in this step');
  expect(describeStageElapsed('12')).toBe('');
});

it('describes the selected weekday recipe honestly', () => {
  expect(describeWeekdayRecipe('monday')).toContain('early footholds');
  expect(describeWeekdayRecipe('tuesday')).toContain('alternate senses');
  expect(describeWeekdayRecipe('wednesday')).toContain('fair misdirection');
  expect(describeWeekdayRecipe('thursday')).toContain('shared prefix or suffix');
  expect(describeWeekdayRecipe('thursday')).toContain('standard letter grid');
  expect(describeWeekdayRecipe('friday')).toContain('stronger long entries');
  expect(describeWeekdayRecipe('saturday')).toContain('densest fair challenge');
  expect(describeWeekdayRecipe('sunday')).toContain('21×21');
});

it('keeps play calibration copy limited to the three difficulty recommendations', () => {
  expect(describePlayCalibration({ recommendation: 'more-footholds' })).toBe(
    'Difficulty calibration only: more footholds.',
  );
  expect(describePlayCalibration({ recommendation: 'balanced' })).toBe(
    'Difficulty calibration only: balanced.',
  );
  expect(describePlayCalibration({ recommendation: 'gentle-stretch' })).toBe(
    'Difficulty calibration only: gentle stretch.',
  );
  expect(describePlayCalibration(null)).toBe('');
  expect(describePlayCalibration({ recommendation: 'unknown' })).toBe('');
});

it('describes a bounded personal theme thread from generated provenance', () => {
  expect(
    describeThemeThread({ themeAnswers: ['KOFFI', 'ACCRA', 'COFFEE', 'BEANS'] }),
  ).toBe('Personal thread: KOFFI · ACCRA · COFFEE · BEANS');
  expect(describeThemeThread({ themeAnswers: ['too-long-answer-xxxxxxxx'] })).toBe('');
  expect(describeThemeThread(null)).toBe('');
});

it('labels explicit language display forms without exposing the answer', () => {
  expect(
    describeLanguageTokenThread({
      languageLearning: {
        tokenHints: [{ entryId: 'across-1', cellIndex: 3, displayToken: 'É' }],
        tokenHintSource: 'synthetic-unadmitted',
      },
    }),
  ).toContain('experimental local display form');
  expect(
    describeLanguageTokenThread({
      languageLearning: {
        tokenHints: [{ entryId: 'across-1', cellIndex: 3, displayToken: 'É' }],
        tokenHintSource: 'reviewed-admitted',
      },
    }),
  ).toContain('admitted display form');
  expect(
    describeLanguageTokenThread({
      tokenConstruction: {
        hints: [{ entryId: 'across-1', cellIndex: 2, displayToken: 'ß' }],
      },
    }),
  ).toContain('experimental local display form');
  expect(describeLanguageTokenThread(null)).toBe('');
});

it('describes bounded scheduled language recurrence without exposing forms', () => {
  const text = describeLanguageRecurrence({
    languageLearning: {
      language: 'German',
      dueDetails: [
        { form: 'JA', reviewStage: 2, overdueHours: 4 },
        { form: 'NEIN', reviewStage: 1, overdueHours: 0 },
      ],
    },
  });
  expect(text).toContain('2 German recall threads');
  expect(text).toContain('review 2');
  expect(text).toContain('1 overdue');
  expect(text).not.toContain('JA');
  expect(describeLanguageRecurrence(null)).toBe('');
});

it('describes language task-pair provenance without exposing the target form', () => {
  const text = describeLanguageTaskSources({
    languageLearning: {
      language: 'French',
      taskPairSources: [
        {
          pairId: 'fr-en-oui-v1',
          reviewStatus: 'synthetic-unadmitted',
          sourceText: 'yes',
        },
      ],
    },
  });
  expect(text).toContain('1 French clue anchored to local task pairs');
  expect(text).toContain('source provenance');
  expect(text).not.toContain('OUI');
  expect(describeLanguageTaskSources(null)).toBe('');
});

it('describes the bounded profile revision receipt without exposing profile text', () => {
  expect(
    describePersonalizationReceipt({
      personalizationReceipt: {
        version: 'private-personalization-receipt-v1',
        epistemeRevision: 7,
        epistemeDigest: 'a'.repeat(64),
        inputs: {
          claimCount: 2,
          associationCount: 1,
          recentExposureCount: 3,
          languageThread: true,
          difficultyRecommendation: 'balanced',
        },
      },
    }),
  ).toBe(
    'Personalized from saved signals · open threads · recent word history · language thread · difficulty calibration · episteme revision 7',
  );
  expect(
    personalizationReceiptFacts({
      personalizationReceipt: {
        version: 'private-personalization-receipt-v1',
        epistemeRevision: 7,
        epistemeDigest: 'a'.repeat(64),
        inputs: {
          claimCount: 2,
          associationCount: 1,
          recentExposureCount: 3,
          languageThread: true,
          difficultyRecommendation: 'balanced',
        },
      },
    }),
  ).toEqual([
    '2 saved signals',
    '1 open thread',
    '3 recent exposures',
    'language thread',
    'difficulty trace',
  ]);
  expect(
    describePersonalizationReceipt({
      personalizationReceipt: {
        version: 'private-personalization-receipt-v1',
        epistemeRevision: 7,
        epistemeDigest: 'not-a-digest',
      },
    }),
  ).toBe('');
  expect(personalizationReceiptFacts({})).toEqual([]);
});

it('shows bounded personalization lanes without exposing the episteme digest', () => {
  mount(
    appState({
      currentPuzzleProvenance: {
        personalizationReceipt: {
          version: 'private-personalization-receipt-v1',
          epistemeRevision: 3,
          epistemeDigest: 'b'.repeat(64),
          inputs: { claimCount: 1, associationCount: 2 },
        },
      },
    }),
  );
  const receipt = host.querySelector('.future-private-puzzle-personalization');
  expect(receipt?.textContent).toContain(
    'Personalized from saved signals · open threads',
  );
  expect(receipt?.textContent).toContain('1 saved signal');
  expect(receipt?.textContent).toContain('2 open threads');
  expect(receipt?.textContent).not.toContain('b'.repeat(64));
});

it('surfaces reversible association steering without exposing association text', () => {
  expect(
    personalizationReceiptFacts({
      personalizationReceipt: {
        version: 'private-personalization-receipt-v1',
        epistemeRevision: 3,
        epistemeDigest: 'c'.repeat(64),
        associationSteering: {
          eligibleCount: 2,
          diversity: { status: 'varied' },
        },
      },
    }),
  ).toEqual(['2 active associations', 'varied association paths']);
});

it('explains when a proposed theme was released by fill quality', () => {
  expect(
    personalizationReceiptFacts({
      personalizationReceipt: {
        version: 'private-personalization-receipt-v1',
        epistemeRevision: 3,
        epistemeDigest: 'd'.repeat(64),
      },
      weekdayRecipe: { themeLocksUsed: 3, themeEntriesUsed: 0 },
    }),
  ).toEqual(['3 theme invitations', 'theme released by fill quality']);
  expect(
    personalizationReceiptFacts({
      personalizationReceipt: {
        version: 'private-personalization-receipt-v1',
        epistemeRevision: 3,
        epistemeDigest: 'e'.repeat(64),
      },
      weekdayRecipe: { themeLocksUsed: 2, themeEntriesUsed: 2 },
    }),
  ).toEqual(['2 theme invitations', '2 theme entries anchored']);
});

it('shows the current puzzle difficulty calibration as an accessible status', () => {
  mount(
    appState({
      currentPuzzleProvenance: {
        playCalibration: { recommendation: 'more-footholds' },
      },
    }),
  );

  const status = host.querySelector(
    '[role="status"][aria-label="Difficulty calibration recommendation"]',
  );
  expect(status?.textContent).toBe(
    'Difficulty calibration only: more footholds.',
  );
});

it('omits the play calibration status when no recommendation is available', () => {
  mount(appState());
  expect(
    host.querySelector(
      '[aria-label="Difficulty calibration recommendation"]',
    ),
  ).toBeNull();
});

it('enables generation when the host profile-save promise resolves', async () => {
  let resolveProfile;
  const readiness = new Promise((resolve) => {
    resolveProfile = resolve;
  });
  mount(appState(), { profileReady: readiness });

  expect(host.querySelector('button').disabled).toBe(true);
  await act(async () => {
    resolveProfile(true);
    await readiness;
  });
  expect(host.querySelector('button').disabled).toBe(false);
});

it('requests a puzzle only on click and loads it through the shared app initializer', async () => {
  const app = appState();
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => privateJobPayload(),
  });
  vi.stubGlobal('fetch', fetchMock);
  mount(app);

  expect(fetchMock).not.toHaveBeenCalled();
  expect(host.textContent).toContain('Make a new personal crossword');
  expect(host.textContent).toContain('Thursday can reward spotting a checked shared prefix or suffix');

  await act(async () => {
    clickButton();
    await new Promise((resolve) => setTimeout(resolve, 25));
  });

  expect(fetchMock).toHaveBeenCalledOnce();
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe('/api/future/private-puzzle-jobs');
  expect(options.method).toBe('POST');
  expect(options.headers['Content-Type']).toBe('application/json');
  const request = JSON.parse(options.body);
  expect(request).toMatchObject({ profileId: 'profile-1', weekday: 'thursday' });
  expect(typeof request.idempotencyKey).toBe('string');
  expect(Number.isInteger(request.seed)).toBe(true);
  expect(request.seed).toBeGreaterThanOrEqual(0);
  expect(request.seed).toBeLessThan(0x80000000);
  expect(app.selectedWeekday).toBe('thursday');
  expect(app.currentPuzzleMetadata).toEqual(privatePuzzlePayload().metadata);
  expect(app.currentPuzzleManifest).toEqual(privatePuzzlePayload().puzzleManifest);
  expect(app.currentPuzzleProvenance).toEqual(privatePuzzlePayload().provenance);
  expect(app.currentPuzzleRequestSeed).toBe(request.seed);
  expect(app.crossword).toEqual(privatePuzzlePayload().entries);
  expect(app.lastLoadedWeekday).toBe('thursday');
  expect(app.init).toHaveBeenCalledOnce();
  expect(host.textContent).toContain('Locally made with Ollama');
  expect(host.textContent).toContain('Personal thread: KOFFI · ACCRA');
});

it('uses the durable response body exactly once before applying a ready board', async () => {
  const app = appState();
  const json = vi
    .fn()
    .mockResolvedValueOnce(privateJobPayload())
    .mockRejectedValue(new TypeError('body already used'));
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    status: 202,
    json,
  }));
  mount(app);

  await act(async () => {
    clickButton();
    await new Promise((resolve) => setTimeout(resolve, 25));
  });

  expect(json).toHaveBeenCalledOnce();
  expect(app.init).toHaveBeenCalledOnce();
  expect(host.textContent).toContain('Locally made with Ollama');
});

it('offers a contextual one-more action after a finished game', async () => {
  const app = appState();
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 202,
    json: async () => privateJobPayload(),
  });
  vi.stubGlobal('fetch', fetchMock);
  mount(app, { postgameReady: true });

  const button = host.querySelector('.future-one-more-button');
  expect(button).not.toBeNull();
  expect(button.textContent).toContain('one more personal crossword');
  await act(async () => {
    button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 25));
  });

  expect(fetchMock).toHaveBeenCalledOnce();
  expect(app.init).toHaveBeenCalledOnce();
});

it('retries an interrupted durable job request with the same idempotency key', async () => {
  const app = appState();
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new TypeError('offline'))
    .mockResolvedValueOnce({
      ok: true,
      status: 202,
      json: async () => privateJobPayload(),
    });
  vi.stubGlobal('fetch', fetchMock);
  mount(app);

  await act(async () => {
    clickButton();
    await new Promise((resolve) => setTimeout(resolve, 900));
  });

  expect(fetchMock).toHaveBeenCalledTimes(2);
  const firstRequest = JSON.parse(fetchMock.mock.calls[0][1].body);
  const retryRequest = JSON.parse(fetchMock.mock.calls[1][1].body);
  expect(retryRequest.idempotencyKey).toBe(firstRequest.idempotencyKey);
  expect(app.init).toHaveBeenCalledOnce();
  expect(host.textContent).not.toContain('offline');
});

it('reattaches to a durable job after the solver view mounts again', async () => {
  const app = appState();
  const pending = {
    profileId: 'profile-1',
    jobId: 'job-1',
    seed: 42,
    weekday: 'thursday',
  };
  localStorage.setItem(
    'crossword.future.private-job.v1:profile-1',
    JSON.stringify(pending),
  );
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new TypeError('offline'))
    .mockResolvedValueOnce({
      ok: true,
      json: async () => privateJobPayload('ready'),
    });
  vi.stubGlobal('fetch', fetchMock);
  mount(app);

  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
  });

  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(fetchMock.mock.calls[0][0]).toBe(
    '/api/future/private-puzzle-jobs/job-1?profileId=profile-1',
  );
  expect(app.init).toHaveBeenCalledOnce();
  expect(localStorage.getItem('crossword.future.private-job.v1:profile-1')).toBeNull();
});

it('retries a transient durable poll without losing the in-flight puzzle', async () => {
  const app = appState();
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => privateJobPayload('running'),
    })
    .mockRejectedValueOnce(new TypeError('offline'))
    .mockResolvedValueOnce({
      ok: true,
      json: async () => privateJobPayload('ready'),
    });
  vi.stubGlobal('fetch', fetchMock);
  mount(app);

  await act(async () => {
    clickButton();
    await new Promise((resolve) => setTimeout(resolve, 1800));
  });

  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(app.init).toHaveBeenCalledOnce();
  expect(host.textContent).not.toContain('could not be read');
  expect(host.textContent).not.toContain('offline');
});

it('consumes an explicit language token hint before initializing the shared solver', async () => {
  const app = appState();
  const payload = privateLanguageTokenPayload();
  vi.stubGlobal('crypto', webcrypto);
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => payload }),
  );
  mount(app);

  await act(async () => {
    clickButton();
    await new Promise((resolve) => setTimeout(resolve, 25));
  });

  expect(app.init).toHaveBeenCalledOnce();
  expect(app.currentPuzzleTokenManifest).toMatchObject({
    schemaVersion: 'future-token-manifest-v1',
    languagePolicy: { language: 'fr' },
  });
  expect(app.crossword[0].characters[3]).toMatchObject({
    letters: 'E',
    tokenMetadata: { displayToken: 'É', fillToken: 'E' },
  });
});

it('lets the player choose a weekday before creating a local grid', async () => {
  const app = appState();
  const onWeekdayChange = vi.fn();
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => privateJobPayload(),
  });
  vi.stubGlobal('fetch', fetchMock);
  mount(app, { onWeekdayChange });

  const select = host.querySelector('select');
  select.value = 'wednesday';
  act(() => select.dispatchEvent(new Event('change', { bubbles: true })));
  expect(onWeekdayChange).toHaveBeenCalledWith('wednesday');
  expect(host.textContent).toContain('Wednesday aims for a satisfying middle-distance solve');

  await act(async () => {
    clickButton();
    await Promise.resolve();
  });
  expect(JSON.parse(fetchMock.mock.calls[0][1].body).weekday).toBe('wednesday');
});

it('passes an explicit local writing model through the durable request', async () => {
  const app = appState();
  const onModelPreferenceChange = vi.fn();
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => privateJobPayload(),
  });
  vi.stubGlobal('fetch', fetchMock);
  mount(app, { onModelPreferenceChange });

  const select = host.querySelector('select[aria-label="Local writing model"]');
  act(() => {
    select.value = 'qwen3.8:27b';
    select.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await act(async () => {
    clickButton();
    await new Promise((resolve) => setTimeout(resolve, 25));
  });

  expect(JSON.parse(fetchMock.mock.calls[0][1].body).model).toBe('qwen3.8:27b');
  expect(onModelPreferenceChange).toHaveBeenCalledWith('qwen3.8:27b');
});

it('restores the saved model preference when the profile view mounts', () => {
  mount(appState(), { modelPreference: 'gemma4:26b' });
  expect(host.querySelector('[aria-label="Local writing model"]').value).toBe(
    'gemma4:26b',
  );
});

it('shows an in-progress state and prevents duplicate requests', async () => {
  const app = appState();
  let resolveResponse;
  const fetchMock = vi.fn(
    () =>
      new Promise((resolve) => {
        resolveResponse = resolve;
      }),
  );
  vi.stubGlobal('fetch', fetchMock);
  mount(app);

  let button;
  await act(async () => {
    button = host.querySelector('button');
    button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await Promise.resolve();
  });
  expect(button.disabled).toBe(true);
  expect(host.textContent).toContain('Queued for the local maker');
  expect(fetchMock).toHaveBeenCalledOnce();

  await act(async () => {
    resolveResponse({ ok: true, json: async () => privatePuzzlePayload() });
    await Promise.resolve();
  });
  expect(button.disabled).toBe(false);
  expect(app.init).toHaveBeenCalledOnce();
});

it('keeps the current puzzle and reports a host error', async () => {
  const app = appState();
  const fetchMock = vi.fn().mockResolvedValue({
    ok: false,
    status: 503,
    json: async () => ({ error: 'The local model is unavailable.' }),
  });
  vi.stubGlobal('fetch', fetchMock);
  mount(app);

  await act(async () => {
    clickButton();
    await new Promise((resolve) => setTimeout(resolve, 1100));
  });

  expect(host.textContent).toContain('The local model is unavailable.');
  expect(app.currentPuzzleMetadata).toEqual({ date: '260927', title: 'Daily' });
  expect(app.crossword).toEqual([{ clue_text: 'Old clue' }]);
  expect(app.init).not.toHaveBeenCalled();
});

it('falls back when an older host returns an HTML 404 for the job route', async () => {
  const app = appState();
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => {
        throw new SyntaxError('Unexpected token <');
      },
    })
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => privatePuzzlePayload(),
    });
  vi.stubGlobal('fetch', fetchMock);
  mount(app);

  await act(async () => {
    clickButton();
    await Promise.resolve();
  });

  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(fetchMock.mock.calls[1][0]).toBe('/api/future/private-puzzles');
  expect(app.init).toHaveBeenCalledOnce();
  expect(host.textContent).not.toContain('unreadable response');
});

it('does not request a replacement when the player cancels the progress prompt', () => {
  const app = appState({ grid: [['A']] });
  const fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  vi.spyOn(window, 'confirm').mockReturnValue(false);
  mount(app);

  clickButton();

  expect(window.confirm).toHaveBeenCalledOnce();
  expect(fetchMock).not.toHaveBeenCalled();
  expect(app.init).not.toHaveBeenCalled();
});

it('rejects a response without the local Ollama provenance marker', async () => {
  const app = appState();
  const payload = privatePuzzlePayload();
  payload.provenance.source = 'unknown-source';
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => payload }),
  );
  mount(app);

  await act(async () => {
    clickButton();
    await Promise.resolve();
  });

  expect(host.textContent).toContain('unsupported format');
  expect(app.currentPuzzleMetadata).toEqual({ date: '260927', title: 'Daily' });
  expect(app.init).not.toHaveBeenCalled();
});

it('opens the reviewed warm-up when the local model is unavailable', async () => {
  const app = appState();
  const payload = privatePuzzlePayload();
  payload.provenance = {
    source: 'reviewed-sample',
    version: 'reviewed-sample-v1',
    sampleId: 'sator-square-v1',
    weekday: 'thursday',
    seed: 0,
  };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => payload,
  });
  vi.stubGlobal('fetch', fetchMock);
  mount(app);

  await act(async () => {
    host
      .querySelector('.future-private-puzzle-sample-button')
      .dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await Promise.resolve();
  });

  expect(fetchMock.mock.calls[0][0]).toContain(
    '/api/future/reviewed-samples/sator-square-v1',
  );
  expect(app.currentPuzzleProvenance).toMatchObject({
    source: 'reviewed-sample',
    sampleId: 'sator-square-v1',
  });
  expect(app.init).toHaveBeenCalledOnce();
  expect(host.textContent).toContain('Reviewed authored sample');
});
