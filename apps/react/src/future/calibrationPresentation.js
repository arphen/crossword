const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_CALIBRATION_OFFER = 12;

/**
 * v1 is the selector used by persisted calibration sessions. v2 uses
 * rejection sampling for unbiased bounded indices. Callers must persist the
 * selected version alongside the session before opting into v2.
 */
export const CALIBRATION_SELECTOR_VERSION_V1 = 'selector-v1';
export const CALIBRATION_SELECTOR_VERSION_V2 = 'selector-v2';

/**
 * Derive a stable, non-secret uint32 selector seed from a calibration UUID.
 * FNV-1a is used only to make the initial presentation reproducible; this is
 * not a capability, privacy boundary, or cryptographic hash.
 * @param {string} calibrationId
 * @returns {number}
 */
export function deriveCalibrationSeed(calibrationId) {
  if (typeof calibrationId !== 'string' || !UUID_PATTERN.test(calibrationId)) {
    throw new TypeError('A canonical calibration UUID is required.');
  }

  let hash = 0x811c9dc5;
  for (const byte of new TextEncoder().encode(calibrationId.toLowerCase())) {
    hash ^= byte;
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/** @param {number} seed */
function assertSeed(seed) {
  if (!Number.isInteger(seed) || seed < 0 || seed > 0xffffffff) {
    throw new TypeError('The calibration seed must be an unsigned 32-bit integer.');
  }
}

/**
 * A small deterministic PRNG for Fisher-Yates. It has no dependency on the
 * browser's ambient random source, so a retained seed reproduces an offer.
 * @param {number} seed
 */
function createSeededUint32(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return (value ^ (value >>> 14)) >>> 0;
  };
}

/** @param {number} seed */
function createSeededRandom(seed) {
  const nextUint32 = createSeededUint32(seed);
  return () => nextUint32() / 0x100000000;
}

/**
 * Map uint32 values to [0, bound) without modulo bias. Values in the short
 * tail above the largest complete range are discarded before taking modulo.
 * @param {() => number} nextUint32
 * @param {number} bound
 */
function randomBelow(nextUint32, bound) {
  const uint32Range = 0x1_0000_0000;
  const acceptedRange = Math.floor(uint32Range / bound) * bound;
  let value = nextUint32();
  while (value >= acceptedRange) value = nextUint32();
  return value % bound;
}

/**
 * Return a shuffled copy in reproducible order. The input array is untouched.
 * @template T
 * @param {readonly T[]} items
 * @param {number} seed
 * @param {'selector-v1' | 'selector-v2'} selectorVersion
 * @returns {T[]}
 */
export function seededShuffle(
  items,
  seed,
  selectorVersion = CALIBRATION_SELECTOR_VERSION_V1,
) {
  if (!Array.isArray(items)) throw new TypeError('Items must be an array.');
  assertSeed(seed);
  if (
    selectorVersion !== CALIBRATION_SELECTOR_VERSION_V1 &&
    selectorVersion !== CALIBRATION_SELECTOR_VERSION_V2
  ) {
    throw new TypeError('A supported calibration selector version is required.');
  }

  const ordered = [...items];
  if (selectorVersion === CALIBRATION_SELECTOR_VERSION_V1) {
    // Keep the exact pre-versioned selector-v1 draw sequence. Persisted
    // calibration sessions replay the original ordering with the default.
    const random = createSeededRandom(seed);
    for (let index = ordered.length - 1; index > 0; index -= 1) {
      const otherIndex = Math.floor(random() * (index + 1));
      [ordered[index], ordered[otherIndex]] = [ordered[otherIndex], ordered[index]];
    }
  } else {
    const nextUint32 = createSeededUint32(seed);
    for (let index = ordered.length - 1; index > 0; index -= 1) {
      const otherIndex = randomBelow(nextUint32, index + 1);
      [ordered[index], ordered[otherIndex]] = [ordered[otherIndex], ordered[index]];
    }
  }
  return ordered;
}

/**
 * Describe the exact catalog items shown in this order. Positions are stable,
 * zero-based offer slots, not screen coordinates or global catalog indices.
 * Versions are stringified because the persisted calibration contract stores
 * stimulusVersion as text.
 * @param {readonly {id: string, version: string | number}[]} shownItems
 * @returns {{stimulusId: string, stimulusVersion: string, position: number}[]}
 */
export function toCalibrationOffer(shownItems) {
  if (!Array.isArray(shownItems) || shownItems.length > MAX_CALIBRATION_OFFER) {
    throw new TypeError(`A calibration offer must contain at most ${MAX_CALIBRATION_OFFER} items.`);
  }

  const ids = new Set();
  return shownItems.map((item, position) => {
    if (
      !item ||
      typeof item.id !== 'string' ||
      item.id.length === 0 ||
      !(typeof item.version === 'string' || Number.isSafeInteger(item.version)) ||
      String(item.version).length === 0
    ) {
      throw new TypeError('Each offered item must have a stable id and version.');
    }
    if (ids.has(item.id)) {
      throw new TypeError(`A calibration offer cannot repeat stimulus ${item.id}.`);
    }
    ids.add(item.id);
    return {
      stimulusId: item.id,
      stimulusVersion: String(item.version),
      position,
    };
  });
}

/**
 * Shuffle a bounded catalog selection and return both the visible items and
 * their exact persisted offer metadata. Recreate this call with the same seed
 * and input order to reproduce the presentation.
 * @template {{id: string, version: string | number}} T
 * @param {readonly T[]} items
 * @param {number} seed
 * @param {'selector-v1' | 'selector-v2'} selectorVersion
 * @returns {{shownItems: T[], offered: ReturnType<typeof toCalibrationOffer>}}
 */
export function createCalibrationPresentation(
  items,
  seed,
  selectorVersion = CALIBRATION_SELECTOR_VERSION_V1,
) {
  const shownItems = seededShuffle(items, seed, selectorVersion);
  return { shownItems, offered: toCalibrationOffer(shownItems) };
}
