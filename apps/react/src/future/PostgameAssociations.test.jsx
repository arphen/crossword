// @vitest-environment jsdom
import React, { act } from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createRoot } from 'react-dom/client';
import PostgameAssociations from './PostgameAssociations';

const deck = {
  sessionId: 'session-1',
  paths: [
    {
      associationId: 'association-1',
      phrase: 'river clock',
      relation: 'metaphor',
      explanation: 'A possible meeting of movement and measure.',
    },
  ],
  responses: {},
};

let root;
let host;

beforeEach(() => vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true));

async function mount() {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(<PostgameAssociations deck={deck} />));
}

async function click(button) {
  await act(async () => {
    button.click();
    await Promise.resolve();
    await Promise.resolve();
  });
}

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  host?.remove();
  vi.unstubAllGlobals();
  root = undefined;
  host = undefined;
});

it('presents a possible postgame path and records a response', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ responseId: 'response-1', profileRevision: 4 }),
  });
  vi.stubGlobal('fetch', fetchMock);
  await mount();

  expect(host.textContent).toContain('Where might it lead?');
  expect(host.textContent).toContain('river clock');
  await click(host.querySelector('.future-hypothesis-choice-keep'));
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/future/sessions/session-1/episteme-associations/association-1/response',
    expect.objectContaining({ method: 'POST' }),
  );
  expect(host.textContent).toContain('Kept as a possible thread');
});

it('can follow a kept path once and renders the durable child path', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ responseId: 'response-1', profileRevision: 4 }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        expansions: {
          'association-1': [{
            associationId: 'association-child',
            expansionOf: 'association-1',
            depth: 1,
            phrase: 'clockwork rain',
            relation: 'sound',
            explanation: 'A second possible crossing.',
          }],
        },
      }),
    });
  vi.stubGlobal('fetch', fetchMock);
  await mount();
  await click(host.querySelector('.future-hypothesis-choice-keep'));
  await click([...host.querySelectorAll('button')].find((button) => button.textContent.includes('Follow this thread')));
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/future/sessions/session-1/episteme-associations/association-1/expand',
    expect.objectContaining({ method: 'POST' }),
  );
  expect(host.textContent).toContain('clockwork rain');
  expect(host.textContent).toContain('followed thread');
});

it('maps a touch swipe to the corresponding reversible response', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ responseId: 'response-swipe', profileRevision: 5 }),
  });
  vi.stubGlobal('fetch', fetchMock);
  await mount();
  const card = host.querySelector('.future-hypothesis-card');
  const down = new Event('pointerdown', { bubbles: true });
  Object.defineProperties(down, {
    pointerId: { value: 7 },
    pointerType: { value: 'touch' },
    clientX: { value: 120 },
  });
  const up = new Event('pointerup', { bubbles: true });
  Object.defineProperties(up, {
    pointerId: { value: 7 },
    pointerType: { value: 'touch' },
    clientX: { value: 220 },
  });
  await act(async () => {
    card.dispatchEvent(down);
    card.dispatchEvent(up);
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/future/sessions/session-1/episteme-associations/association-1/response',
    expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('"response":"keep"'),
    }),
  );
  expect(host.textContent).toContain('Kept as a possible thread');
});
