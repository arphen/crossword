// @vitest-environment jsdom
import React, { act } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { createRoot } from 'react-dom/client';
import AssistancePanel from './AssistancePanel';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const entry = {
  direction: 'across',
  clue_number: 1,
  clue_text: 'Feline?',
  start_x: 0,
  start_y: 0,
  characters: [{ letters: 'C' }, { letters: 'A' }, { letters: 'T' }],
};
const crossing = {
  direction: 'down',
  clue_number: 1,
  clue_text: 'Vehicle',
  start_x: 0,
  start_y: 0,
  characters: [{ letters: 'C' }, { letters: 'A' }, { letters: 'R' }],
};

let host;
let root;

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  host?.remove();
  root = null;
  host = null;
});

it('reveals only the requested amount and journals every revealed cell', async () => {
  const app = {
    grid: [['C', '', '']],
    crossword: [entry, crossing],
    revealsUsed: 0,
    score: 100,
    isChecking: false,
  };
  const revealed = [];
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(
      <AssistancePanel
        app={app}
        entry={entry}
        onHintShown={vi.fn()}
        onCellRevealed={(cell) => revealed.push(cell)}
      />,
    ),
  );

  for (const label of ['How to read this clue', 'A little more context', 'Suggest a crossing']) {
    await act(async () => host.querySelector('button').click());
    expect(host.textContent).toContain(label);
  }
  await act(async () => host.querySelector('button').click());
  expect(app.grid[0][0]).toBe('C');
  expect(app.grid[0][1]).toBe('A');
  expect(revealed).toHaveLength(1);
  expect(app.revealsUsed).toBe(1);

  await act(async () => host.querySelector('button').click());
  expect(app.grid[0]).toEqual(['C', 'A', 'T']);
  expect(revealed).toHaveLength(2);
  expect(app.revealsUsed).toBe(2);
});
