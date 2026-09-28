// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import GameHistory, {
  calibrationSummary,
  gameHistoryStats,
  playtestHistorySummary,
  personalizationHistorySummary,
} from './GameHistory';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let host;
let root;

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('renders an answer-free route summary for saved games', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({
      history: [{
        sessionId: 'session-1',
        title: 'A remembered thread',
        createdAt: '2026-09-28T12:00:00.000Z',
        weekday: 'wednesday',
        model: 'gemma4:26b',
        finished: true,
        analysis: {
          version: 'private-session-analysis-summary-v1',
          independentCount: 4,
          supportedCount: 2,
          assistedCount: 1,
        },
        personalization: {
          version: 'private-history-personalization-v1',
          epistemeRevision: 4,
          claimCount: 2,
          associationCount: 1,
          recentExposureCount: 3,
          languageThread: true,
          associationSteering: { eligibleCount: 1 },
          clueDiversity: { status: 'varied', repairRewrittenCount: 2 },
        },
      }],
    }),
  })));
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(<GameHistory profileId="profile-1" open />));
  await vi.waitFor(() => expect(host.textContent).toContain('A remembered thread'));
  expect(host.textContent).toContain('2026-09-28 · Wednesday · gemma4:26b');
  expect(host.textContent).toContain('4 independent · 2 supported · 1 assisted');
  expect(host.textContent).toContain('Episteme revision 4 · signals · threads · recent words · language · 1 active path · varied clue surfaces · 2 surface repairs');
  expect(host.textContent).not.toContain('SECRET');
  expect(fetch).toHaveBeenCalledWith(
    '/api/future/profile/profile-1/history?limit=12',
    expect.objectContaining({ cache: 'no-store' }),
  );
});

it('keeps incomplete history explicit and bounded', () => {
  expect(gameHistoryStats({ finished: false })).toBe('In progress');
  expect(gameHistoryStats({ finished: true })).toBe('Replay saved · analysis pending');
});

it('keeps malformed personalization history silent', () => {
  expect(personalizationHistorySummary({})).toBe('');
  expect(
    personalizationHistorySummary({
      personalization: {
        version: 'private-history-personalization-v1',
        epistemeRevision: 2,
        associationSteering: { eligibleCount: 2 },
        clueDiversity: { status: 'varied', repairRewrittenCount: 1 },
      },
    }),
  ).toBe('Episteme revision 2 · 2 active paths · varied clue surfaces · 1 surface repair');
  expect(
    personalizationHistorySummary({
      personalization: { version: 'wrong', epistemeRevision: 2 },
    }),
  ).toBe('');
});

it('summarizes the bounded game-specific pulse without interpreting the player', () => {
  expect(
    playtestHistorySummary({
      playtest: {
        schemaVersion: 1,
        worth: 'yes',
        returnIntent: 'more-footholds',
        roughEdge: 'too-opaque',
      },
    }),
  ).toBe('Playtest: worth another · next: more footholds · edge: too opaque');
  expect(playtestHistorySummary({ playtest: { schemaVersion: 1, worth: 'yes' } })).toBe('');
});

it('describes observed calibration without calling it a probability', () => {
  expect(
    calibrationSummary({
      version: 'private-play-calibration-report-v1',
      sessionCount: 2,
      requiredSessions: 3,
      totals: { completionRate: 0.5, supportRate: 0.25 },
    }),
  ).toContain('more traces');
  expect(
    calibrationSummary({
      version: 'private-play-calibration-report-v1',
      sessionCount: 3,
      requiredSessions: 3,
      totals: { completionRate: 0.667, supportRate: 0.333 },
    }),
  ).toBe(
    'Observed across 3 finished games: 67% completed · 33% used crossings or assistance.',
  );
});

it('offers a bounded calibration trace download', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ history: [], calibration: null }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ version: 'private-play-calibration-export-v1', traces: [] }),
    });
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn(() => 'blob:calibration'),
    revokeObjectURL: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(<GameHistory profileId="profile-1" open />));
  await vi.waitFor(() => expect(host.textContent).toContain('Download calibration trace'));
  await act(async () => host.querySelector('button').click());
  await vi.waitFor(() => expect(host.textContent).toContain('Saved locally.'));
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    '/api/future/profile/profile-1/calibration-export?limit=50',
    expect.objectContaining({ cache: 'no-store' }),
  );
});
