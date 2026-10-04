// @vitest-environment jsdom
import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import SpecimenLabelPanel from './SpecimenLabelPanel';

let root;
let host;

const reference = {
  id: 'sp-tautology-shadier',
  answer: 'SHADIER',
  clue: 'more shady',
  verdict: 'tautology',
  pairId: null,
  note: '§0: the comparative is the answer',
  source: 'hand-listed §0',
  origin: 'spec',
};

const blindOpen = {
  id: 'real-moss-0-candidate',
  answer: 'MOSS',
  clue: 'Green stuff',
  verdict: null,
  pairId: null,
  note: null,
  source: 'real-harvest',
  origin: 'blind',
};

const blindJudged = {
  id: 'real-dark-1-candidate',
  answer: 'DARK',
  clue: 'Without light',
  verdict: 'acceptable',
  pairId: null,
  note: null,
  source: 'real-harvest',
  origin: 'blind',
};

const ledger = {
  version: 'private-clue-specimen-ledger-v1',
  verdicts: ['leak', 'tautology', 'name-slot', 'pseudo-pun', 'acceptable', 'better-of-pair'],
  records: [reference, blindOpen, blindJudged],
  summary: {
    records: 3,
    reference: 1,
    blind: 2,
    blindLabeled: 1,
    blindUnlabeled: 1,
    labeled: 2,
    unlabeled: 1,
    verdictCounts: { acceptable: 1, tautology: 1 },
    problems: [],
  },
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

function verdictButton(name) {
  return [...host.querySelectorAll('.future-specimens-verdicts button')].find((button) =>
    button.textContent.toLowerCase().includes(name),
  );
}

it('offers to prepare the ledger when none exists, then shows the blind queue', async () => {
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ error: 'No specimen ledger on this host yet' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ version: 'private-clue-specimen-ledger-v1', summary: { records: 3, reference: 1, blind: 2, blindLabeled: 0, blindUnlabeled: 2, labeled: 1, unlabeled: 2, verdictCounts: {}, problems: [] } }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ledger });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<SpecimenLabelPanel open />));
  await settle();
  expect(host.textContent).toContain('Prepare the judging surfaces');
  await act(async () => {
    host.querySelector('button').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  await settle();
  expect(host.textContent).toContain('Green stuff');
  expect(host.textContent).toContain('You judge 2 genuine unknowns · 1 done · 1 to go');
  expect(host.textContent).toContain('needs your verdict');
  expect(host.textContent).toContain('just restates the answer');
});

it('records a verdict on the focused blind card', async () => {
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ledger })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'real-moss-0-candidate', verdict: 'acceptable', summary: { records: 3, reference: 1, blind: 2, blindLabeled: 2, blindUnlabeled: 0, labeled: 3, unlabeled: 0, verdictCounts: {}, problems: [] } }),
    });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<SpecimenLabelPanel open />));
  await settle();
  const good = verdictButton('good clue');
  expect(good).toBeTruthy();
  await act(async () => {
    good.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  await settle();
  expect(fetchImpl.mock.calls[1][0]).toContain('/real-moss-0-candidate/verdict');
});

it('shows reference read-only with its spec verdict', async () => {
  const fetchImpl = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ledger });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<SpecimenLabelPanel open />));
  await settle();
  const referenceTab = [...host.querySelectorAll('button')].find((button) => button.textContent.includes('Reference'));
  await act(async () => {
    referenceTab.click();
  });
  expect(host.textContent).toContain('more shady');
  expect(host.textContent).toContain('tautology (spec)');
  expect(host.textContent).toContain('read-only');
});

it('links a suggested same-answer blind pair', async () => {
  const paired = {
    ...ledger,
    records: [
      reference,
      { ...blindOpen, id: 'real-moss-a', clue: 'Green stuff' },
      { ...blindOpen, id: 'real-moss-b', clue: 'Lawn cover' },
    ],
  };
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => paired })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ pairId: 'pair-a-b', members: ['real-moss-a', 'real-moss-b'] }) });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<SpecimenLabelPanel open />));
  await settle();
  const link = [...host.querySelectorAll('button')].find((button) => button.textContent.includes('Link these 2'));
  expect(link).toBeTruthy();
  await act(async () => {
    link.click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(fetchImpl.mock.calls[1][0]).toContain('/pairs');
});

it('attests the closed blind queue and shows the digest', async () => {
  const closed = {
    ...ledger,
    records: ledger.records.map((record) =>
      record.origin !== 'spec' && !record.verdict ? { ...record, verdict: 'acceptable' } : record,
    ),
  };
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => closed })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ attested: true, pairs: 3, digest: 'sha256:abc', out: 'att.json' }),
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
