// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import {
  futureOptions,
  reflectionStorageValue,
  savedReflectionSessionId,
} from './FutureSolver';

it('binds saved reflection sessions to the puzzle identity', () => {
  const raw = reflectionStorageValue('session-1', 'puzzle-1');
  expect(savedReflectionSessionId(raw, 'puzzle-1')).toBe('session-1');
  expect(savedReflectionSessionId(raw, 'puzzle-2')).toBeNull();
  expect(savedReflectionSessionId('session-1', 'puzzle-1')).toBeNull();
  expect(savedReflectionSessionId('{bad json', 'puzzle-1')).toBeNull();
});

it('starts with a blank local board without fetching the daily preference', () => {
  const socket = { on: vi.fn() };
  const dependencies = { socket };
  const onWeekdayChange = vi.fn();
  const future = futureOptions(dependencies, 'thursday', onWeekdayChange);
  localStorage.setItem('selectedWeekday', 'monday');
  future.watch.selectedWeekday('thursday');
  future.watch.selectedWeekday('invented');
  expect(onWeekdayChange).toHaveBeenCalledOnce();
  expect(onWeekdayChange).toHaveBeenCalledWith('thursday');
  expect(localStorage.getItem('selectedWeekday')).toBe('monday');
  const app = {
    updateCachedCounts: vi.fn(),
    loadCrossword: vi.fn(),
    handleOnlineStatus: vi.fn(),
    handleDocumentClick: vi.fn(),
  };
  future.created.call(app);
  expect(app.loadCrossword).not.toHaveBeenCalled();
  expect(app.selectedWeekday).toBe('thursday');
  expect(future.computed.weekdayOptions()).toHaveLength(7);
  expect(future.data().currentPuzzleProvenance).toBeNull();
  window.removeEventListener('online', app.handleOnlineStatus);
  window.removeEventListener('offline', app.handleOnlineStatus);
  document.removeEventListener('click', app.handleDocumentClick);
});

it('clears the custom-puzzle marker before loading the daily puzzle', async () => {
  const future = futureOptions({ socket: { on: vi.fn() } }, 'wednesday');
  const app = {
    currentPuzzleProvenance: { source: 'local-ollama-xfill' },
    isOffline: true,
    loadCachedCrossword: vi.fn(),
  };
  await future.methods.loadCrossword.call(app, 'friday');
  expect(app.currentPuzzleProvenance).toBeNull();
  expect(app.loadCachedCrossword).toHaveBeenCalledWith('friday');
});
