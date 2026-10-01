// @vitest-environment jsdom
import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import SpecimenLabelPanel from './SpecimenLabelPanel';

let root;
let host;

const ledger = {
  version: 'private-clue-specimen-ledger-v1',
  verdicts: ['leak', 'tautology', 'name-slot', 'pseudo-pun', 'acceptable', 'better-of-pair'],
  records: [
    {
      id: 'sp-tautology-shadier',
      answer: 'SHADIER',
      clue: 'more shady',
      verdict: null,
      pairId: null,
      note: '§0: the comparative is the answer',
      source: 'hand-listed §0',
    },
    {
      id: 'sp-plain-dark',
      answer: 'DARK',
      clue: 'Without light',
      verdict: 'acceptable',
      pairId: null,
      note: null,
      source: 'hand-listed §0',
    },
  ],
  summary: { records: 2, labeled: 1, unlabeled: 1, verdictCounts: { acceptable: 1 }, problems: [] },
};

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function settle() {
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
}

it('offers to prepare the ledger when none exists, then lists surfaces', async () => {
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ error: 'No specimen ledger on this host yet' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ version: 'private-clue-specimen-ledger-v1', summary: { records: 2, labeled: 0, unlabeled: 2, verdictCounts: {}, problems: [] } }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ledger });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<SpecimenLabelPanel open />));
  await settle();
  expect(host.textContent).toContain('Prepare 62 judging surfaces');
  await act(async () => {
    host.querySelector('button').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  await settle();
  expect(host.textContent).toContain('more shady');
  expect(host.textContent).toContain('1 of 2 judged');
});

it('records a verdict and links a pair', async () => {
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ledger })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'sp-tautology-shadier', verdict: 'tautology', summary: { records: 2, labeled: 2, unlabeled: 0, verdictCounts: {}, problems: [] } }),
    })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ pairId: 'pair-a-b', members: ['a', 'b'] }) });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<SpecimenLabelPanel open />));
  await settle();
  const buttons = [...host.querySelectorAll('.future-specimens-verdicts button')];
  const tautology = buttons.find((button) => button.textContent === 'tautology');
  await act(async () => {
    tautology.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(fetchImpl.mock.calls[1][0]).toContain('/sp-tautology-shadier/verdict');
  const allFilter = [...host.querySelectorAll('.future-specimens-filters button')].find(
    (button) => button.textContent === 'all',
  );
  await act(async () => {
    allFilter.click();
  });
  const boxes = [...host.querySelectorAll('input[type="checkbox"]')];
  await act(async () => {
    boxes[0].click();
    boxes[1].click();
  });
  const link = [...host.querySelectorAll('button')].find((button) => button.textContent === 'Link selected pair');
  await act(async () => {
    link.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(fetchImpl.mock.calls[2][0]).toContain('/pairs');
});

it('attests the closed ledger and shows the digest', async () => {
  const closed = { ...ledger, records: ledger.records.map((record) => ({ ...record, verdict: record.verdict || 'acceptable' })) };
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => closed })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ attested: true, pairs: 2, digest: 'sha256:abc', out: 'att.json' }),
    });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<SpecimenLabelPanel open />));
  await settle();
  const attest = [...host.querySelectorAll('button')].find((button) => button.textContent === 'Attest the closed ledger');
  expect(attest).toBeTruthy();
  await act(async () => {
    attest.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(host.textContent).toContain('sha256:abc');
});
