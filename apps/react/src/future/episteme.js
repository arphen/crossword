import catalog from '../../../../src/crossword/future_catalog.json';

export { catalog };
export const STORAGE_KEY = 'crossword.future.v1';
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
  step: 0,
  object: null,
  companion: null,
  traces: [],
  weekday: 'wednesday',
  learningLanguage: 'None for now',
  excluded: [],
  reflection: null,
  complete: false,
});

export function validateDraft(value) {
  if (
    !value ||
    value.version !== 1 ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(
      value.id,
    ) ||
    !Number.isInteger(value.step) ||
    value.step < 0 ||
    value.step > 4
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
    return validateDraft(value) ? value : freshDraft();
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
  const companion = catalog.companions.find(
    (item) => item.id === draft.companion,
  );
  const associations = [
    ...new Set([
      ...draft.traces,
      ...(object?.words ?? []),
      ...(companion?.words ?? []),
      ...(draft.reflection?.words ?? []),
    ]),
  ]
    .slice(0, 18)
    .filter((word) => !draft.excluded.includes(word));
  const observations = [object?.label, companion?.label].filter(Boolean);
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
  return {
    ...draft,
    object,
    companion: draft.object === object ? draft.companion : null,
    excluded: [],
    reflection: draft.object === object ? draft.reflection : null,
  };
}

export async function saveProfile(draft, signal) {
  const response = await fetch(`/api/future/profile/${draft.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(draft),
    signal,
  });
  if (!response.ok)
    throw new Error('The local server could not save your starting profile.');
  return response.json();
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
