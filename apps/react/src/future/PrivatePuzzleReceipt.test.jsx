// @vitest-environment jsdom
import React, { act } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { createRoot } from 'react-dom/client';
import PrivatePuzzleReceipt from './PrivatePuzzleReceipt';

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

it('reopens a bounded construction receipt after the game', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        version: 'private-puzzle-provenance-v1',
        provenance: {
          model: 'gemma4:26b',
          weekday: 'wednesday',
          fillQuality: {
            meanScore: 78.1,
            minimumScore: 55,
            weakCount: 19,
          },
          clueQuality: { checkedCount: 78, issueCount: 0 },
          clueDiversity: {
            status: 'varied',
            nonDefinitionFamilies: ['pun', 'spoken-equivalent'],
          },
          semanticClueChallenge: { enabled: true },
          themeExposure: { freshThemeCount: 4 },
        },
      }),
    })),
  );
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(<PrivatePuzzleReceipt sessionId="session-1" profileId="profile-1" />),
  );
  await vi.waitFor(() => expect(host.textContent).toContain('How this game was made.'));
  expect(host.textContent).toContain('Wednesday · gemma4:26b');
  expect(host.textContent).toContain('78.1');
  expect(host.textContent).toContain('19');
  expect(host.textContent).toContain('bounded');
  expect(host.textContent).toContain('4fresh themes');
  expect(host.textContent).toContain('varied (2)surface mix');
  expect(host.textContent).toContain('does not grade the solver');
  expect(fetch).toHaveBeenCalledWith(
    '/api/future/sessions/session-1/private-provenance?profileId=profile-1',
    expect.objectContaining({ cache: 'no-store' }),
  );
});

it('surfaces the Thursday mechanic receipt without calling it a quality grade', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        version: 'private-puzzle-provenance-v1',
        provenance: {
          model: 'gemma4:26b',
          weekday: 'thursday',
          mechanicEvaluation: { status: 'pass' },
          fillQuality: {},
          clueQuality: {},
          semanticClueChallenge: {},
        },
      }),
    })),
  );
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(<PrivatePuzzleReceipt sessionId="session-2" profileId="profile-1" />),
  );
  await vi.waitFor(() => expect(host.textContent).toContain('theme mechanic'));
  expect(host.textContent).toContain('checked');
  expect(host.textContent).toContain('does not grade the solver');
});

it('keeps missing receipts fail-open for private play', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, json: async () => ({}) })));
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () =>
    root.render(<PrivatePuzzleReceipt sessionId="session-1" profileId="profile-1" />),
  );
  await vi.waitFor(() => expect(host.firstChild).toBeNull());
});
