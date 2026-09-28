const RESPONSE_VALUES = new Set(['keep', 'not-for-me', 'pass']);
const ACTION_VALUES = new Set(['retract', 'restore']);

function record(value, message) {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error(message);
  return value;
}

function secureId(cryptoApi = globalThis.crypto) {
  if (cryptoApi?.randomUUID) return cryptoApi.randomUUID();
  if (!cryptoApi?.getRandomValues)
    throw new Error('Secure response identifiers are unavailable.');
  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function calibrationPath(calibrationId) {
  if (typeof calibrationId !== 'string' || !calibrationId)
    throw new Error('A calibration journal is required.');
  return `/api/future/calibrations/${encodeURIComponent(calibrationId)}/hypotheses`;
}

async function responseJson(response, fallback) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.error || fallback);
  return record(payload, fallback);
}

/** Read a saved, host-authored deck without asking the model to generate one. */
export async function loadCalibrationHypotheses({
  calibrationId,
  fetchImpl = globalThis.fetch?.bind(globalThis),
  signal,
}) {
  if (!fetchImpl) throw new Error('The local crossword host is unavailable.');
  const response = await fetchImpl(calibrationPath(calibrationId), {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
    signal,
  });
  if (response.status === 404) return null;
  return responseJson(response, 'The saved word paths could not be loaded.');
}

/** Generate once on the local host; retries return the same frozen deck. */
export async function createCalibrationHypotheses({
  calibrationId,
  fetchImpl = globalThis.fetch?.bind(globalThis),
  signal,
}) {
  if (!fetchImpl) throw new Error('The local crossword host is unavailable.');
  const response = await fetchImpl(calibrationPath(calibrationId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({}),
    signal,
  });
  return responseJson(response, 'The local word paths could not be created.');
}

/** Record only the player's response to a host-frozen hypothesis. */
export async function respondToCalibrationHypothesis({
  calibrationId,
  proposalId,
  deckId,
  response,
  fetchImpl = globalThis.fetch?.bind(globalThis),
  cryptoApi = globalThis.crypto,
}) {
  if (!fetchImpl) throw new Error('The local crossword host is unavailable.');
  if (
    !proposalId ||
    !deckId ||
    !RESPONSE_VALUES.has(response)
  )
    throw new Error('This word-path response is invalid.');
  const payload = {
    responseId: secureId(cryptoApi),
    deckId,
    response,
  };
  const responseResult = await fetchImpl(
    `${calibrationPath(calibrationId)}/${encodeURIComponent(proposalId)}/response`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    },
  );
  const result = await responseJson(
    responseResult,
    'This word-path response could not be saved.',
  );
  return { payload, result };
}

/** Retract or restore one immutable response; the history remains inspectable. */
export async function reviseCalibrationHypothesisResponse({
  calibrationId,
  proposalId,
  responseId,
  action,
  fetchImpl = globalThis.fetch?.bind(globalThis),
  cryptoApi = globalThis.crypto,
}) {
  if (!fetchImpl) throw new Error('The local crossword host is unavailable.');
  if (!proposalId || !responseId || !ACTION_VALUES.has(action))
    throw new Error('This word-path revision is invalid.');
  const payload = {
    actionId: secureId(cryptoApi),
    action,
  };
  const response = await fetchImpl(
    `${calibrationPath(calibrationId)}/${encodeURIComponent(proposalId)}/responses/${encodeURIComponent(responseId)}/actions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    },
  );
  const result = await responseJson(
    response,
    'This word-path revision could not be saved.',
  );
  return { payload, result };
}
