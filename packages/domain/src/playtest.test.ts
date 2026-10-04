import { describe, expect, it } from 'vitest';
import { validatePlaytestPulse } from './playtest';

const pulse = {
  schemaVersion: 1,
  pulseId: '11111111-1111-4111-8111-111111111111',
  sessionId: '22222222-2222-4222-8222-222222222222',
  recordedAt: '2026-09-28T12:00:00.000Z',
  worth: 'yes',
  returnIntent: 'same-world-new-angle',
  roughEdge: 'none',
} as const;

describe('playtest pulse contract', () => {
  it('accepts the bounded game-specific signal', () => {
    expect(validatePlaytestPulse(pulse)).toBe(true);
  });

  it('rejects unknown fields and malformed values', () => {
    expect(validatePlaytestPulse({ ...pulse, extra: true })).toBe(false);
    expect(validatePlaytestPulse({ ...pulse, roughEdge: 'free text' })).toBe(false);
    expect(validatePlaytestPulse({ ...pulse, recordedAt: '2026-09-28 12:00:00' })).toBe(false);
  });
});
