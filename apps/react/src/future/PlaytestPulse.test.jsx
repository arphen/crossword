// @vitest-environment jsdom
import React, { act } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { createRoot } from 'react-dom/client';
import PlaytestPulse from './PlaytestPulse';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root;
let container;

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  container?.remove();
  root = null;
  container = null;
  vi.unstubAllGlobals();
});

it('collects the bounded postgame pulse and restores its saved state', async () => {
  vi.stubGlobal('crypto', {
    randomUUID: () => '11111111-1111-4111-8111-111111111111',
  });
  const fetchImpl = vi.fn(async () => ({
    ok: true,
    json: async () => ({ revision: 3, replayed: false }),
  }));
  vi.stubGlobal('fetch', fetchImpl);
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () =>
    root.render(<PlaytestPulse sessionId="session-1" savedPulse={null} />),
  );

  const button = (text) =>
    [...container.querySelectorAll('button')].find((item) => item.textContent === text);
  await act(async () => button('Yes').click());
  await act(async () => button('More footholds').click());
  await act(async () => button('A clue felt opaque').click());
  await act(async () => button('Save this signal').click());
  await vi.waitFor(() => expect(container.textContent).toContain('Saved for this game'));
  expect(fetchImpl).toHaveBeenCalledOnce();
  expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toMatchObject({
    worth: 'yes',
    returnIntent: 'more-footholds',
    roughEdge: 'too-opaque',
  });
});
