import { expect, it, vi } from 'vitest';
import { recordAssociationPreference } from './episteme';

it('records an explicit keep/exclude choice and links a correction to prior evidence', async () => {
  const requests = [];
  const profile = { revision: 0, evidence: [] };
  const fetchImpl = vi.fn(async (url, options = {}) => {
    requests.push({ url, options });
    if (options.method !== 'POST') {
      return { ok: true, json: async () => ({ profile: structuredClone(profile) }) };
    }
    const body = JSON.parse(options.body);
    profile.evidence.push(...body.evidence);
    profile.revision += 1;
    return { ok: true, json: async () => ({ revision: profile.revision }) };
  });
  let id = 0;
  const random = { randomUUID: () => `00000000-0000-4000-8000-${String(++id).padStart(12, '0')}` };

  await recordAssociationPreference('profile-id', 'Tension', 'exclude', { fetchImpl, random });
  await recordAssociationPreference('profile-id', 'Tension', 'seek', { fetchImpl, random });

  const updates = requests.filter((request) => request.options.method === 'POST');
  const first = JSON.parse(updates[0].options.body).evidence[0];
  const correction = JSON.parse(updates[1].options.body).evidence[0];
  expect(first.action).toBe('exclude');
  expect(correction.action).toBe('seek');
  expect(correction.supersedesEvidenceIds).toEqual([first.evidenceId]);
  expect(correction.concept).toEqual(first.concept);
  expect(JSON.parse(updates[1].options.body).expectedRevision).toBe(1);
});
