// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { createOptions, focusCell, focusEntryStart } from './desktop';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function inputMock() {
  const focus = vi.fn();
  return { element: { focus, scrollIntoView: vi.fn() }, focus };
}

it('focuses the live node synchronously with the scroll deferred', () => {
  const { element, focus } = inputMock();
  const nextTick = vi.fn();
  const controller = { $refs: { 'input-2-3': [element] }, $nextTick: nextTick };

  expect(focusCell(controller, 2, 3, { deferScroll: true })).toBe(true);
  expect(focus).toHaveBeenCalledTimes(1);
  expect(focus.mock.calls[0][0]).toEqual({ preventScroll: true });
  expect(nextTick).not.toHaveBeenCalled();
  expect(element.scrollIntoView).not.toHaveBeenCalled();
});

it('falls back to post-commit focus while the grid is still loading', () => {
  const nextTick = vi.fn();
  const controller = { $refs: {}, $nextTick: nextTick };

  expect(focusCell(controller, 0, 0, { deferScroll: true })).toBe(false);
  expect(nextTick).toHaveBeenCalledTimes(1);
});

it('keeps the native scroll for adjacent moves', () => {
  const { element, focus } = inputMock();
  const controller = { $refs: { 'input-4-4': [element] }, $nextTick: vi.fn() };

  expect(focusCell(controller, 4, 4)).toBe(true);
  expect(focus).toHaveBeenCalledTimes(1);
  expect(focus.mock.calls[0]).toEqual([]);
});

it('clue clicks land on the entry start with a deferred scroll', () => {
  const methods = createOptions({
    axios: {},
    socket: {},
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    requestAnimationFrame,
    cancelAnimationFrame,
  }).methods;
  const { element, focus } = inputMock();
  const app = {
    direction: 'across',
    activeClueNumber: null,
    activeDirection: null,
    $refs: { 'input-0-0': [element] },
    $nextTick: vi.fn(),
  };

  methods.handle_clue_click.call(app, {}, {
    direction: 'down',
    clue_number: 1,
    start_x: 0,
    start_y: 0,
  });

  expect(app.direction).toBe('down');
  expect(app.activeClueNumber).toBe(1);
  expect(focus).toHaveBeenCalledTimes(1);
  expect(app.$nextTick).not.toHaveBeenCalled();
  expect(focusEntryStart(app, { direction: 'down', start_x: 0, start_y: 0 })).toBe(true);
  expect(focus).toHaveBeenCalledTimes(2);
});
