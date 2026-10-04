import catalog from '../../../../src/crossword/future_catalog.json';

export { catalog };
export const STORAGE_KEY = 'crossword.future.v1';
export const LOCAL_MODEL_CHOICES = [
  'automatic',
  'gemma4:26b',
  'qwen3.8:27b',
  'gemma4:31b',
  'gemma3:27b',
];
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const CALIBRATION_PRESENTATION_MODES = [
  'visual',
  'monochrome',
  'text-equivalent',
];
const COLOR_STIMULUS_IDS = new Set(
  catalog.stimuli.items
    .filter((item) => item.kind === 'color')
    .map((item) => item.id),
);
const STIMULUS_IDS = new Set(catalog.stimuli.items.map((item) => item.id));
export function createProfileId(random = crypto) {
  if (random.randomUUID) return random.randomUUID();
  // getRandomValues also works on local-network HTTP, where randomUUID may
  // be unavailable. Do not downgrade the capability id to Math.random.
  const bytes = random.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
export const freshDraft = () => ({
  version: 1,
  id: createProfileId(),
  calibrationId: createProfileId(),
  step: 0,
  object: null,
  firstStimulus: null,
  companion: null,
  variation: null,
  presentationMode: 'visual',
  traces: [],
  weekday: 'wednesday',
  learningLanguage: 'None for now',
  modelPreference: 'automatic',
  excluded: [],
  reflection: null,
  complete: false,
});

export function validateDraft(value) {
  const hasCalibrationId = value?.calibrationId !== undefined;
  if (
    !value ||
    value.version !== 1 ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(
      value.id,
    ) ||
    !Number.isInteger(value.step) ||
    value.step < 0 ||
    value.step > 5 ||
    (hasCalibrationId && !UUID_PATTERN.test(value.calibrationId)) ||
    (value?.firstStimulus !== undefined &&
      value.firstStimulus !== null &&
      !STIMULUS_IDS.has(value.firstStimulus)) ||
    (value?.variation !== undefined &&
      value.variation !== null &&
      value.variation !== 'keep-original' &&
      !COLOR_STIMULUS_IDS.has(value.variation)) ||
    (value?.presentationMode !== undefined &&
      !CALIBRATION_PRESENTATION_MODES.includes(value.presentationMode)) ||
    (value.profileUpdatedAt !== undefined &&
      (typeof value.profileUpdatedAt !== 'string' ||
        value.profileUpdatedAt.length > 40 ||
        !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(
          value.profileUpdatedAt,
        )))
    ||
    (value.modelPreference !== undefined &&
      !LOCAL_MODEL_CHOICES.includes(value.modelPreference))
  )
    return false;
  const object = catalog.objects.find((item) => item.id === value.object);
  return (
    (value.object === null || Boolean(object)) &&
    (value.companion === null ||
      Boolean(object?.companions.includes(value.companion))) &&
    Array.isArray(value.traces) &&
    value.traces.length <= 3 &&
    value.traces.every((word) => catalog.traces.includes(word)) &&
    new Set(value.traces).size === value.traces.length &&
    catalog.days.some((day) => day.id === value.weekday) &&
    catalog.languages.includes(value.learningLanguage) &&
    Array.isArray(value.excluded) &&
    value.excluded.length <= 24 &&
    value.excluded.every(
      (word) => typeof word === 'string' && word.length <= 40,
    ) &&
    typeof value.complete === 'boolean' &&
    (!value.reflection ||
      (typeof value.reflection.model === 'string' &&
        value.reflection.model.length <= 100 &&
        Array.isArray(value.reflection.words) &&
        value.reflection.words.length <= 6 &&
        value.reflection.words.every(
          (word) =>
            typeof word === 'string' && /^[a-z][a-z -]{1,28}$/i.test(word),
        )))
  );
}

export function readDraft(storage = undefined) {
  try {
    const value = JSON.parse(
      (storage ?? window.localStorage).getItem(STORAGE_KEY),
    );
    if (!validateDraft(value)) return freshDraft();
    if (value.calibrationId) {
      return {
        ...value,
        modelPreference: value.modelPreference ?? 'automatic',
      };
    }
    // Existing v1 drafts used step 2 for traces, step 3 for weekday, and step
    // 4 for the preview. Move those saved screens forward around the new
    // visual-variation movement without discarding any earlier choices.
    const nextStep = value.step > 1 ? Math.min(5, value.step + 1) : value.step;
    return {
      ...value,
      calibrationId: createProfileId(),
      step: nextStep,
      firstStimulus:
        value.object === null
          ? null
          : catalog.stimuli.items.find((item) =>
              item.legacy_ids?.includes(value.object),
            )?.id ?? null,
      variation: null,
      presentationMode: 'visual',
      modelPreference: value.modelPreference ?? 'automatic',
    };
  } catch {
    return freshDraft();
  }
}

export function writeDraft(draft, storage = undefined) {
  try {
    (storage ?? window.localStorage).setItem(
      STORAGE_KEY,
      JSON.stringify(draft),
    );
    return true;
  } catch {
    return false;
  }
}

// These are explicitly provisional editorial associations, never inferred traits.
// The server independently derives the same grounded seed for durable storage.
export function seedProfile(draft) {
  const object = catalog.objects.find((item) => item.id === draft.object);
  const firstStimulus =
    catalog.stimuli.items.find((item) => item.id === draft.firstStimulus) ??
    catalog.stimuli.items.find((item) =>
      item.legacy_ids?.includes(draft.object),
    );
  const companion = catalog.companions.find(
    (item) => item.id === draft.companion,
  );
  const associations = [
    ...new Set([
      ...draft.traces,
      ...(object?.words ?? []),
      ...(firstStimulus?.association_seeds ?? []),
      ...(companion?.words ?? []),
      ...(draft.reflection?.words ?? []),
    ]),
  ]
    .slice(0, 18)
    .filter((word) => !draft.excluded.includes(word));
  const observations = [
    firstStimulus?.accessible_label ?? object?.label,
    companion?.label,
  ].filter(Boolean);
  const prose = observations.length
    ? `${observations.map((label, index) => (index ? label[0].toLowerCase() + label.slice(1) : label)).join(' beside ')}. ${draft.traces.length ? `You kept ${draft.traces.map((word) => `“${word}”`).join(', ')}. ` : ''}A few possible paths through words; nothing here has to stay.`
    : 'An open beginning. Let the first puzzle be a place to discover what catches your attention.';
  return {
    version: 1,
    associations,
    prose,
    observations,
    weekday: draft.weekday,
    learningLanguage: draft.learningLanguage,
    source: 'authored-associations',
    provisional: true,
    knowledge: {},
  };
}

export function changeObject(draft, object) {
  const firstStimulus = catalog.stimuli.items.find((item) =>
    item.legacy_ids?.includes(object),
  )?.id;
  return {
    ...draft,
    object,
    firstStimulus: firstStimulus ?? null,
    variation: draft.object === object ? draft.variation : null,
    companion: draft.object === object ? draft.companion : null,
    excluded: [],
    reflection: draft.object === object ? draft.reflection : null,
  };
}

export async function saveProfile(draft, signal) {
  const headers = { 'Content-Type': 'application/json' };
  const { profileUpdatedAt, ...profileDraft } = draft;
  if (profileUpdatedAt)
    headers['If-Match'] = `"${profileUpdatedAt}"`;
  else headers['If-None-Match'] = '*';
  const response = await fetch(`/api/future/profile/${draft.id}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(profileDraft),
    signal,
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = /** @type {Error & {status?: number}} */ (
      new Error(
        result?.error ||
          'The local server could not save your starting profile.',
      )
    );
    error.status = response.status;
    throw error;
  }
  return result;
}

export async function loadSavedProfile(profileId) {
  const response = await fetch(
    `/api/future/profile/${encodeURIComponent(profileId)}`,
    { cache: 'no-store' },
  );
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !validateDraft(result?.draft)) {
    throw new Error(result?.error || 'The saved beginning could not be loaded.');
  }
  return { ...result.draft, profileUpdatedAt: result.updatedAt };
}

export async function recordAssociationPreference(
  profileId,
  phrase,
  action,
  { fetchImpl = globalThis.fetch?.bind(globalThis), random = globalThis.crypto } = {},
) {
  if (!fetchImpl) throw new Error('The local profile server is unavailable.');
  const epistemeUrl = `/api/future/profile/${encodeURIComponent(profileId)}/episteme`;
  const currentResponse = await fetchImpl(epistemeUrl, { cache: 'no-store' });
  if (!currentResponse.ok) throw new Error('The local episteme could not be read.');
  const { profile } = await currentResponse.json();
  const normalizedPhrase = phrase.trim().normalize('NFC');
  const conceptId = `association:en:${encodeURIComponent(normalizedPhrase.toLocaleLowerCase('en-US'))}`;
  const scope = { mode: 'association-field', language: 'en' };
  const existing = profile.evidence.filter((item) =>
    item.type === 'explicit-preference'
      && item.concept.conceptId === conceptId
      && JSON.stringify(item.scope) === JSON.stringify(scope),
  );
  const evidence = {
    evidenceId: createProfileId(random),
    recordedAt: new Date().toISOString(),
    type: 'explicit-preference',
    concept: { conceptId, label: normalizedPhrase, language: 'en' },
    kind: 'taste',
    action,
    scope,
    supersedesEvidenceIds: existing.map((item) => item.evidenceId),
  };
  const update = {
    expectedRevision: profile.revision,
    updateId: createProfileId(random),
    recordedAt: new Date().toISOString(),
    evidence: [evidence],
    evidenceActions: [],
  };
  const response = await fetchImpl(`${epistemeUrl}/updates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.error || 'The local episteme could not be updated.');
  }
  return response.json();
}

export async function recordEpistemePreference(
  profileId,
  claim,
  action,
  { fetchImpl = globalThis.fetch?.bind(globalThis), random = globalThis.crypto, userText = '' } = {},
) {
  if (!fetchImpl) throw new Error('The local profile server is unavailable.');
  const concept = claim?.concept;
  if (!concept || typeof concept.conceptId !== 'string' || typeof concept.label !== 'string') {
    throw new Error('The episteme signal is malformed.');
  }
  if (!['seek', 'exclude', 'clear'].includes(action)) throw new Error('The episteme correction is invalid.');
  if (typeof userText !== 'string' || userText.length > 2000) throw new Error('The episteme correction note is too long.');
  const epistemeUrl = `/api/future/profile/${encodeURIComponent(profileId)}/episteme`;
  const currentResponse = await fetchImpl(epistemeUrl, { cache: 'no-store' });
  if (!currentResponse.ok) throw new Error('The local episteme could not be read.');
  const current = await currentResponse.json();
  const profile = current?.profile;
  if (!profile || !Number.isInteger(profile.revision) || !Array.isArray(profile.evidence)) {
    throw new Error('The local episteme returned an invalid revision.');
  }
  const kind = ['taste', 'goal', 'style', 'context'].includes(claim.kind) ? claim.kind : 'taste';
  const scope = { mode: 'profile-snapshot', language: concept.language || 'en' };
  const existing = profile.evidence.filter((item) =>
    item.type === 'explicit-preference' &&
    item.concept?.conceptId === concept.conceptId &&
    item.kind === kind &&
    JSON.stringify(item.scope) === JSON.stringify(scope),
  );
  const evidence = {
    evidenceId: createProfileId(random),
    recordedAt: new Date().toISOString(),
    type: 'explicit-preference',
    concept: { conceptId: concept.conceptId, label: concept.label, language: concept.language || 'en' },
    kind,
    action,
    scope,
    supersedesEvidenceIds: existing.map((item) => item.evidenceId),
    userText: userText.trim() || 'Corrected from the living episteme.',
  };
  const update = {
    expectedRevision: profile.revision,
    updateId: createProfileId(random),
    recordedAt: new Date().toISOString(),
    evidence: [evidence],
    evidenceActions: [],
  };
  const response = await fetchImpl(`${epistemeUrl}/updates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || 'The local episteme could not be updated.');
  return result;
}

export async function expandAssociations(draft, signal) {
  const response = await fetch('/api/future/associations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(draft),
    signal,
  });
  if (!response.ok)
    throw new Error(
      'Local imagination is unavailable. Your beginning is already ready to use.',
    );
  return response.json();
}
