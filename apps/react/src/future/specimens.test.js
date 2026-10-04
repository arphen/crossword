import { expect, it, vi } from 'vitest';
import {
  SPECIMEN_VERDICTS,
  attestSpecimens,
  linkPair,
  loadSpecimens,
  normalizeSpecimens,
  recordVerdict,
  seedSpecimens,
} from './specimens';

const record = {
  id: 'sp-tautology-shadier',
  answer: 'SHADIER',
  clue: 'more shady',
  verdict: null,
  pairId: null,
  note: '§0: the comparative is the answer',
  source: 'hand-listed §0',
};

it('accepts only the versioned ledger shape', () => {
  expect(normalizeSpecimens({ version: 'private-clue-specimen-ledger-v1', records: [record] }).records).toHaveLength(1);
  expect(normalizeSpecimens({ version: 'private-clue-specimen-ledger-v1', records: [{ ...record, verdict: 'wrong' }] })).toBeNull();
  expect(normalizeSpecimens({})).toBeNull();
});

it('loads the ledger through fetch', async () => {
  const fetchImpl = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ version: 'private-clue-specimen-ledger-v1', records: [record] }),
  });
  const value = await loadSpecimens({ fetchImpl });
  expect(value.records[0].id).toBe('sp-tautology-shadier');
  expect(fetchImpl).toHaveBeenCalledTimes(1);
});

it('rejects a verdict outside the closed set before any request', async () => {
  const fetchImpl = vi.fn();
  await expect(recordVerdict('sp-1', 'wrong', { fetchImpl })).rejects.toThrow('six closed verdicts');
  expect(fetchImpl).not.toHaveBeenCalled();
});

it('seeds, links, and attests through the API', async () => {
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ version: 'private-clue-specimen-ledger-v1', summary: { records: 14, labeled: 0, unlabeled: 14, verdictCounts: {}, problems: [] } }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ pairId: 'pair-a-b', members: ['a', 'b'] }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ attested: true, pairs: 14, digest: 'sha256:x', out: 'att.json' }) });
  const seeded = await seedSpecimens({ fetchImpl });
  expect(seeded.records).toBe(14);
  const pair = await linkPair('a', 'b', { fetchImpl });
  expect(pair.pairId).toBe('pair-a-b');
  const attested = await attestSpecimens({ fetchImpl });
  expect(attested.digest).toBe('sha256:x');
  expect(SPECIMEN_VERDICTS).toHaveLength(6);
});

it('surfaces an open ledger as a labeling error', async () => {
  const fetchImpl = vi.fn().mockResolvedValue({
    ok: false,
    json: async () => ({ error: 'unlabeled', unlabeled: 3 }),
  });
  await expect(attestSpecimens({ fetchImpl })).rejects.toThrow('3 surfaces still need a verdict');
});
