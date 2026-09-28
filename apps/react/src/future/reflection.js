function uuid(cryptoApi) {
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

export async function submitReflectionResponse({
  sessionId,
  card,
  shownPosition,
  response,
  fetchImpl = globalThis.fetch?.bind(globalThis),
  cryptoApi = globalThis.crypto,
  now = () => new Date(),
}) {
  if (!fetchImpl) throw new Error('The local crossword host is unavailable.');
  if (
    !sessionId ||
    !card?.cardId ||
    !Number.isInteger(shownPosition) ||
    shownPosition < 0 ||
    shownPosition > 2 ||
    !['keep', 'not-for-me', 'pass'].includes(response)
  ) {
    throw new Error(
      'This reflection response does not match the displayed card.',
    );
  }
  const payload = {
    schemaVersion: 1,
    responseId: uuid(cryptoApi),
    sessionId,
    cardId: card.cardId,
    cardVersion: card.version,
    shownPosition,
    recordedAt: now().toISOString(),
    response,
  };
  const result = await fetchImpl(
    `/api/future/sessions/${sessionId}/reflections/${encodeURIComponent(card.cardId)}/response`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    },
  );
  const body = await result.json();
  if (!result.ok)
    throw new Error(body?.error || 'This impression could not be saved.');
  return { payload, result: body };
}

export async function submitReflectionAction({
  sessionId,
  cardId,
  responseId,
  action,
  fetchImpl = globalThis.fetch?.bind(globalThis),
  cryptoApi = globalThis.crypto,
  now = () => new Date(),
}) {
  if (!fetchImpl) throw new Error('The local crossword host is unavailable.');
  if (
    !sessionId ||
    !cardId ||
    !responseId ||
    !['retract', 'restore'].includes(action)
  ) {
    throw new Error('This revision does not match the saved impression.');
  }
  const payload = {
    schemaVersion: 1,
    actionId: uuid(cryptoApi),
    targetResponseId: responseId,
    recordedAt: now().toISOString(),
    action,
  };
  const result = await fetchImpl(
    `/api/future/sessions/${sessionId}/reflections/${encodeURIComponent(cardId)}/responses/${responseId}/actions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    },
  );
  const body = await result.json();
  if (!result.ok)
    throw new Error(body?.error || 'This revision could not be saved.');
  return { payload, result: body };
}
