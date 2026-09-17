// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createOptions as desktopOptions } from './behavior/desktop';
import { createOptions as mobileOptions } from './behavior/mobile';
import { createController } from './controller';


// Deliberately consistent intersections: CAT / CAD / DOG share C and D.
const entries = () => [
  { clue_number: 1, clue_text: 'Feline', direction: 'across', start_x: 0, start_y: 0, characters: [...'CAT'].map(letters => ({ letters })) },
  { clue_number: 1, clue_text: 'Rogue', direction: 'down', start_x: 0, start_y: 0, characters: [...'CAD'].map(letters => ({ letters })) },
  { clue_number: 3, clue_text: 'Canine', direction: 'across', start_x: 0, start_y: 2, characters: [...'DOG'].map(letters => ({ letters })) }
];
const metadata = { date: '260829', title: 'Synthetic fixture', authors: ['Test'], width: 3, height: 3 };
let controllers;


beforeEach(() => {
  controllers = [];
  vi.useFakeTimers();
  // Node's localStorage shadows jsdom here; preserve Storage's string coercion.
  const storage = new Map();
  vi.stubGlobal('localStorage', {
    getItem: key => storage.get(String(key)) ?? null,
    setItem: (key, value) => storage.set(String(key), String(value)),
    removeItem: key => storage.delete(String(key)),
    clear: () => storage.clear()
  });
  vi.stubGlobal('alert', vi.fn());
  vi.stubGlobal('confirm', vi.fn(() => true));
});
afterEach(() => {
  controllers.forEach(controller => controller.dispose());
  vi.clearAllTimers();
  vi.useRealTimers();
  localStorage.clear();
  document.body.replaceChildren();
  document.body.removeAttribute('data-active-direction');
  document.documentElement.style.removeProperty('color-scheme');
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function fresh(options = desktopOptions) {
  const socket = { on: vi.fn(), emit: vi.fn(), connect: vi.fn(), disconnect: vi.fn(), removeAllListeners: vi.fn() };
  const axios = { get: vi.fn(), post: vi.fn().mockResolvedValue({ data: {} }) };
  const controller = createController(options, { socket, axios, room: 'TEST', role: 'across' });
  controllers.push(controller);
  const { app } = controller;
  if (options === desktopOptions) {
    // Method tests do not start the created hook's unrelated network/cache load.
    app.currentPuzzleMetadata = { ...metadata };
    app.crossword = entries();
    app.init();
    app.grid.forEach((row, r) => row.forEach((value, c) => {
      if (value === null) return;
      const cell = document.createElement('div');
      cell.className = 'grid-cell';
      const input = document.createElement('input');
      input.dataset.coordinate = `${r},${c}`;
      cell.append(input);
      document.body.append(cell);
      app.setRef(`input-${r}-${c}`, input);
    }));
  }
  return { app, controller, socket, axios };
}
function key(key, target = document.body) {
  return { key, target, preventDefault: vi.fn(), stopPropagation: vi.fn() };
}
function input(app, r, c) { return app.$refs[`input-${r}-${c}`][0]; }
function fill(app, r, c, value) { app.grid[r][c] = value; input(app, r, c).value = value; }

describe('desktop reference contracts (controller method tests)', () => {
  it('builds seven mapped cells and preserves black squares and shared word membership', () => {
    const { app } = fresh();
    expect(app.grid).toEqual([['', '', ''], ['', null, null], ['', '', '']]);
    expect(app.cellMap.size).toBe(7);
    expect(app.getCellClasses(1, 1)).toBe('black-cell');
    expect(app.getCellClasses(0, 0)).toBe('');
    expect(app.getCell(0, 0).words).toHaveLength(2);
    expect(app.find_solution(2, 0)).toBe('D');
  });

  it('focuses on the next render tick and preserves stale clue highlighting on mini-cell click', () => {
    const { app, controller } = fresh();
    const refsDescriptor = Object.getOwnPropertyDescriptor(app, '$refs');
    expect(refsDescriptor).toMatchObject({ configurable: false, writable: false });
    expect(app.$refs).toBe(refsDescriptor.value); // Proxy must return exact fixed property value
    app.handle_clue_click({}, app.crossword[1]);
    expect(document.activeElement).not.toBe(input(app, 0, 0));
    controller.flush();
    expect(document.activeElement).toBe(input(app, 0, 0));
    expect([app.direction, app.activeClueNumber, app.activeDirection]).toEqual(['down', 1, 'down']);
    const event = key('');
    app.handle_cell_click(event, app.crossword[0], 2);
    expect(event.stopPropagation).toHaveBeenCalledOnce();
    controller.flush();
    expect(document.activeElement).toBe(input(app, 0, 2));
    expect([app.direction, app.activeClueNumber, app.activeDirection]).toEqual(['across', 1, 'down']);
    expect(document.body.dataset.activeDirection).toBe('down');
  });

  it('moves within words, jumps only from a filled word, skips black squares, and changes arrow direction', () => {
    const { app, controller } = fresh();
    input(app, 0, 0).focus();
    app.move(0, 0, 'forward');
    controller.flush();
    expect(document.activeElement).toBe(input(app, 0, 1));
    input(app, 0, 2).focus();
    app.move(0, 2, 'forward');
    controller.flush();
    expect(document.activeElement).toBe(input(app, 0, 2)); // incomplete: no next-word jump
    [...'CAT'].forEach((letter, c) => fill(app, 0, c, letter));
    app.move(0, 2, 'forward');
    controller.flush();
    expect(document.activeElement).toBe(input(app, 2, 0));
    input(app, 0, 1).focus();
    const arrow = key('ArrowDown');
    app.handle_crossword_cell_keydown(arrow, 0, 1);
    controller.flush();
    expect(app.direction).toBe('down');
    expect(document.activeElement).toBe(input(app, 0, 1)); // first arrow only changes direction
    app.handle_crossword_cell_keydown(arrow, 0, 1);
    controller.flush();
    expect(document.activeElement).toBe(input(app, 2, 1)); // skipped (1,1)
    expect(arrow.preventDefault).not.toHaveBeenCalled(); // legacy arrow quirk
  });

  it('replaces letters and advances; backspace clears current then focuses previous without erasing it', () => {
    const { app, controller } = fresh();
    fill(app, 0, 0, 'Z');
    const letter = key('a');
    app.handle_crossword_cell_keydown(letter, 0, 0);
    controller.flush();
    expect(app.grid[0][0]).toBe('A');
    expect(letter.preventDefault).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(input(app, 0, 1));
    fill(app, 0, 1, 'X');
    const backspace = key('Backspace');
    app.handle_crossword_cell_keydown(backspace, 0, 1);
    controller.flush();
    expect(app.grid[0].slice(0, 2)).toEqual(['A', '']);
    expect(document.activeElement).toBe(input(app, 0, 0));
    expect(backspace.preventDefault).toHaveBeenCalledOnce();
  });

  it('penalizes once per erroneous check, not per letter; clearChecks preserves completed words', () => {
    const { app } = fresh();
    [...'CAT'].forEach((letter, c) => fill(app, 0, c, letter));
    fill(app, 1, 0, 'X');
    fill(app, 2, 2, 'X');
    app.check_all();
    expect([app.checksUsed, app.score, app.isChecking]).toEqual([1, 90, true]);
    expect([...app.completedWords]).toEqual(['Feline']);
    expect(input(app, 0, 0).classList.contains('green')).toBe(true);
    expect(input(app, 1, 0).classList.contains('red')).toBe(true);
    app.check_all();
    expect([app.checksUsed, app.score, app.isChecking]).toEqual([1, 90, false]);
    expect([...app.completedWords]).toEqual(['Feline']);
    expect(document.querySelectorAll('.red, .green')).toHaveLength(0);
    app.check_all();
    expect([app.checksUsed, app.score]).toEqual([2, 80]);
    expect([...app.completedWords]).toEqual(['Feline']);
  });

  it('reveals only empty nonblack cells; rebus input opens, focuses, normalizes and saves', () => {
    const { app, controller } = fresh();
    const event = key(' ', input(app, 0, 0));
    app.handle_crossword_cell_contextmenu(event, 0, 0);
    expect(app.grid[0][0]).toBe('C');
    expect([app.revealsUsed, app.score]).toEqual([1, 80]);
    app.handle_crossword_cell_contextmenu(event, 0, 0);
    app.handle_crossword_cell_contextmenu(event, 1, 1);
    expect(app.grid[1][1]).toBe(null);
    expect(app.revealsUsed).toBe(1);
    app.handle_crossword_cell_keydown(event, 0, 0);
    expect(app.showRebusMenu).toBe(false);
    app.getCell(0, 0).is_rebus = true;
    const editor = document.createElement('input');
    editor.className = 'rebus-context-menu-input';
    document.body.append(editor);
    app.handle_crossword_cell_keydown(event, 0, 0);
    controller.flush();
    expect(document.activeElement).toBe(editor);
    expect(app.rebusMenuCell).toEqual({ row: 0, col: 0 });
    app.rebusInputValue = ' cat ';
    app.handleRebusMenuKeydown(key('Enter'));
    expect(app.grid[0][0]).toBe('CAT');
    expect(app.showRebusMenu).toBe(false);
    expect([app.revealsUsed, app.score]).toEqual([1, 80]);
  });

  it('round-trips string-valued Storage and posts the supplied completion day, not the puzzle weekday', async () => {
    const { app, axios } = fresh();
    app.timer = 42;
    app.score = 80;
    await app.markPuzzleSolved('monday', metadata.date);
    const solved = JSON.parse(localStorage.getItem('solved_monday'));
    expect(solved).toEqual([{
      id: metadata.date, title: metadata.title, authors: metadata.authors,
      dayOfWeekSolved: 'monday', dateSolved: new Date().toISOString()
    }]);
    expect(app.solvedPuzzlesCount.monday).toBe(1);
    expect(app.getCurrentDay()).toBe('saturday');
    expect(axios.post).toHaveBeenCalledWith(`${window.location.origin}/api/completed_puzzles`, {
      puzzle_date: metadata.date, title: metadata.title, authors: metadata.authors,
      weekday: 'monday', time_taken: 42, score: 80
    });
    await app.markPuzzleSolved('monday', metadata.date);
    expect(JSON.parse(localStorage.getItem('solved_monday'))).toHaveLength(1);
    expect(axios.post).toHaveBeenCalledTimes(2); // only local persistence deduplicates
  });

  it('cancelled loading leaves selection, progress and checks untouched', () => {
    const { app, axios } = fresh();
    app.grid[0][0] = 'A';
    app.isChecking = true;
    app.completedWords.add('Feline');
    confirm.mockReturnValue(false);
    expect(app.attemptLoadDay('TUESDAY')).toBe(false);
    expect(confirm).toHaveBeenCalledOnce();
    expect(app.selectedWeekday).toBe('monday');
    expect(app.grid[0][0]).toBe('A');
    expect(app.isChecking).toBe(true);
    expect([...app.completedWords]).toEqual(['Feline']);
    expect(axios.get).not.toHaveBeenCalled();
  });

  it('disposes active timers and subscriptions even without calling start', () => {
    const { app, controller, socket } = fresh();
    const listener = vi.fn();
    controller.subscribe(listener);
    vi.advanceTimersByTime(2000);
    expect(app.timer).toBe(2);
    expect(listener).toHaveBeenCalled();
    controller.dispose();
    listener.mockClear();
    const revision = controller.snapshot();
    vi.advanceTimersByTime(2000);
    expect(app.timer).toBe(2);
    expect(controller.snapshot()).toBe(revision);
    expect(listener).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    expect(socket.removeAllListeners).toHaveBeenCalledOnce();
    expect(socket.disconnect).toHaveBeenCalledOnce();
    controllers = controllers.filter(item => item !== controller);
  });
});

describe('mobile reference contracts (controller method tests)', () => {
  it('check-then-clear marks only fully correct own entries and emits actual coordinate clears', () => {
    const { app, socket, controller } = fresh(mobileOptions);
    controller.start();
    expect(socket.emit).toHaveBeenCalledWith('join', { room: 'TEST', role: 'across' });
    socket.emit.mockClear();
    app.crossword = entries();
    Object.assign(app.grid, { '0,0': 'C', '0,1': 'X', '1,0': 'Z', '2,0': 'D', '2,1': 'O', '2,2': 'G' });
    app.toggleCheck();
    expect(app.checkButtonLabel).toBe('Clear Errors');
    expect(socket.emit).not.toHaveBeenCalled();
    app.toggleCheck();
    expect(app.checkButtonLabel).toBe('Check');
    expect(app.solvedKeys).toEqual(['3-across']);
    expect(app.sortedEntries.map(entry => entry.clue_number)).toEqual([1, 3]);
    expect(app.grid['0,1']).toBe('');
    expect(app.grid['1,0']).toBe('Z'); // partner's down-only cell is not cleared
    expect(socket.emit.mock.calls).toEqual([['update_cell', { room: 'TEST', row: 0, col: 1, value: '' }]]);
  });

  it('focuses hidden input, uses last character, and empty backspace deletes the preceding cell', () => {
    const { app, socket, controller } = fresh(mobileOptions);
    app.crossword = entries();
    const hidden = document.createElement('input');
    document.body.append(hidden);
    app.setRef('hiddenInput', hidden);
    app.selectEntry(app.crossword[0]);
    controller.flush();
    expect(document.activeElement).toBe(hidden);
    const event = { target: { value: 'cq' } };
    app.handleInput(event);
    expect(event.target.value).toBe('');
    expect([app.grid['0,0'], app.activeCharIndex]).toEqual(['Q', 1]);
    app.handleKeydown(key('Backspace'));
    expect([app.grid['0,0'], app.activeCharIndex]).toEqual(['', 0]);
    expect(socket.emit.mock.calls).toEqual([
      ['update_cell', { room: 'TEST', row: 0, col: 0, value: 'Q' }],
      ['update_cell', { room: 'TEST', row: 0, col: 0, value: '' }]
    ]);
  });
});
