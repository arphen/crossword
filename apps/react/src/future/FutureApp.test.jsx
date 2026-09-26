// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import FutureApp from './FutureApp';
import { STORAGE_KEY } from './episteme';

vi.mock('./FutureSolver', () => ({
  default: ({ weekday }) => <div data-testid="solver">{weekday}</div>,
}));
let root;
let host;
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, json: async () => ({ profile: {} }) })),
  );
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
const click = (element) =>
  act(async () => {
    element.click();
  });

it('walks the sequence, limits traces, restores progress, and uses the chosen weekday', async () => {
  await mount();
  expect(button('Continue').disabled).toBe(true);
  await click(host.querySelector('[aria-label="A red thread"]'));
  await click(button('Continue'));
  expect(host.querySelector('h1').textContent).toContain('curious company');
  await click(host.querySelector('[aria-label="A tuning fork"]'));
  await click(button('Continue'));
  await click(button('echo'));
  await click(button('moss'));
  await click(button('elsewhere'));
  expect(button('salt').disabled).toBe(true);
  await click(button('Continue'));
  await click(host.querySelector('[aria-label="Thursday"]'));
  expect(JSON.parse(localStorage.getItem(STORAGE_KEY)).weekday).toBe(
    'thursday',
  );
  await act(async () => root.unmount());
  root = createRoot(host);
  await mount();
  expect(host.querySelector('h1').textContent).toBe('Find your rhythm.');
  await click(button('See your beginning'));
  await click(button('tension×'));
  expect(button('tension+').getAttribute('aria-pressed')).toBe('false');
  await click(button('Enter crossword'));
  expect(host.querySelector('[data-testid="solver"]').textContent).toBe(
    'thursday',
  );
  const saved = JSON.parse(fetch.mock.calls[0][1].body);
  expect(saved).toMatchObject({
    object: 'thread',
    companion: 'fork',
    traces: ['echo', 'moss', 'elsewhere'],
    weekday: 'thursday',
    complete: true,
  });
  expect(saved.excluded).toContain('tension');
  expect(localStorage.getItem('selectedWeekday')).toBeNull();
});

it('can skip associations, go back, and still enter with the server unavailable', async () => {
  fetch.mockRejectedValue(new Error('offline'));
  await mount();
  await click(button('Go straight to a puzzle'));
  await click(button('Back'));
  expect(host.querySelector('h1').textContent).toBe('Let a word find you.');
  await click(button('Let this one pass'));
  await click(button('See your beginning'));
  await click(button('Enter crossword'));
  expect(host.querySelector('[data-testid="solver"]')).not.toBeNull();
  expect(JSON.parse(localStorage.getItem(STORAGE_KEY))).toMatchObject({
    complete: true,
    object: null,
    companion: null,
    traces: [],
  });
});
