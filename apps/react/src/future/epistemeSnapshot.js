const MAX_PROFILE_ID_LENGTH = 64;

function validProfileId(value) {
  return typeof value === 'string' && value.length > 0 && value.length <= MAX_PROFILE_ID_LENGTH;
}

export function normalizeEpistemeSnapshot(body) {
  const profile = body?.profile;
  const projection = profile?.projection;
  if (
    !profile ||
    typeof profile !== 'object' ||
    !projection ||
    typeof projection !== 'object' ||
    !Number.isInteger(profile.revision) ||
    profile.revision < 0 ||
    !Array.isArray(projection.claims) ||
    !Array.isArray(projection.associations) ||
    !Array.isArray(projection.knowledge)
  ) {
    return null;
  }
  return {
    profile,
    revision: profile.revision,
    claims: projection.claims,
    associations: projection.associations,
    knowledge: projection.knowledge,
  };
}

/** @param {string} profileId @param {{fetchImpl?: typeof fetch, signal?: AbortSignal}} [options] */
export async function loadEpistemeSnapshot(
  profileId,
  { fetchImpl = globalThis.fetch, signal } = {},
) {
  if (!validProfileId(profileId) || typeof fetchImpl !== 'function') return null;
  const response = await fetchImpl(
    `/api/future/profile/${encodeURIComponent(profileId)}/episteme`,
    { headers: { Accept: 'application/json' }, signal, cache: 'no-store' },
  );
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    throw new Error(body?.error || 'The local episteme could not be read.');
  }
  const snapshot = normalizeEpistemeSnapshot(body);
  if (!snapshot) throw new Error('The local episteme returned an invalid snapshot.');
  return snapshot;
}
