// @vitest-environment jsdom
import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import EpistemeSnapshot from './EpistemeSnapshotView';
import { loadEpistemeSnapshot, normalizeEpistemeSnapshot } from './epistemeSnapshot';

let root;
let host;

const profile = {
  revision: 4,
  evidence: [],
  projection: {
    claims: [{ concept: { conceptId: 'sound', label: 'Sound' }, stance: 'seek' }],
    associations: [{ phrase: 'river stone', response: 'kept' }],
    knowledge: [{ task: { taskId: 'one' } }],
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

it('normalizes only a complete projection', () => {
  expect(normalizeEpistemeSnapshot({ profile })).toMatchObject({ revision: 4 });
  expect(normalizeEpistemeSnapshot({ profile: { revision: 1 } })).toBeNull();
});

it('loads the host snapshot with a same-profile endpoint', async () => {
  const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ profile }) });
  await expect(loadEpistemeSnapshot('profile/1', { fetchImpl })).resolves.toMatchObject({ revision: 4 });
  expect(fetchImpl).toHaveBeenCalledWith(
    '/api/future/profile/profile%2F1/episteme',
    expect.objectContaining({ cache: 'no-store' }),
  );
});

it('renders claims, open threads, revision and the learning boundary', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ profile }) }));
  await act(async () => root.render(<EpistemeSnapshot profileId="profile-1" open />));
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
  expect(host.textContent).toContain('The living episteme');
  expect(host.textContent).toContain('Sound · drawn toward');
  expect(host.textContent).toContain('river stone · kept');
  expect(host.textContent).toContain('revision 4');
  expect(host.textContent).toContain('1 learning thread');
});

it('lets the player correct a claim through the explicit preference route', async () => {
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ profile }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ profile }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ revision: 5 }) });
  const onChanged = vi.fn();
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<EpistemeSnapshot profileId="profile-1" open onChanged={onChanged} />));
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
  const buttons = [...host.querySelectorAll('button')];
  await act(async () => {
    buttons.find((button) => button.textContent === 'Set aside').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(fetchImpl).toHaveBeenCalledTimes(3);
  expect(fetchImpl.mock.calls[2][1]).toMatchObject({ method: 'POST' });
  expect(JSON.parse(fetchImpl.mock.calls[2][1].body).evidence[0].action).toBe('exclude');
  expect(onChanged).toHaveBeenCalledTimes(1);
});

it('lets the player release an explicit claim lock', async () => {
  const lockedProfile = {
    ...profile,
    projection: {
      ...profile.projection,
      claims: [{
        concept: { conceptId: 'sound', label: 'Sound' },
        claimId: 'claim:sound',
        stance: 'seek',
        lockedByUser: true,
      }],
    },
  };
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ profile: lockedProfile }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ profile: lockedProfile }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ revision: 5 }) });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<EpistemeSnapshot profileId="profile-1" open />));
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
  await act(async () => {
    host.querySelector('.future-episteme-claim-release').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(JSON.parse(fetchImpl.mock.calls[2][1].body).evidence[0].action).toBe('clear');
});

it('separates contradictory signals into a tension lane', async () => {
  const conflictedProfile = {
    ...profile,
    projection: {
      ...profile.projection,
      claims: [{
        concept: { conceptId: 'sound', label: 'Sound' },
        claimId: 'claim:sound',
        stance: 'ambivalent',
        adequacy: 'contradictory',
        evidenceIds: ['toward-1'],
        counterEvidenceIds: ['away-1'],
        lockedByUser: false,
      }],
    },
  };
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ profile: conflictedProfile }) }));
  await act(async () => root.render(<EpistemeSnapshot profileId="profile-1" open />));
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
  expect(host.textContent).toContain('Tensions');
  expect(host.textContent).toContain('conflicting controls');
  expect(host.textContent).toContain('Sound · in tension with');
  expect(host.textContent).toContain('Why this is in tension');
  expect(host.textContent).toContain('1 supporting signal');
  expect(host.textContent).toContain('1 counter-signal');
});

it('records an optional player correction note for a tension', async () => {
  const conflictedProfile = {
    ...profile,
    projection: {
      ...profile.projection,
      claims: [{
        concept: { conceptId: 'sound', label: 'Sound' },
        claimId: 'claim:sound',
        stance: 'ambivalent',
        adequacy: 'contradictory',
        evidenceIds: ['toward-1'],
        counterEvidenceIds: ['away-1'],
      }],
    },
  };
  const fetchImpl = vi.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ profile: conflictedProfile }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ profile: conflictedProfile }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ revision: 5 }) });
  vi.stubGlobal('fetch', fetchImpl);
  await act(async () => root.render(<EpistemeSnapshot profileId="profile-1" open />));
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
  await act(async () => {
    host.querySelector('.future-episteme-claim-correction summary').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  const note = host.querySelector('.future-episteme-claim-correction textarea');
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(
      note,
      'Keep both meanings available.',
    );
    note.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  await act(async () => {
    [...host.querySelectorAll('button')].find((button) => button.textContent === 'Keep with note').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  expect(JSON.parse(fetchImpl.mock.calls[2][1].body).evidence[0].userText).toBe('Keep both meanings available.');
});
