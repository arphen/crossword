// @vitest-environment jsdom
import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import ProfileNarrativePanel from './ProfileNarrativePanel';
import { normalizeProfileNarrative } from './profileNarrative';

let root;
let host;
const body = {
  status: 'ready',
  stale: false,
  receipt: {
    epistemeRevision: 3,
    sourceDigest: 'a'.repeat(64),
    generation: {
      returnedModel: 'gemma4:26b',
      promptVersion: 'private-profile-narrative-prompt-v1',
      digest: 'b'.repeat(64),
    },
  },
  narrative: {
    version: 'private-profile-narrative-v1',
    paragraphs: [{ text: 'A field of echoes and crossings.', evidenceIds: ['starting-profile'] }],
    openQuestions: [{ text: 'What will recur next?', evidenceIds: [] }],
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

it('accepts only the versioned field-note shape', () => {
  expect(normalizeProfileNarrative(body).narrative.paragraphs).toHaveLength(1);
  expect(normalizeProfileNarrative({ ...body, narrative: { ...body.narrative, version: 'old' } })).toBeNull();
});

it('loads and renders a field note, then can regenerate it', async () => {
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => body })
    .mockResolvedValueOnce({ ok: true, json: async () => body });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<ProfileNarrativePanel profileId="profile-1" open />));
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
  expect(host.textContent).toContain('A field of echoes and crossings.');
  expect(host.textContent).toContain('Written locally with gemma4:26b');
  await act(async () => {
    host.querySelector('button').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(fetchImpl).toHaveBeenCalledTimes(2);
  expect(fetchImpl.mock.calls[1][1]).toMatchObject({ method: 'POST' });
  expect(JSON.parse(fetchImpl.mock.calls[1][1].body).requestId).toMatch(/^[0-9a-f-]{36}$/i);
});

it('keeps stale suggestions visible but disables acceptance until a fresh note is written', async () => {
  const stale = {
    ...body,
    stale: true,
    narrative: {
      ...body.narrative,
      suggestions: [{
        conceptId: 'association:en:acoustic',
        label: 'acoustic',
        kind: 'taste',
        action: 'seek',
        rationale: 'A sound-adjacent path remains open.',
        evidenceIds: ['starting-profile'],
      }],
    },
  };
  const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => stale });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<ProfileNarrativePanel profileId="profile-1" open />));
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
  const suggestionButton = [...host.querySelectorAll('button')].find((button) => button.textContent.includes('Keep this path'));
  expect(suggestionButton?.disabled).toBe(true);
  expect(host.textContent).toContain('The evidence has changed since this note');
});
