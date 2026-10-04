// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import ReflectionCards from './ReflectionCards';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const deck = {
  sessionId: 'session-1',
  cards: [
    {
      cardId: 'wordplay',
      version: 1,
      text: 'A turn of phrase.',
      interpretation: {
        keep: 'More play.',
        notForMe: 'Less play.',
        pass: 'Undecided.',
      },
    },
    {
      cardId: 'discovery',
      version: 1,
      text: 'A fair way in.',
      interpretation: {
        keep: 'More discoveries.',
        notForMe: 'Fewer obscure terms.',
        pass: 'Undecided.',
      },
    },
    {
      cardId: 'challenge',
      version: 1,
      text: 'A small click.',
      interpretation: {
        keep: 'Keep challenge.',
        notForMe: 'Ease the friction.',
        pass: 'Undecided.',
      },
    },
  ],
};

let container;
let root;

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  container?.remove();
  root = null;
  container = null;
  vi.unstubAllGlobals();
});

it('saves an indirect response and lets the player retract and restore it', async () => {
  vi.stubGlobal('crypto', {
    randomUUID: vi
      .fn()
      .mockReturnValueOnce('response-1')
      .mockReturnValueOnce('action-1')
      .mockReturnValueOnce('action-2'),
  });
  const requests = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, options) => {
      requests.push({ url, options });
      return {
        ok: true,
        json: async () =>
          url.includes('/response')
            ? {
                revision: requests.length,
                evidence: {
                  mappings: {
                    'not-for-me': [
                      { concept: { label: 'wordplay and misdirection' } },
                    ],
                  },
                },
              }
            : { revision: requests.length },
      };
    }),
  );
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => root.render(<ReflectionCards deck={deck} />));

  const turnAway = [...container.querySelectorAll('button')].find(
    (button) =>
      button.getAttribute('aria-label') === 'Turn away from this impression',
  );
  await act(async () => {
    turnAway.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  await vi.waitFor(() => expect(container.textContent).toContain('Less play.'));
  expect(container.textContent).toContain('Saved to this local episteme.');
  expect(container.textContent).toContain(
    'Episteme receipt · revision 1 · avoid: wordplay and misdirection',
  );

  const undo = [...container.querySelectorAll('button')].find(
    (button) => button.textContent === 'Undo this signal',
  );
  await act(async () =>
    undo.dispatchEvent(new MouseEvent('click', { bubbles: true })),
  );
  await vi.waitFor(() =>
    expect(container.textContent).toContain('no longer steering your profile'),
  );
  expect(container.textContent).toContain(
    'Retraction recorded at episteme revision 2.',
  );

  const restore = [...container.querySelectorAll('button')].find(
    (button) => button.textContent === 'Restore this signal',
  );
  await act(async () =>
    restore.dispatchEvent(new MouseEvent('click', { bubbles: true })),
  );
  await vi.waitFor(() => expect(container.textContent).toContain('Less play.'));
  expect(container.textContent).toContain(
    'Restoration recorded at episteme revision 3.',
  );
  expect(
    requests.map(
      (request) =>
        JSON.parse(request.options.body).action ||
        JSON.parse(request.options.body).response,
    ),
  ).toEqual(['not-for-me', 'retract', 'restore']);
  expect(requests[0].url).toContain('/reflections/wordplay/response');
  expect(requests[1].url).toContain('/responses/response-1/actions');
});

it('maps a touch swipe to a reversible reflection response', async () => {
  vi.stubGlobal('crypto', {
    randomUUID: vi.fn().mockReturnValue('response-swipe'),
  });
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ revision: 4, evidence: { mappings: {} } }),
    })),
  );
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => root.render(<ReflectionCards deck={deck} />));
  const card = container.querySelector('.future-reflection-card');
  const down = new Event('pointerdown', { bubbles: true });
  Object.defineProperties(down, {
    pointerId: { value: 4 },
    pointerType: { value: 'touch' },
    clientX: { value: 120 },
  });
  const up = new Event('pointerup', { bubbles: true });
  Object.defineProperties(up, {
    pointerId: { value: 4 },
    pointerType: { value: 'touch' },
    clientX: { value: 220 },
  });
  await act(async () => {
    card.dispatchEvent(down);
    card.dispatchEvent(up);
    await Promise.resolve();
    await Promise.resolve();
  });
  await vi.waitFor(() => expect(container.textContent).toContain('More play.'));
  expect(fetch).toHaveBeenCalledWith(
    '/api/future/sessions/session-1/reflections/wordplay/response',
    expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('"response":"keep"'),
    }),
  );
});

it('restores saved response state after a session deck is fetched again', async () => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () =>
    root.render(
      <ReflectionCards
        deck={{
          ...deck,
          responses: [
            {
              response: {
                cardId: 'discovery',
                responseId: 'response-2',
                response: 'pass',
              },
              state: 'retracted',
              latestAction: { action: 'retract' },
              actions: [{ action: 'retract' }],
            },
          ],
        }}
      />,
    ),
  );

  expect(container.textContent).toContain(
    'This impression is no longer steering your profile.',
  );
  expect(container.textContent).toContain('Restore this signal');
  expect(
    container.querySelector('[aria-label="Turn away from this impression"]'),
  ).not.toBeNull();
});

it('shows the answer-free replay trace alongside postgame reflections', async () => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () =>
    root.render(
      <ReflectionCards
        deck={{
          ...deck,
          analysisSummary: {
            version: 'private-session-analysis-summary-v1',
            entryCount: 42,
            independentCount: 12,
            supportedCount: 8,
            assistedCount: 3,
            incorrectAttemptCount: 4,
            untouchedCount: 19,
          },
        }}
      />,
    ),
  );

  expect(container.textContent).toContain('A trace, not a verdict.');
  expect(container.textContent).toContain('12independent');
  expect(container.textContent).toContain('42 entries replayed');
  expect(container.textContent).toContain('mastery');
});

it('labels model wording as a local mirror suggestion', async () => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () =>
    root.render(
      <ReflectionCards
        deck={{
          ...deck,
          cards: deck.cards.map((card, index) =>
            index === 0
              ? {
                  ...card,
                  source: 'model',
                  generationReceipt: {
                    model: 'gemma4:26b',
                    promptVersion: 'private-reflection-mirror-prompt-v1',
                  },
                }
              : card,
          ),
        }}
      />,
    ),
  );

  expect(container.textContent).toContain('Local mirror · wording suggestion');
  expect(container.textContent).toContain(
    'gemma4:26b · private-reflection-mirror-prompt-v1',
  );
});
