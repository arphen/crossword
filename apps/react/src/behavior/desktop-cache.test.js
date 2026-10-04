// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createOptions } from './desktop';

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'];

const puzzle = (date) => ({
  metadata: { date, title: `Title ${date}`, authors: ['Author'] },
  entries: [
    {
      clue_number: 1,
      clue_text: 'Across fixture',
      direction: 'across',
      start_x: 0,
      start_y: 0,
      characters: [{ letters: 'A' }, { letters: 'B' }, { letters: 'C' }],
    },
    {
      clue_number: 1,
      clue_text: 'Down fixture',
      direction: 'down',
      start_x: 0,
      start_y: 0,
      characters: [{ letters: 'A' }, { letters: 'X' }, { letters: 'C' }],
    },
  ],
});

const stock = (day) => JSON.parse(localStorage.getItem(`crosswords_${day}`) || '[]');

function cachingApp(axios, overrides = {}) {
  const methods = createOptions({
    axios,
    socket: {},
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    requestAnimationFrame,
    cancelAnimationFrame,
  }).methods;
  const app = {
    baseUrl: 'http://test',
    isOffline: false,
    isChecking: false,
    isCachingInProgress: false,
    activeCaching: Object.fromEntries(DAYS.map((day) => [day, false])),
    cachingErrors: Object.fromEntries(DAYS.map((day) => [day, 0])),
    cachedCrosswordsCount: Object.fromEntries(DAYS.map((day) => [day, 0])),
    completedWords: new Set(),
    currentPuzzleMetadata: null,
    selectedWeekday: 'monday',
    lastLoadedWeekday: 'monday',
    ...overrides,
  };
  for (const [name, method] of Object.entries(methods)) {
    if (!(name in app)) app[name] = method.bind(app);
  }
  return app;
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal('alert', vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it('retains the played puzzle in offline stock across sessions', () => {
  const axios = { get: vi.fn(), post: vi.fn() };
  const app = cachingApp(axios, { isOffline: true, init: vi.fn() });
  localStorage.setItem('crosswords_monday', JSON.stringify([puzzle('date-1'), puzzle('date-2')]));

  app.loadCachedCrossword('monday');

  expect(app.crossword).toHaveLength(2);
  expect(app.init).toHaveBeenCalledTimes(1);
  // Both puzzles stay cached: playing offline no longer drains the stock.
  expect(stock('monday')).toHaveLength(2);
});

it('still evicts solved and invalid stock when loading from cache', () => {
  const axios = { get: vi.fn(), post: vi.fn() };
  const app = cachingApp(axios, { isOffline: true, init: vi.fn() });
  localStorage.setItem(
    'crosswords_monday',
    JSON.stringify([puzzle('solved-1'), { metadata: {}, entries: [] }, puzzle('good-1')]),
  );
  localStorage.setItem('solved_monday', JSON.stringify([{ id: 'solved-1' }]));
  // Worst order: the bad entries come up first, so clearing them must not
  // trip the recursion guard before the good puzzle loads.
  vi.spyOn(Math, 'random').mockReturnValue(0);

  app.loadCachedCrossword('monday');

  expect(app.currentPuzzleMetadata.date).toBe('good-1');
  expect(stock('monday').map((p) => p.metadata.date)).toEqual(['good-1']);
  expect(alert).not.toHaveBeenCalled();
});

it('reports whether caching a puzzle grew the stock', () => {
  const axios = { get: vi.fn(), post: vi.fn() };
  const app = cachingApp(axios);

  expect(app.cacheCrossword('monday', puzzle('date-1'))).toBe(true);
  expect(app.cacheCrossword('monday', puzzle('date-1'))).toBe(false); // duplicate
  expect(app.cacheCrossword('monday', { metadata: {}, entries: [] })).toBe(false); // invalid
  localStorage.setItem('solved_monday', JSON.stringify([{ id: 'solved-9' }]));
  expect(app.cacheCrossword('monday', puzzle('solved-9'))).toBe(false); // solved
  expect(stock('monday')).toHaveLength(1);
});

it('stops refilling when the backend only deals stock already held', async () => {
  vi.stubGlobal('setTimeout', (callback) => {
    callback();
    return 0;
  });
  // Fresh cooldown timestamp: the background retry the loop schedules on
  // success stays parked, so only this fill's own requests are counted.
  localStorage.setItem('lastCachingTime', String(Date.now()));
  const axios = { get: vi.fn(async () => ({ data: puzzle('same-date') })) };
  const app = cachingApp(axios);

  await app.fillCache('monday', 50);

  // One add, then eight consecutive refusals stop the loop instead of
  // burning all fifty requests for zero progress.
  expect(axios.get).toHaveBeenCalledTimes(9);
  expect(stock('monday')).toHaveLength(1);
});

it('tops the stock back up after an online load while counts are low', async () => {
  const fresh = puzzle('fresh-date');
  const axios = {
    get: vi.fn(async (url) => {
      if (url.includes('/random_crossword/')) return { data: fresh };
      return { data: { completed: false } };
    }),
    post: vi.fn(),
  };
  const fillCache = vi.fn(async () => {});
  const app = cachingApp(axios, { init: vi.fn(), fillCache });

  await app.loadCrossword('monday');

  expect(app.crossword).toHaveLength(2);
  expect(stock('monday')).toHaveLength(1);
  // Low counts trigger the background refill for every low day. The refill
  // runs detached from the load, so wait for it to arrive.
  await vi.waitFor(() => expect(fillCache).toHaveBeenCalledTimes(5));
  expect(fillCache).toHaveBeenCalledWith('monday', 49);
});

it('evicts a solved puzzle from the retained stock', () => {
  const axios = { get: vi.fn(), post: vi.fn(async () => ({ data: {} })) };
  const app = cachingApp(axios, {
    currentPuzzleMetadata: { date: 'date-1', title: 'T', authors: ['A'] },
    timer: 0,
    score: 100,
  });
  localStorage.setItem('crosswords_monday', JSON.stringify([puzzle('date-1'), puzzle('date-2')]));

  app.evictCachedPuzzle('monday', 'date-1');

  expect(stock('monday').map((p) => p.metadata.date)).toEqual(['date-2']);
  expect(app.cachedCrosswordsCount.monday).toBe(1);
});
