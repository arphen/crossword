// @vitest-environment jsdom
import desktopSource from '../../../src/crossword/static/main.js?raw';
import mobileSource from '../../../src/crossword/static/mobile.js?raw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Vue from 'vue/dist/vue.runtime.common.js';
import { createController } from './controller';
import { createOptions as desktopOptions } from './behavior/desktop';
import { createOptions as mobileOptions } from './behavior/mobile';

// Execute the ORIGINAL source, not the generated behavior modules, to obtain
// the oracle. Only automatic DOM mounting is suppressed; Vue itself supplies
// data, methods, computed properties, watchers, $set, and $nextTick.
const sources = { main: desktopSource, mobile: mobileSource };
function originalOptions(kind, axios, socket) {
  let captured;
  function CaptureVue(options) { captured = options; }
  CaptureVue.set = Vue.set;
  const doc = new Proxy(document, {
    get(target, name) {
      if (name === 'addEventListener') return (event, callback, ...args) => {
        if (event !== 'DOMContentLoaded') target.addEventListener(event, callback, ...args);
      };
      const value = Reflect.get(target, name);
      return typeof value === 'function' ? value.bind(target) : value;
    }
  });
  const module = { exports: {} };
  new Function('Vue', 'io', 'axios', 'ROOM_ID', 'INITIAL_ROLE', 'document', 'module', sources[kind])(
    CaptureVue, () => socket, axios, 'TEST', 'across', doc, module
  );
  const options = kind === 'main' ? module.exports.CrosswordApp : captured;
  const { el, ...withoutAutoMount } = options;
  return withoutAutoMount;
}
const puzzle = () => ({
  metadata: { date: '260829', title: 'Differential fixture', authors: ['Test'], width: 3, height: 3 },
  entries: [
    { clue_number: 1, clue_text: 'Feline', direction: 'across', start_x: 0, start_y: 0, characters: [...'CAT'].map(letters => ({ letters })) },
    { clue_number: 1, clue_text: 'Rogue', direction: 'down', start_x: 0, start_y: 0, characters: [...'CAD'].map(letters => ({ letters })) },
    { clue_number: 3, clue_text: 'Canine', direction: 'across', start_x: 0, start_y: 2, characters: [...'DOG'].map(letters => ({ letters })) }
  ]
});
const cleanups = [];
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-09-01T12:00:00Z'));
  vi.stubGlobal('alert', vi.fn());
  vi.stubGlobal('confirm', vi.fn(() => true));
});
afterEach(() => {
  cleanups.splice(0).reverse().forEach(cleanup => cleanup());
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.body.replaceChildren();
  document.body.removeAttribute('data-active-direction');
  document.documentElement.style.removeProperty('color-scheme');
});
const plain = value => JSON.parse(JSON.stringify(value));
const event = (key, target = document.body) => ({ key, target, preventDefault: vi.fn(), stopPropagation: vi.fn() });

async function run(kind, engine, scenario) {
  document.body.replaceChildren();
  document.body.removeAttribute('data-active-direction');
  document.documentElement.style.removeProperty('color-scheme');
  const storage = new Map();
  vi.stubGlobal('localStorage', {
    getItem: key => storage.get(String(key)) ?? null,
    setItem: (key, value) => storage.set(String(key), String(value)),
    removeItem: key => storage.delete(String(key)), clear: () => storage.clear()
  });
  const handlers = new Map();
  const socket = {
    on: vi.fn((name, callback) => handlers.set(name, callback)), emit: vi.fn(),
    connect: vi.fn(), disconnect: vi.fn(), removeAllListeners: vi.fn(() => handlers.clear())
  };
  const axios = {
    get: vi.fn(async url => ({ data: url.includes('/api/completed_puzzles/') ? { completed: false } : puzzle() })),
    post: vi.fn(async () => ({ data: {} }))
  };
  let app, controller, options;
  if (engine === 'vue') {
    options = originalOptions(kind, axios, socket);
    app = new Vue(options); // actual original created hook, including desktop load
    if (options.mounted) options.mounted.call(app); // no templates in this method-level suite
  } else {
    controller = createController(kind === 'main' ? desktopOptions : mobileOptions, { axios, socket, room: 'TEST', role: 'across' });
    app = controller.app;
    controller.start();
  }
  let disposed = false;
  const cleanup = () => {
    if (disposed) return;
    disposed = true;
    if (controller) controller.dispose();
    else {
      options.beforeUnmount?.call(app); // Vue 2 does not run Vue 3's hook name
      window.removeEventListener('online', app.handleOnlineStatus);
      window.removeEventListener('offline', app.handleOnlineStatus);
      document.removeEventListener('click', app.handleDocumentClick);
      app.$destroy();
      socket.removeAllListeners();
      socket.disconnect();
    }
  };
  cleanups.push(cleanup);
  const settle = async () => {
    // All fixture requests resolve immediately; allow load + completion awaits
    // and Vue's watcher queue before comparing to React's post-render flush.
    for (let i = 0; i < 8; i++) await Promise.resolve();
    await Vue.nextTick();
    controller?.flush();
  };
  const inputs = new Map();
  const attach = (name, coordinate, className = 'grid-cell') => {
    const cell = document.createElement('div');
    cell.className = className;
    const input = document.createElement('input');
    input.dataset.coordinate = coordinate;
    cell.append(input);
    document.body.append(cell);
    app.$refs[name] = [input]; // exercises controller's readonly-$refs Proxy invariant
    inputs.set(coordinate, input);
    return input;
  };
  const syncInputs = () => inputs.forEach((input, coordinate) => {
    const [row, col] = coordinate.split(',').map(Number);
    if (Number.isFinite(row) && Number.isFinite(col)) input.value = app.grid[row]?.[col] ?? '';
  });
  try {
    await settle();
    if (kind === 'main') app.grid.forEach((row, r) => row.forEach((value, c) => {
      if (value !== null) attach(`input-${r}-${c}`, `${r},${c}`);
    }));
    else app.crossword = puzzle().entries;
    return plain(await scenario({ app, axios, socket, handlers, storage, settle, attach, inputs, syncInputs }));
  } finally { cleanup(); }
}
async function compare(kind, scenario) {
  const original = await run(kind, 'vue', scenario);
  const port = await run(kind, 'react', scenario);
  expect(port).toEqual(original);
  return original; // explicit contracts keep identical-but-wrong traces from passing
}

describe('original Vue runtime versus React controller differential behavior', () => {
  it('loads and caches the fixture through the original created hook and handles remote cell updates', async () => {
    const result = await compare('main', async ({ app, axios, handlers, storage, settle }) => {
      handlers.get('cell_updated')({ row: 0, col: 1, value: 'X' });
      handlers.get('cell_updated')({ row: 99, col: 0, value: 'ignored' });
      app.selectedWeekday = 'tuesday';
      app.activeDirection = 'down';
      await settle();
      const direction = document.body.dataset.activeDirection;
      app.activeDirection = null;
      await settle();
      return {
        grid: app.grid, cells: [...app.cellMap.entries()], requests: axios.get.mock.calls,
        cached: JSON.parse(storage.get('crosswords_monday')), count: app.cachedCrosswordsCount.monday,
        selection: storage.get('selectedWeekday'), direction, clearedDirection: document.body.hasAttribute('data-active-direction')
      };
    });
    expect(result.grid).toEqual([['', 'X', ''], ['', null, null], ['', '', '']]);
    expect(result.cells).toHaveLength(7);
    expect(result.requests).toEqual([
      [`${window.location.origin}/random_crossword/monday`],
      [`${window.location.origin}/api/completed_puzzles/260829`]
    ]);
    expect([result.count, result.selection, result.direction, result.clearedDirection]).toEqual([1, 'tuesday', 'down', false]);
  });

  it('matches actual focus transitions, stale clue selection, typing, arrows and backspace', async () => {
    const trace = await compare('main', async ({ app, settle, inputs }) => {
      const trace = [];
      const record = async action => {
        action(); await settle();
        trace.push({ focus: document.activeElement.dataset.coordinate, direction: app.direction,
          active: [app.activeClueNumber, app.activeDirection], grid: plain(app.grid) });
      };
      await record(() => app.handle_clue_click({}, app.crossword[1]));
      const click = event('');
      await record(() => app.handle_cell_click(click, app.crossword[0], 1));
      await record(() => app.handle_crossword_cell_keydown(event('q'), 0, 1));
      await record(() => app.handle_crossword_cell_keydown(event('Backspace'), 0, 2));
      await record(() => app.handle_crossword_cell_keydown(event('ArrowDown'), 0, 1));
      await record(() => app.handle_crossword_cell_keydown(event('ArrowDown'), 0, 1));
      return { trace, stopped: click.stopPropagation.mock.calls.length, refIsElement: app.$refs['input-0-0'][0] === inputs.get('0,0') };
    });
    expect(trace.trace.map(step => step.focus)).toEqual(['0,0', '0,1', '0,2', '0,1', '0,1', '2,1']);
    expect(trace.trace[1].active).toEqual([1, 'down']);
    expect(trace.trace[2].grid[0][1]).toBe('Q');
    expect([trace.stopped, trace.refIsElement]).toEqual([1, true]);
  });

  it('matches check colors, per-check scoring and retained completed-word state', async () => {
    const trace = await compare('main', async ({ app, inputs, syncInputs }) => {
      app.grid[0] = ['C', 'A', 'T']; app.grid[1][0] = 'X';
      syncInputs();
      const snapshots = [];
      for (let i = 0; i < 3; i++) {
        app.check_all();
        snapshots.push({ checking: app.isChecking, score: app.score, checks: app.checksUsed,
          completed: [...app.completedWords], colors: [...inputs].map(([coordinate, input]) => [coordinate, input.className]) });
      }
      return snapshots;
    });
    expect(trace.map(step => [step.checking, step.score, step.checks, step.completed])).toEqual([
      [true, 90, 1, ['Feline']], [false, 90, 1, ['Feline']], [true, 80, 2, ['Feline']]
    ]);
    expect(trace[0].colors).toContainEqual(['1,0', 'red']);
    expect(trace[1].colors.every(([, color]) => color === '')).toBe(true);
  });

  it('matches reveal penalties, rebus focus/save/cancel and completion persistence', async () => {
    const result = await compare('main', async ({ app, inputs, settle, storage, axios }) => {
      const target = inputs.get('0,0');
      app.handle_crossword_cell_contextmenu(event('', target), 0, 0);
      app.handle_crossword_cell_contextmenu(event('', target), 0, 0);
      const revealed = [app.grid[0][0], app.revealsUsed, app.score];
      app.getCell(0, 0).is_rebus = true;
      const editor = document.createElement('input');
      editor.className = 'rebus-context-menu-input'; document.body.append(editor);
      app.handle_crossword_cell_keydown(event(' ', target), 0, 0);
      await settle();
      const focused = document.activeElement === editor;
      app.rebusInputValue = ' cat ';
      app.handleRebusMenuKeydown(event('Enter'));
      app.handle_crossword_cell_contextmenu(event('', target), 0, 0);
      app.rebusInputValue = 'discard';
      app.handleRebusMenuKeydown(event('Escape'));
      app.timer = 42;
      await app.markPuzzleSolved('monday', '260829');
      await app.markPuzzleSolved('monday', '260829');
      return { revealed, focused, value: app.grid[0][0], menu: app.showRebusMenu,
        saved: JSON.parse(storage.get('solved_monday')), posts: axios.post.mock.calls, solvedCount: app.solvedPuzzlesCount.monday };
    });
    expect(result.revealed).toEqual(['C', 1, 80]);
    expect([result.focused, result.value, result.menu, result.solvedCount]).toEqual([true, 'CAT', false, 1]);
    expect(result.saved).toHaveLength(1);
    expect(result.posts).toHaveLength(2);
    expect(result.posts[0][1]).toMatchObject({ weekday: 'monday', time_taken: 42, score: 80 });
  });

  it('matches cancellation and accepted loading including normalized weekday and stale active clue', async () => {
    const result = await compare('main', async ({ app, axios, settle }) => {
      app.grid[0][0] = 'C'; app.activeClueNumber = 1; app.activeDirection = 'down';
      app.isChecking = true; app.completedWords.add('Feline');
      confirm.mockReturnValueOnce(false);
      const cancelled = app.attemptLoadDay('TUESDAY');
      const before = [app.selectedWeekday, app.grid[0][0], app.isChecking, [...app.completedWords], axios.get.mock.calls.length];
      const accepted = app.attemptLoadDay('TUESDAY');
      await settle();
      return { cancelled, before, accepted, after: [app.selectedWeekday, app.lastLoadedWeekday, app.grid[0][0], app.isChecking,
        [...app.completedWords], app.activeClueNumber, app.activeDirection], requests: axios.get.mock.calls };
    });
    expect(result.cancelled).toBe(false);
    expect(result.before).toEqual(['monday', 'C', true, ['Feline'], 2]);
    expect(result.accepted).toBe(true);
    expect(result.after).toEqual(['tuesday', 'tuesday', '', false, [], 1, 'down']);
  });

  it('matches mobile input/backspace boundaries, hidden-input focus and emitted coordinates', async () => {
    const result = await compare('mobile', async ({ app, socket, attach, settle }) => {
      const hidden = attach('hiddenInput', 'hidden', 'mobile-input');
      app.selectEntry(app.crossword[0]); await settle();
      const focused = document.activeElement === hidden;
      const target = { value: 'cq' }; app.handleInput({ target });
      app.handleKeydown(event('Backspace')); // empty current -> previous + delete
      app.focusInput(app.crossword[0], 2); await settle();
      app.handleInput({ target: { value: 'at' } }); // final cell does not advance
      const finalIndex = app.activeCharIndex;
      app.handleKeydown(event('Backspace')); // occupied -> clear without moving
      return { focused, inputCleared: target.value, finalIndex, activeIndex: app.activeCharIndex, grid: app.grid, emits: socket.emit.mock.calls };
    });
    expect([result.focused, result.inputCleared, result.finalIndex, result.activeIndex]).toEqual([true, '', 2, 2]);
    expect(result.emits).toEqual([
      ['join', { room: 'TEST', role: 'across' }],
      ['update_cell', { room: 'TEST', row: 0, col: 0, value: 'Q' }],
      ['update_cell', { room: 'TEST', row: 0, col: 0, value: '' }],
      ['update_cell', { room: 'TEST', row: 0, col: 2, value: 'T' }],
      ['update_cell', { room: 'TEST', row: 0, col: 2, value: '' }]
    ]);
  });

  it('matches mobile role-scoped error clears, solved sorting and persistent solved keys', async () => {
    const result = await compare('mobile', async ({ app, socket, settle }) => {
      Object.assign(app.grid, { '0,0': 'C', '0,1': 'A', '0,2': 'T', '1,0': 'X', '2,0': 'X' });
      app.toggleCheck(); const label = app.checkButtonLabel;
      app.toggleCheck(); await settle();
      const sorted = app.sortedEntries.map(entry => entry.clue_number);
      app.grid['0,0'] = 'X';
      app.toggleCheck(); app.toggleCheck(); await settle();
      return { label, sorted, solved: app.solvedKeys, grid: app.grid, emits: socket.emit.mock.calls };
    });
    expect(result.label).toBe('Clear Errors');
    expect(result.sorted).toEqual([3, 1]);
    expect(result.solved).toEqual(['1-across']); // solved marker is intentionally sticky
    expect(result.grid['1,0']).toBe('X'); // partner's entry remains untouched
    expect(result.emits.slice(1)).toEqual([
      ['update_cell', { room: 'TEST', row: 2, col: 0, value: '' }],
      ['update_cell', { room: 'TEST', row: 0, col: 0, value: '' }]
    ]);
  });

  it('matches mobile socket state loading, remote edits and optimistic/server swap quirks', async () => {
    const result = await compare('mobile', async ({ app, handlers, socket, axios, settle }) => {
      handlers.get('game_state')({ grid: { '0,0': 'C' }, puzzle_date: '260829' });
      await settle();
      handlers.get('game_state')({ grid: { '0,0': 'A' }, puzzle_date: '260830' });
      handlers.get('cell_updated')({ row: 2, col: 1, value: 'O' });
      app.selectEntry(app.crossword[0]);
      app.requestSwap(); handlers.get('swap_requested')();
      const requested = app.showSwapRequest;
      app.confirmSwap();
      const optimistic = [app.role, app.showSwapRequest, app.activeEntry.clue_number];
      handlers.get('swap_confirmed')(); await settle();
      return { grid: app.grid, date: app.puzzleDate, requests: axios.get.mock.calls, requested, optimistic,
        final: [app.role, app.activeEntry], emits: socket.emit.mock.calls };
    });
    expect(result.requests).toEqual([['/crossword_by_date/260829']]);
    expect(result.date).toBe('260829');
    expect(result.grid).toEqual({ '0,0': 'A', '2,1': 'O' });
    expect(result.requested).toBe(true);
    expect(result.optimistic).toEqual(['down', false, 1]);
    expect(result.final).toEqual(['across', null]); // optimistic + broadcast toggles twice in Vue too
    expect(result.emits).toEqual([
      ['join', { room: 'TEST', role: 'across' }], ['request_swap', { room: 'TEST' }], ['confirm_swap', { room: 'TEST' }]
    ]);
  });
});
