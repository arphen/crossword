// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import LearningReview from './LearningReview';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let host;
let root;

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.unstubAllGlobals();
});

it('keeps an unassisted recall distinct from an answer-assisted response', async () => {
  const requests = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, options) => {
      requests.push({ url, options });
      if (url.includes('/answer?')) {
        return { ok: true, json: async () => ({ answer: 'JA' }) };
      }
      if (options?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({ recorded: true, reviewId: 'review-1' }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          due: [
            {
              taskId: 'private-answer-form:session-1:across-1',
              clue: 'Yes, in German',
              language: 'de',
              length: 2,
              overdueHours: 26,
              taskPack: {
                reviewStatus: 'synthetic-unadmitted',
              },
            },
          ],
        }),
      };
    }),
  );
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(<LearningReview profileId="profile-1" />));
  await vi.waitFor(() => expect(host.textContent).toContain('Yes, in German'));
  expect(host.textContent).toContain('Local fixture · meaning unverified');
  expect(host.textContent).toContain('26h overdue');

  await act(async () => {
    host.querySelector('button').click();
    await Promise.resolve();
  });
  expect(host.textContent).toContain('JA');

  const sawIt = [...host.querySelectorAll('button')].find(
    (button) => button.textContent === 'Saw it',
  );
  await act(async () => {
    sawIt.click();
    await Promise.resolve();
  });
  const post = requests.find((request) => request.options?.method === 'POST');
  expect(JSON.parse(post.options.body)).toMatchObject({
    taskId: 'private-answer-form:session-1:across-1',
    response: 'remembered',
    mode: 'assisted',
  });
});

it('lets a player type an unassisted recall and submit it without revealing', async () => {
  const requests = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, options) => {
      requests.push({ url, options });
      if (options?.method === 'POST') {
        return { ok: true, json: async () => ({ recorded: true }) };
      }
      return {
        ok: true,
        json: async () => ({
          due: [{ taskId: 'task-typed', clue: 'Yes, in German', language: 'de', length: 2 }],
          remaining: 0,
        }),
      };
    }),
  );
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(<LearningReview profileId="profile-1" />));
  await vi.waitFor(() => expect(host.querySelector('input')).not.toBeNull());
  const input = host.querySelector('input');
  const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  setValue.call(input, 'JA');
  await act(async () => {
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await Promise.resolve();
  });
  await vi.waitFor(() => expect(host.querySelector('.future-learning-review-card')).toBeNull());
  const post = requests.find((request) => request.options?.method === 'POST');
  expect(JSON.parse(post.options.body)).toMatchObject({
    taskId: 'task-typed',
    response: 'remembered',
    mode: 'independent',
  });
});

it('starts with a calm due budget and can reveal the next bounded page', async () => {
  const requests = [];
  const item = (index) => ({
    taskId: `task-${index}`,
    clue: `Clue ${index}`,
    language: 'de',
    length: 4,
  });
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      requests.push(url);
      if (url.includes('?limit=6')) {
        return {
          ok: true,
          json: async () => ({ due: [1, 2, 3, 4, 5, 6].map(item), remaining: 6 }),
        };
      }
      return {
        ok: true,
        json: async () => ({ due: [1, 2, 3].map(item), remaining: 9 }),
      };
    }),
  );
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(<LearningReview profileId="profile-1" />));
  await vi.waitFor(() => expect(host.textContent).toContain('3 of 12 due'));
  expect(host.querySelectorAll('.future-learning-review-card')).toHaveLength(3);

  const more = [...host.querySelectorAll('button')].find(
    (button) => button.textContent === 'Show more recall threads',
  );
  await act(async () => {
    more.click();
    await Promise.resolve();
  });
  expect(requests.some((url) => url.includes('?limit=6'))).toBe(true);
  expect(host.querySelectorAll('.future-learning-review-card')).toHaveLength(6);
  expect(host.textContent).toContain('6 of 12 due');
});

it('waits for the host profile before requesting delayed review', async () => {
  let resolveProfile;
  const profileReady = new Promise((resolve) => {
    resolveProfile = resolve;
  });
  const requests = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      requests.push(url);
      return {
        ok: true,
        json: async () => ({
          due: [{ taskId: 'task-1', clue: 'Yes, in German', language: 'de', length: 2 }],
          remaining: 0,
        }),
      };
    }),
  );
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(<LearningReview profileId="profile-1" profileReady={profileReady} />));
  expect(requests).toHaveLength(0);
  await act(async () => {
    resolveProfile(true);
    await Promise.resolve();
  });
  await vi.waitFor(() => expect(requests).toHaveLength(1));
  expect(host.textContent).toContain('Yes, in German');
});
