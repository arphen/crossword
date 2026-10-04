import { afterEach, expect, it, vi } from 'vitest';
import {
  submitPlaytestPulse,
  submitReflectionAction,
  submitReflectionResponse,
} from './reflection';

afterEach(() => vi.restoreAllMocks());

it('binds the response to its exact session, card version, and shown position', async () => {
  const fetchImpl = vi.fn(async () => ({
    ok: true,
    json: async () => ({ revision: 4 }),
  }));
  const card = { cardId: 'reflection-discovery-v1', version: 3 };
  const { payload, result } = await submitReflectionResponse({
    sessionId: 'session-1',
    card,
    shownPosition: 1,
    response: 'not-for-me',
    fetchImpl,
    cryptoApi: { randomUUID: () => 'response-1' },
    now: () => new Date('2026-09-26T12:00:00.000Z'),
  });

  expect(payload).toEqual({
    schemaVersion: 1,
    responseId: 'response-1',
    sessionId: 'session-1',
    cardId: 'reflection-discovery-v1',
    cardVersion: 3,
    shownPosition: 1,
    recordedAt: '2026-09-26T12:00:00.000Z',
    response: 'not-for-me',
  });
  expect(fetchImpl).toHaveBeenCalledWith(
    '/api/future/sessions/session-1/reflections/reflection-discovery-v1/response',
    expect.objectContaining({ method: 'POST', credentials: 'same-origin' }),
  );
  expect(result.revision).toBe(4);
});

it('does not turn pass into an explicit preference or accept a card outside its deck positions', async () => {
  const fetchImpl = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
  const card = { cardId: 'reflection-wordplay-v1', version: 1 };
  await submitReflectionResponse({
    sessionId: 'session-1',
    card,
    shownPosition: 0,
    response: 'pass',
    fetchImpl,
    cryptoApi: { randomUUID: () => 'response-2' },
  });
  expect(JSON.parse(fetchImpl.mock.calls[0][1].body).response).toBe('pass');
  await expect(
    submitReflectionResponse({
      sessionId: 'session-1',
      card,
      shownPosition: 3,
      response: 'keep',
      fetchImpl,
    }),
  ).rejects.toThrow('does not match');
  expect(fetchImpl).toHaveBeenCalledOnce();
});

it('surfaces a host rejection without treating the response as saved', async () => {
  const fetchImpl = vi.fn(async () => ({
    ok: false,
    json: async () => ({ error: 'The card version changed.' }),
  }));
  await expect(
    submitReflectionResponse({
      sessionId: 'session-1',
      card: { cardId: 'card', version: 1 },
      shownPosition: 0,
      response: 'keep',
      fetchImpl,
      cryptoApi: { randomUUID: () => 'response-3' },
    }),
  ).rejects.toThrow('The card version changed.');
});

it('retracts and restores a saved signal without replacing its response evidence', async () => {
  const fetchImpl = vi.fn(async () => ({
    ok: true,
    json: async () => ({ revision: 7 }),
  }));
  const { payload, result } = await submitReflectionAction({
    sessionId: 'session-1',
    cardId: 'reflection-challenge-v1',
    responseId: 'response-4',
    action: 'retract',
    fetchImpl,
    cryptoApi: { randomUUID: () => 'action-1' },
    now: () => new Date('2026-09-26T12:01:00.000Z'),
  });

  expect(payload).toEqual({
    schemaVersion: 1,
    actionId: 'action-1',
    targetResponseId: 'response-4',
    recordedAt: '2026-09-26T12:01:00.000Z',
    action: 'retract',
  });
  expect(fetchImpl).toHaveBeenCalledWith(
    '/api/future/sessions/session-1/reflections/reflection-challenge-v1/responses/response-4/actions',
    expect.objectContaining({ method: 'POST' }),
  );
  expect(result.revision).toBe(7);
});

it('binds the playtest pulse to the finished session and keeps the signal bounded', async () => {
  const fetchImpl = vi.fn(async () => ({
    ok: true,
    json: async () => ({ revision: 8, replayed: false }),
  }));
  const { payload, result } = await submitPlaytestPulse({
    sessionId: '22222222-2222-4222-8222-222222222222',
    worth: 'yes',
    returnIntent: 'more-footholds',
    roughEdge: 'too-opaque',
    fetchImpl,
    cryptoApi: { randomUUID: () => '11111111-1111-4111-8111-111111111111' },
    now: () => new Date('2026-09-28T12:00:00.000Z'),
  });
  expect(payload).toEqual({
    schemaVersion: 1,
    pulseId: '11111111-1111-4111-8111-111111111111',
    sessionId: '22222222-2222-4222-8222-222222222222',
    recordedAt: '2026-09-28T12:00:00.000Z',
    worth: 'yes',
    returnIntent: 'more-footholds',
    roughEdge: 'too-opaque',
  });
  expect(fetchImpl).toHaveBeenCalledWith(
    '/api/future/sessions/22222222-2222-4222-8222-222222222222/playtest-pulse',
    expect.objectContaining({ method: 'POST', credentials: 'same-origin' }),
  );
  expect(result.revision).toBe(8);
});
