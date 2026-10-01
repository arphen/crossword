export const SPECIMEN_VERDICTS = [
  'leak',
  'tautology',
  'name-slot',
  'pseudo-pun',
  'acceptable',
  'better-of-pair',
];

function normalizeRecord(value) {
  if (!value || typeof value !== 'object') return null;
  if (typeof value.id !== 'string' || !value.id) return null;
  if (typeof value.answer !== 'string' || typeof value.clue !== 'string') return null;
  if (value.verdict !== null && value.verdict !== undefined && !SPECIMEN_VERDICTS.includes(value.verdict)) return null;
  if (value.pairId !== null && value.pairId !== undefined && typeof value.pairId !== 'string') return null;
  return {
    id: value.id,
    answer: value.answer,
    clue: value.clue,
    verdict: value.verdict ?? null,
    pairId: value.pairId ?? null,
    note: typeof value.note === 'string' ? value.note : null,
    source: typeof value.source === 'string' ? value.source : null,
  };
}

export function normalizeSpecimens(body) {
  if (!body || typeof body !== 'object') return null;
  if (typeof body.version !== 'string' || !Array.isArray(body.records)) return null;
  const records = body.records.map(normalizeRecord);
  if (records.some((item) => !item)) return null;
  return { version: body.version, verdicts: SPECIMEN_VERDICTS, records };
}

export function normalizeSpecimenSummary(body) {
  if (!body || typeof body !== 'object') return null;
  const summary = body.summary;
  if (!summary || typeof summary !== 'object') return null;
  if (!Number.isInteger(summary.records) || !Number.isInteger(summary.labeled) || !Number.isInteger(summary.unlabeled)) return null;
  return {
    records: summary.records,
    labeled: summary.labeled,
    unlabeled: summary.unlabeled,
    verdictCounts: summary.verdictCounts && typeof summary.verdictCounts === 'object' ? summary.verdictCounts : {},
    problems: Array.isArray(summary.problems) ? summary.problems : [],
  };
}

async function readJson(response, fallbackMessage) {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = /** @type {Error & {code?: string}} */ (new Error(body?.error || fallbackMessage));
    if (response.status === 404) error.code = 'missing-ledger';
    throw error;
  }
  return body;
}

/** Read an attached error code without tripping the type checker. */
export function errorCode(cause) {
  if (cause instanceof Error && 'code' in cause) return cause.code;
  return undefined;
}

/** @param {{fetchImpl?: typeof fetch, signal?: AbortSignal}} [options] */
export async function loadSpecimens({ fetchImpl = globalThis.fetch, signal } = {}) {
  const response = await fetchImpl('/api/future/specimens', { headers: { Accept: 'application/json' }, signal, cache: 'no-store' });
  const result = normalizeSpecimens(await readJson(response, 'The specimen ledger could not be read.'));
  if (!result) throw new Error('The specimen ledger returned an invalid snapshot.');
  return result;
}

/** @param {{fetchImpl?: typeof fetch, corpusN?: number, force?: boolean}} [options] */
export async function seedSpecimens({ fetchImpl = globalThis.fetch, corpusN = 48, force = false } = {}) {
  const response = await fetchImpl('/api/future/specimens/seed', {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ corpusN, ...(force ? { force: true } : {}) }),
  });
  const body = await readJson(response, 'The specimen ledger could not be prepared.');
  const summary = normalizeSpecimenSummary(body);
  if (!summary) throw new Error('The specimen ledger returned an invalid receipt.');
  return summary;
}

/** @param {string} id @param {string} verdict @param {{fetchImpl?: typeof fetch, note?: string}} [options] */
export async function recordVerdict(id, verdict, { fetchImpl = globalThis.fetch, note } = {}) {
  if (!SPECIMEN_VERDICTS.includes(verdict)) throw new Error('Choose one of the six closed verdicts.');
  const response = await fetchImpl(`/api/future/specimens/${encodeURIComponent(id)}/verdict`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(note ? { verdict, note } : { verdict }),
  });
  const body = await readJson(response, 'The verdict could not be recorded.');
  const summary = normalizeSpecimenSummary(body);
  if (!summary) throw new Error('The verdict receipt was invalid.');
  return summary;
}

/** @param {string} a @param {string} b @param {{fetchImpl?: typeof fetch}} [options] */
export async function linkPair(a, b, { fetchImpl = globalThis.fetch } = {}) {
  const response = await fetchImpl('/api/future/specimens/pairs', {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ a, b }),
  });
  const body = await readJson(response, 'The pair could not be linked.');
  if (typeof body?.pairId !== 'string') throw new Error('The pair receipt was invalid.');
  return body;
}

/** @param {{fetchImpl?: typeof fetch}} [options] */
export async function attestSpecimens({ fetchImpl = globalThis.fetch } = {}) {
  const response = await fetchImpl('/api/future/specimens/attest', {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  const body = await response.json().catch(() => null);
  if (body?.attested === true && typeof body?.digest === 'string') {
    return { pairs: body.pairs, digest: body.digest, out: body.out };
  }
  const remaining = body?.unlabeled ?? body?.summary?.unlabeled;
  throw new Error(
    typeof remaining === 'number' && remaining > 0
      ? `${remaining} surfaces still need a verdict before attesting.`
      : body?.error || 'The ledger is not closed yet.',
  );
}
