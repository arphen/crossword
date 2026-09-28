import { describe, expect, it, vi } from 'vitest';
import {
  createCalibrationHypotheses,
  loadCalibrationHypotheses,
  respondToCalibrationHypothesis,
  reviseCalibrationHypothesisResponse,
} from './calibrationHypothesesApi';

const calibrationId = '00000000-0000-4000-8000-000000000001';
const uuid = '00000000-0000-4000-8000-000000000002';

function response(status, body = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
  };
}

function cryptoApi() {
  return { randomUUID: vi.fn(() => uuid) };
}

describe('calibration hypothesis API client', () => {
  it('loads a persisted deck without triggering generation', async () => {
    const deck = { deck: { deckId: 'deck-1', items: [] }, responses: {} };
    const fetchImpl = vi.fn(async () => response(200, deck));

    await expect(
      loadCalibrationHypotheses({ calibrationId, fetchImpl }),
    ).resolves.toEqual(deck);
    expect(fetchImpl).toHaveBeenCalledWith(
      `/api/future/calibrations/${calibrationId}/hypotheses`,
      expect.objectContaining({
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      }),
    );
  });

  it('treats a missing deck as an empty state', async () => {
    const fetchImpl = vi.fn(async () => response(404, { error: 'Not found' }));
    await expect(
      loadCalibrationHypotheses({ calibrationId, fetchImpl }),
    ).resolves.toBeNull();
  });

  it('creates the optional deck with an explicit empty JSON object', async () => {
    const payload = { deck: { deckId: 'deck-1' }, responses: {} };
    const fetchImpl = vi.fn(async () => response(200, payload));

    await expect(
      createCalibrationHypotheses({ calibrationId, fetchImpl }),
    ).resolves.toEqual(payload);
    expect(fetchImpl).toHaveBeenCalledWith(
      `/api/future/calibrations/${calibrationId}/hypotheses`,
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({}),
      }),
    );
  });

  it('submits only a response to the frozen proposal and returns its idempotency key', async () => {
    const fetchImpl = vi.fn(async () => response(200, { responses: {} }));
    const submitted = await respondToCalibrationHypothesis({
      calibrationId,
      proposalId: 'hypothesis/1',
      deckId: 'deck-1',
      response: 'not-for-me',
      fetchImpl,
      cryptoApi: cryptoApi(),
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      `/api/future/calibrations/${calibrationId}/hypotheses/hypothesis%2F1/response`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          responseId: uuid,
          deckId: 'deck-1',
          response: 'not-for-me',
        }),
      }),
    );
    expect(submitted.payload.responseId).toBe(uuid);
  });

  it('sends an immutable retract or restore action by its saved response ID', async () => {
    const fetchImpl = vi.fn(async () => response(200, { responses: {} }));
    await reviseCalibrationHypothesisResponse({
      calibrationId,
      proposalId: 'thread-1',
      responseId: uuid,
      action: 'retract',
      fetchImpl,
      cryptoApi: cryptoApi(),
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      `/api/future/calibrations/${calibrationId}/hypotheses/thread-1/responses/${uuid}/actions`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ actionId: uuid, action: 'retract' }),
      }),
    );
  });

  it('rejects invalid stances before making a request', async () => {
    const fetchImpl = vi.fn();
    await expect(
      respondToCalibrationHypothesis({
        calibrationId,
        proposalId: 'thread-1',
        deckId: 'deck-1',
        response: 'diagnose-me',
        fetchImpl,
        cryptoApi: cryptoApi(),
      }),
    ).rejects.toThrow('response is invalid');
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it('surfaces local-host errors without inventing a saved response', async () => {
    const fetchImpl = vi.fn(async () =>
      response(503, { error: 'Local model unavailable' }),
    );
    await expect(
      createCalibrationHypotheses({ calibrationId, fetchImpl }),
    ).rejects.toThrow('Local model unavailable');
  });
});
