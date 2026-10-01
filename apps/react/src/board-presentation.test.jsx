// @vitest-environment jsdom
import React, { act, useLayoutEffect, useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createOptions as desktopOptions } from './behavior/desktop';
import { createController } from './controller';
import CrosswordView from './CrosswordView';
import { VIEW_SETTINGS_KEY } from './viewSettings';

const boxes = (answer) => [...answer].map((letters) => ({ letters }));
// An eleven-letter Across sharing its opening square with a five-letter Down, and
// a three-word answer along the bottom row: enough board to show balanced runs,
// word gaps, and black squares that open a slot.
const entries = () => [
  { clue_number: 1, clue_text: 'Letters that came before (11)', direction: 'across', start_x: 0, start_y: 0, characters: boxes('NEVERSOONER') },
  { clue_number: 1, clue_text: 'Not yet', direction: 'down', start_x: 0, start_y: 0, characters: boxes('NEVER') },
  { clue_number: 2, clue_text: 'Like a promise (3,2,4)', direction: 'across', start_x: 0, start_y: 4, characters: boxes('RUE ON TIME') },
];

let hosts = [];
let roots = [];
let controllers = [];

beforeEach(() => {
  hosts = [];
  roots = [];
  controllers = [];
  // Node's localStorage shadows jsdom here; preserve Storage's string coercion.
  const stored = new Map();
  vi.stubGlobal('localStorage', {
    getItem: (key) => (stored.has(String(key)) ? stored.get(String(key)) : null),
    setItem: (key, value) => stored.set(String(key), String(value)),
    removeItem: (key) => stored.delete(String(key)),
    clear: () => stored.clear(),
  });
  vi.stubGlobal('alert', vi.fn());
  vi.stubGlobal('confirm', vi.fn(() => true));
});

afterEach(async () => {
  // Unmount before the controller lets go: a dispose that mutates state while
  // the view still listens lands as a render React never saw asked for.
  for (const root of roots.splice(0).reverse()) await act(async () => { root.unmount(); });
  controllers.splice(0).forEach((controller) => controller.dispose());
  for (const host of hosts.splice(0).reverse()) host.remove();
  document.body.replaceChildren();
  vi.unstubAllGlobals();
});

async function mountBoard() {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  const socket = { on: vi.fn(), emit: vi.fn(), connect: vi.fn(), disconnect: vi.fn(), removeAllListeners: vi.fn() };
  const axios = { get: vi.fn(async () => ({ data: { entries: [] } })), post: vi.fn(async () => ({ data: {} })) };
  const controller = createController(desktopOptions, { socket, axios, room: 'TEST', role: 'across' });
  controllers.push(controller);
  const { app } = controller;
  // The fixture stands in for the daily load: the board is drawn from the entries.
  app.currentPuzzleMetadata = { date: '260829', title: 'Synthetic fixture', authors: ['Test'], width: 11, height: 5 };
  app.crossword = entries();
  // The behaviour narrates its grid build; the test reads the board, not the log.
  const log = vi.spyOn(console, 'log').mockImplementation(() => {});
  await act(async () => { app.init(); });
  log.mockRestore();
  const host = document.createElement('div');
  document.body.append(host);
  hosts.push(host);
  function View() {
    useSyncExternalStore(controller.subscribe, controller.snapshot);
    useLayoutEffect(() => controller.flush());
    return <CrosswordView app={app} />;
  }
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<View />); });
  return host;
}

const board = (host) => host.querySelector('#app.react-desktop-app');
const tracks = (host) => [...host.querySelectorAll('#across .state-container')];
const runsIn = (track) => [...track.querySelectorAll(':scope > .state-run')].map((run) => ({
  letters: run.querySelectorAll('.state').length,
  wordEnd: run.classList.contains('word-end'),
}));

async function choose(host, row, choice) {
  const rows = [...host.querySelectorAll('.view-row')];
  const labelled = rows.find((candidate) => candidate.querySelector('.view-row-label')?.textContent === row);
  if (!labelled) throw new Error(`No view row named "${row}". Rows: ${rows.map((one) => one.querySelector('.view-row-label')?.textContent).join(', ')}`);
  const buttons = [...labelled.querySelectorAll('.view-choice')];
  const button = buttons.find((candidate) => candidate.textContent === choice);
  if (!button) throw new Error(`Row "${row}" has no choice "${choice}". Choices: ${buttons.map((one) => one.textContent).join(', ')}`);
  await act(async () => { button.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); });
}

it('puts the reader view settings on the board for CSS to read', async () => {
  const host = await mountBoard();
  expect(board(host).dataset).toMatchObject({
    luma: 'standard',
    scale: 'normal',
    rail: 'on',
    ramp: 'on',
    grouping: 'auto',
    cues: 'on',
    glyph: 'regular',
  });
  // A choice with no word to press is the same as a choice that is not there.
  const choices = [...host.querySelectorAll('.view-choice')];
  expect(choices.length).toBe(17);
  expect(choices.every((button) => button.textContent.trim().length > 0)).toBe(true);
  expect(host.querySelectorAll('.view-choice[aria-pressed="true"]').length).toBe(7);
});

it('breaks a letter track into balanced runs and at word gaps', async () => {
  const host = await mountBoard();
  const [eleven, words] = tracks(host);
  expect(runsIn(eleven)).toEqual([
    { letters: 4, wordEnd: false },
    { letters: 4, wordEnd: false },
    { letters: 3, wordEnd: false },
  ]);
  expect(runsIn(words)).toEqual([
    { letters: 4, wordEnd: true },
    { letters: 3, wordEnd: true },
    { letters: 4, wordEnd: false },
  ]);
});

it('names where words begin and which black squares open a slot', async () => {
  const host = await mountBoard();
  expect(host.querySelector(".grid-cell[data-start~='across']")).not.toBeNull();
  expect(host.querySelector(".grid-cell[data-start~='down']")).not.toBeNull();
  const black = [...host.querySelectorAll('.grid-cell.black-cell')].find((cell) => cell.getAttribute('style'));
  expect(black.getAttribute('style')).toMatch(/--open-[nesw]/);
});

it('tints every clue number with its own place on the ramp', async () => {
  const host = await mountBoard();
  const numbers = [...host.querySelectorAll('.clue-number')];
  expect(numbers.length).toBeGreaterThan(1);
  expect(numbers.every((number) => /--clue-ramp/.test(number.getAttribute('style') || ''))).toBe(true);
  expect(new Set(numbers.map((number) => number.getAttribute('style'))).size).toBeGreaterThan(1);
});

it('shares one rank between the ladder row, its chip, and the numbered square', async () => {
  const host = await mountBoard();
  const rampOf = (element) => /--clue-ramp:\s*([^;\s]+)/.exec(element.getAttribute('style') || '')?.[1];
  const rows = [...host.querySelectorAll('#across li, #down li')];
  expect(rows.length).toBeGreaterThan(1);
  for (const row of rows) {
    expect(rampOf(row)).toBeDefined();
    expect(rampOf(row.querySelector('.clue-number'))).toBe(rampOf(row));
  }
  const indices = [...host.querySelectorAll('.clue-index')];
  expect(indices.length).toBeGreaterThan(0);
  for (const index of indices) {
    const cellRamp = rampOf(index.closest('.grid-cell'));
    expect(cellRamp).toBeDefined();
    const chips = [...host.querySelectorAll('.clue-number')].filter((chip) => chip.textContent === index.textContent);
    expect(chips.length).toBeGreaterThan(0);
    for (const chip of chips) expect(rampOf(chip)).toBe(cellRamp);
  }
});

it("lights the selection in the active clue's rank, not the square's own", async () => {
  const host = await mountBoard();
  const { app } = controllers[controllers.length - 1];
  const down = app.crossword.find((entry) => entry.direction === 'down');
  await act(async () => { app.handle_clue_click({}, down); });
  const activeRamp = /--clue-ramp:\s*([^;\s]+)/.exec(
    host.querySelector('#down li.highlighted-clue .clue-number').getAttribute('style') || '',
  )?.[1];
  expect(activeRamp).toBeDefined();
  const selected = [...host.querySelectorAll('.grid-cell[data-entry-index]')];
  expect(selected.length).toBe(down.characters.length);
  for (const cell of selected) {
    expect(/--clue-ramp:\s*([^;\s]+)/.exec(cell.getAttribute('style') || '')?.[1]).toBe(activeRamp);
  }
  // The closing square wears its own number but burns with the active word.
  const borrowed = selected.find((cell) => cell.querySelector('.clue-index')?.textContent === '2');
  expect(borrowed).toBeDefined();
  const boxes = [...host.querySelectorAll('.state[data-entry-index]')];
  expect(boxes.length).toBeGreaterThan(0);
  for (const box of boxes) {
    expect(/--clue-ramp:\s*([^;\s]+)/.exec(box.getAttribute('style') || '')?.[1]).toBe(activeRamp);
  }
});

it('hands the appearance back to CSS when a view choice changes', async () => {
  const host = await mountBoard();
  await choose(host, 'Letter track', 'Solid');
  expect(board(host).dataset.grouping).toBe('none');
  expect(runsIn(tracks(host)[0])).toEqual([{ letters: 11, wordEnd: false }]);
  expect(JSON.parse(localStorage.getItem(VIEW_SETTINGS_KEY))).toMatchObject({ grouping: 'none' });

  await choose(host, 'Square notches', 'Off');
  expect(board(host).dataset.cues).toBe('off');
  expect(host.querySelector('.grid-cell[data-start]')).toBeNull();
  expect([...host.querySelectorAll('.grid-cell.black-cell')].some((cell) => /--open-/.test(cell.getAttribute('style') || ''))).toBe(false);

  await choose(host, 'Number colours', 'Off');
  expect(board(host).dataset.ramp).toBe('off');
  expect(host.querySelector('.clue-number').getAttribute('style') || '').not.toMatch(/--clue-ramp/);
  expect(JSON.parse(localStorage.getItem(VIEW_SETTINGS_KEY))).toMatchObject({ cues: false, grouping: 'none', ramp: false });
});

it('resizes the board without losing the settings it started with', async () => {
  const host = await mountBoard();
  await choose(host, 'Board size', 'L');
  expect(board(host).dataset).toMatchObject({ scale: 'full', grouping: 'auto', cues: 'on' });
  expect(JSON.parse(localStorage.getItem(VIEW_SETTINGS_KEY))).toMatchObject({ scale: 'full' });
});
