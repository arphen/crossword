import { createProfileId } from './episteme';

function validDigest(value) {
  return typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value);
}

function normalizeGeneration(value) {
  if (!value || typeof value !== 'object') return null;
  const generation = {};
  for (const key of ['provider', 'requestedModel', 'returnedModel', 'format', 'promptVersion']) {
    if (typeof value[key] === 'string' && value[key].length <= 160) generation[key] = value[key];
  }
  if (typeof value.digest === 'string' && validDigest(value.digest)) generation.digest = value.digest;
  return Object.keys(generation).length ? generation : null;
}

function normalizeItem(value, maximum) {
  if (
    !value ||
    typeof value !== 'object' ||
    typeof value.text !== 'string' ||
    value.text.trim() !== value.text ||
    value.text.length < 1 ||
    value.text.length > maximum ||
    !Array.isArray(value.evidenceIds) ||
    value.evidenceIds.length > 8 ||
    value.evidenceIds.some((item) => typeof item !== 'string')
  ) return null;
  return { text: value.text, evidenceIds: [...new Set(value.evidenceIds)] };
}

function normalizeSuggestion(value) {
  if (
    !value ||
    typeof value !== 'object' ||
    typeof value.conceptId !== 'string' ||
    value.conceptId.trim() !== value.conceptId ||
    value.conceptId.length < 1 ||
    value.conceptId.length > 240 ||
    typeof value.label !== 'string' ||
    value.label.trim() !== value.label ||
    value.label.length < 1 ||
    value.label.length > 160 ||
    !['taste', 'goal', 'style', 'context'].includes(value.kind) ||
    !['seek', 'exclude'].includes(value.action) ||
    typeof value.rationale !== 'string' ||
    value.rationale.trim() !== value.rationale ||
    value.rationale.length < 1 ||
    value.rationale.length > 360 ||
    !Array.isArray(value.evidenceIds) ||
    value.evidenceIds.length < 1 ||
    value.evidenceIds.length > 8 ||
    value.evidenceIds.some((item) => typeof item !== 'string')
  ) return null;
  return { ...value, evidenceIds: [...new Set(value.evidenceIds)] };
}

export function normalizeProfileNarrative(body) {
  if (!body || typeof body !== 'object') return null;
  if (!['empty', 'ready', 'unavailable'].includes(body.status)) return null;
  const receipt = body.receipt;
  if (receipt !== null && receipt !== undefined) {
    if (
      typeof receipt !== 'object' ||
      !Number.isInteger(receipt.epistemeRevision) ||
      !validDigest(receipt.sourceDigest)
    ) return null;
  }
  const raw = body.narrative;
  if (raw === null || raw === undefined) {
    return { status: body.status, stale: body.stale === true, narrative: null, receipt: receipt ? { ...receipt, generation: normalizeGeneration(receipt.generation) } : null };
  }
  if (
    typeof raw !== 'object' ||
    raw.version !== 'private-profile-narrative-v1' ||
    !Array.isArray(raw.paragraphs) ||
    !Array.isArray(raw.openQuestions)
  ) return null;
  const paragraphs = raw.paragraphs.map((item) => normalizeItem(item, 700));
  const openQuestions = raw.openQuestions.map((item) => normalizeItem(item, 240));
  const suggestions = (raw.suggestions || []).map(normalizeSuggestion);
  if (paragraphs.some((item) => !item) || openQuestions.some((item) => !item) || suggestions.some((item) => !item)) return null;
  return {
    status: body.status,
    stale: body.stale === true,
    narrative: { version: raw.version, paragraphs, openQuestions, suggestions },
    receipt: receipt ? { ...receipt, generation: normalizeGeneration(receipt.generation) } : null,
  };
}

/** @param {string} profileId @param {string} narrativeId @param {number} index @param {number} expectedRevision @param {{fetchImpl?: typeof fetch, random?: Crypto}} [options] */
export async function acceptProfileSuggestion(
  profileId,
  narrativeId,
  index,
  expectedRevision,
  { fetchImpl = globalThis.fetch, random = globalThis.crypto } = {},
) {
  if (!Number.isInteger(expectedRevision) || expectedRevision < 0) throw new Error('The field note revision is invalid.');
  const updateId = random?.randomUUID ? random.randomUUID() : createProfileId(random);
  const response = await fetchImpl(
    `/api/future/profile/${encodeURIComponent(profileId)}/narrative/${encodeURIComponent(narrativeId)}/suggestions/${index}/accept`,
    {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ expectedRevision, updateId }),
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.error || 'The field note path could not be kept.');
  return body;
}

/** @param {string} profileId @param {{fetchImpl?: typeof fetch, signal?: AbortSignal}} [options] */
export async function loadProfileNarrative(profileId, { fetchImpl = globalThis.fetch, signal } = {}) {
  const response = await fetchImpl(
    `/api/future/profile/${encodeURIComponent(profileId)}/narrative`,
    { headers: { Accept: 'application/json' }, signal, cache: 'no-store' },
  );
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.error || 'The profile field note could not be read.');
  const result = normalizeProfileNarrative(body);
  if (!result) throw new Error('The profile field note returned an invalid snapshot.');
  return result;
}

/** @param {string} profileId @param {{fetchImpl?: typeof fetch, signal?: AbortSignal}} [options] */
export async function generateProfileNarrative(profileId, { fetchImpl = globalThis.fetch, signal } = {}) {
  const response = await fetchImpl(
    `/api/future/profile/${encodeURIComponent(profileId)}/narrative`,
    {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ requestId: createProfileId() }),
      signal,
    },
  );
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.error || 'The profile field note could not be written.');
  const result = normalizeProfileNarrative(body);
  if (!result) throw new Error('The profile field note returned an invalid result.');
  return result;
}
