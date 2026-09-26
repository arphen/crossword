// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import { futureOptions } from './FutureSolver';

it('starts at the chosen weekday without writing the daily preference', () => {
  const socket = { on: vi.fn() };
  const dependencies = { socket };
  const future = futureOptions(dependencies, 'thursday');
  localStorage.setItem('selectedWeekday', 'monday');
  future.watch.selectedWeekday('thursday');
  expect(localStorage.getItem('selectedWeekday')).toBe('monday');
  const app = {
    updateCachedCounts: vi.fn(),
    loadCrossword: vi.fn(),
    handleOnlineStatus: vi.fn(),
    handleDocumentClick: vi.fn(),
  };
  future.created.call(app);
  expect(app.loadCrossword).toHaveBeenCalledWith('thursday');
  expect(app.selectedWeekday).toBe('thursday');
  expect(future.computed.weekdayOptions()).toHaveLength(7);
  window.removeEventListener('online', app.handleOnlineStatus);
  window.removeEventListener('offline', app.handleOnlineStatus);
  document.removeEventListener('click', app.handleDocumentClick);
});
