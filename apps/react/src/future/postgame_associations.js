function uuid(cryptoApi = globalThis.crypto) {
  if (cryptoApi?.randomUUID) return cryptoApi.randomUUID();
  if (!cryptoApi?.getRandomValues)
    throw new Error('Secure response identifiers are unavailable');
  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/**
 * @param {string} sessionId
 * @param {{fetchImpl?: typeof fetch, signal?: AbortSignal}} options
 */
export async function loadPostgameAssociations(
  sessionId,
  { fetchImpl = globalThis.fetch?.bind(globalThis), signal } = {},
) {
  if (!fetchImpl) throw new Error('The local crossword host is unavailable.');
  const response = await fetchImpl(
    `/api/future/sessions/${encodeURIComponent(sessionId)}/episteme-associations`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ requestId: uuid() }),
      signal,
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.error || 'The word paths are unavailable.');
  return body;
}

export async function respondToPostgameAssociation({
  sessionId,
  associationId,
  response,
  fetchImpl = globalThis.fetch?.bind(globalThis),
}) {
  if (!fetchImpl) throw new Error('The local crossword host is unavailable.');
  if (!sessionId || !associationId || !['keep', 'not-for-me', 'pass'].includes(response))
    throw new Error('This association response is invalid.');
  const payload = { responseId: uuid(), response };
  const result = await fetchImpl(
    `/api/future/sessions/${encodeURIComponent(sessionId)}/episteme-associations/${encodeURIComponent(associationId)}/response`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    },
  );
  const body = await result.json().catch(() => ({}));
  if (!result.ok) throw new Error(body?.error || 'This word path could not be saved.');
  return { payload, result: body };
}

export async function expandPostgameAssociation({
  sessionId,
  associationId,
  fetchImpl = globalThis.fetch?.bind(globalThis),
}) {
  if (!fetchImpl) throw new Error('The local crossword host is unavailable.');
  if (!sessionId || !associationId) throw new Error('This association expansion is invalid.');
  const response = await fetchImpl(
    `/api/future/sessions/${encodeURIComponent(sessionId)}/episteme-associations/${encodeURIComponent(associationId)}/expand`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ requestId: uuid() }),
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.error || 'This word path could not be expanded.');
  return body;
}
