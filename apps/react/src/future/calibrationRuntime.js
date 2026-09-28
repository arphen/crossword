import {
  orderedCalibrationEvents,
  validateCalibrationSession,
} from '@crossword/domain';
import { createProfileId, catalog } from './episteme';
import {
  CALIBRATION_SELECTOR_VERSION_V2,
  deriveCalibrationSeed,
} from './calibrationPresentation';

const SELECTOR_VERSION = CALIBRATION_SELECTOR_VERSION_V2;
const PRESENTATION_MODES = new Set([
  'visual',
  'monochrome',
  'text-equivalent',
]);

/** @param {unknown} value */
function requireSession(value) {
  if (!validateCalibrationSession(value)) {
    throw new TypeError('The calibration session is invalid.');
  }
  return value;
}

/** @param {Date | string | undefined | (() => Date | string)} value */
function isoTimestamp(value) {
  const resolved = typeof value === 'function' ? value() : value;
  const date = resolved === undefined ? new Date() : new Date(resolved);
  if (!Number.isFinite(date.getTime())) {
    throw new TypeError('A valid timestamp is required.');
  }
  return date.toISOString();
}

/** @param {string} current @param {string} proposed */
function nondecreasingTimestamp(current, proposed) {
  return Date.parse(proposed) < Date.parse(current) ? current : proposed;
}

/** @param {unknown} value */
function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

/** @param {unknown} a @param {unknown} b */
function sameJson(a, b) {
  return canonicalJson(a) === canonicalJson(b);
}

/**
 * Ensure all persisted snapshots satisfy the shared domain contract.
 * @template {Record<string, unknown>} T
 * @param {T} value
 * @returns {T}
 */
function validated(value) {
  if (!validateCalibrationSession(value)) {
    throw new TypeError('The calibration change does not satisfy the session contract.');
  }
  return value;
}

/**
 * Start a reproducible, empty calibration journal for a profile. Raw responses
 * are deliberately kept out of the preference/episteme profile.
 * @param {{draft: {id: string, calibrationId?: string, presentationMode?: string}, now?: Date | string | (() => Date | string), random?: Crypto}} options
 */
export function createInitialCalibrationSession({
  draft,
  now,
  random = globalThis.crypto,
}) {
  if (!draft || typeof draft.id !== 'string' || draft.id.length === 0) {
    throw new TypeError('A starting profile id is required.');
  }
  const calibrationId = draft.calibrationId || createProfileId(random);
  const presentationMode = PRESENTATION_MODES.has(draft.presentationMode)
    ? draft.presentationMode
    : 'visual';
  const createdAt = isoTimestamp(now);
  const session = {
    schemaVersion: 1,
    calibrationId,
    scope: { kind: 'profile', profileId: draft.id },
    bankVersion: String(catalog.stimuli.version),
    selectorVersion: SELECTOR_VERSION,
    seed: deriveCalibrationSeed(calibrationId),
    presentationMode,
    currentMovement: 1,
    observations: [],
    actions: [],
    status: 'in-progress',
    createdAt,
    updatedAt: createdAt,
  };
  return validated(session);
}

/**
 * Move the revisitable calibration cursor without changing observation history.
 * @param {import('@crossword/domain').CalibrationSessionV1} session
 * @param {number} movement
 * @param {{now?: Date | string | (() => Date | string)}} [options]
 */
export function updateCalibrationCursor(session, movement, { now } = {}) {
  requireSession(session);
  if (session.status !== 'in-progress') {
    throw new TypeError('A terminal calibration cannot be moved.');
  }
  if (!Number.isInteger(movement) || movement < 1 || movement > 5) {
    throw new TypeError('The calibration movement must be between 1 and 5.');
  }
  if (movement > session.currentMovement + 1) {
    throw new TypeError('The calibration cursor cannot skip a movement.');
  }
  const updatedAt = nondecreasingTimestamp(session.updatedAt, isoTimestamp(now));
  return validated({ ...session, currentMovement: movement, updatedAt });
}

/**
 * Replay active chosen observations for one movement in the append-only journal.
 * @param {import('@crossword/domain').CalibrationSessionV1} session
 * @param {number} movement
 */
function activeChosenObservations(session, movement) {
  const events = orderedCalibrationEvents(session);
  if (!events) throw new TypeError('The calibration event stream is invalid.');
  const observations = new Map();
  const active = new Set();
  for (const event of events) {
    if (event.kind === 'observation') {
      observations.set(event.value.observationId, event.value);
      if (
        event.value.movement === movement &&
        event.value.response.kind === 'choose'
      ) {
        active.add(event.value.observationId);
      }
    } else if (event.value.action === 'retract') {
      active.delete(event.value.targetObservationId);
    } else {
      active.add(event.value.targetObservationId);
    }
  }
  return [...active]
    .map((id) => observations.get(id))
    .filter((observation) => observation?.movement === movement)
    .sort((left, right) => left.sequence - right.sequence);
}

/** @param {import('@crossword/domain').CalibrationSessionV1} session @param {number} movement */
function latestMovementObservation(session, movement) {
  return session.observations
    .filter((observation) => observation.movement === movement)
    .reduce(
      (latest, observation) =>
        latest === undefined || observation.sequence > latest.sequence
          ? observation
          : latest,
      undefined,
    );
}

/** @param {import('@crossword/domain').CalibrationSessionV1} session */
function nextSequence(session) {
  const events = orderedCalibrationEvents(session);
  if (!events) throw new TypeError('The calibration event stream is invalid.');
  return events.length + 1;
}

/**
 * Append a response to a movement. Revising replaces active chosen evidence by
 * appending retract actions first; prior observations remain untouched.
 * @param {import('@crossword/domain').CalibrationSessionV1} session
 * @param {{movement: number, offered: import('@crossword/domain').CalibrationStimulusPresentationV1[], response: import('@crossword/domain').CalibrationResponseV1, relation?: import('@crossword/domain').CalibrationRelationV1, presentedAt?: Date | string, nextMovement?: number, retractMovements?: readonly import('@crossword/domain').CalibrationMovementV1[]}} input
 * @param {{now?: Date | string | (() => Date | string), random?: Crypto}} [options]
 */
export function appendCalibrationObservation(
  session,
  {
    movement,
    offered,
    response,
    relation,
    presentedAt,
    nextMovement,
    retractMovements = [],
  },
  { now, random = globalThis.crypto } = {},
) {
  requireSession(session);
  if (session.status !== 'in-progress') {
    throw new TypeError('A terminal calibration cannot accept observations.');
  }
  if (!Number.isInteger(movement) || movement < 1 || movement > 5) {
    throw new TypeError('The calibration movement must be between 1 and 5.');
  }
  if (nextMovement !== undefined && (!Number.isInteger(nextMovement) || nextMovement < 1 || nextMovement > 5)) {
    throw new TypeError('The next calibration movement must be between 1 and 5.');
  }
  if (nextMovement !== undefined && nextMovement > session.currentMovement + 1) {
    throw new TypeError('The calibration cursor cannot skip a movement.');
  }
  if (
    !Array.isArray(retractMovements) ||
    retractMovements.some(
      (item) => !Number.isInteger(item) || item < 1 || item > 5,
    )
  ) {
    throw new TypeError('Movements selected for retraction must be between 1 and 5.');
  }
  const recordedAt = nondecreasingTimestamp(session.updatedAt, isoTimestamp(now));
  const shownAt = isoTimestamp(presentedAt ?? recordedAt);
  // If a caller passes a presentation time later than its local clock, clamp
  // event time forward so recordedAt can never precede presentedAt.
  const eventAt = nondecreasingTimestamp(shownAt, recordedAt);
  const persistedOffer = offered?.map((item) => ({ ...item }));
  const persistedResponse = /** @type {import('@crossword/domain').CalibrationResponseV1} */ (
    response?.kind === 'choose'
      ? { kind: 'choose', chosenIds: [...response.chosenIds].sort() }
      : response?.kind === 'pass'
        ? { kind: 'pass' }
        : response
  );
  const persistedRelation = relation ? { ...relation } : undefined;

  const active = activeChosenObservations(session, movement);
  const candidate = {
    offered: persistedOffer,
    response: persistedResponse,
    ...(persistedRelation ? { relation: persistedRelation } : {}),
  };
  const duplicateChosen =
    persistedResponse?.kind === 'choose' &&
    active.some((observation) =>
      sameJson(
        {
          offered: observation.offered,
          response: {
            ...observation.response,
            ...(observation.response.kind === 'choose'
              ? { chosenIds: [...observation.response.chosenIds].sort() }
              : {}),
          },
          ...(observation.relation ? { relation: observation.relation } : {}),
        },
        candidate,
      ),
    );
  const latest = latestMovementObservation(session, movement);
  const duplicatePass =
    persistedResponse?.kind === 'pass' &&
    latest?.response.kind === 'pass' &&
    sameJson(
      {
        offered: latest.offered,
        response: latest.response,
        ...(latest.relation ? { relation: latest.relation } : {}),
      },
      candidate,
    );

  let nextSession = session;
  if (!duplicateChosen && !duplicatePass) {
    const observations = [...session.observations];
    const actions = [...session.actions];
    let sequence = nextSequence(session);
    const movementsToRetract = new Set([movement, ...retractMovements]);
    const activeToRetract = [...movementsToRetract]
      .flatMap((item) => activeChosenObservations(session, item))
      .sort((left, right) => left.sequence - right.sequence);
    for (const previous of activeToRetract) {
      actions.push({
        sequence,
        actionId: createProfileId(random),
        targetObservationId: previous.observationId,
        action: 'retract',
        recordedAt: eventAt,
      });
      sequence += 1;
    }
    observations.push({
      sequence,
      observationId: createProfileId(random),
      trialId: createProfileId(random),
      movement: /** @type {import('@crossword/domain').CalibrationMovementV1} */ (movement),
      offered: persistedOffer,
      response: persistedResponse,
      ...(persistedRelation ? { relation: persistedRelation } : {}),
      presentedAt: shownAt,
      recordedAt: eventAt,
    });
    nextSession = {
      ...session,
      observations,
      actions,
      currentMovement: /** @type {import('@crossword/domain').CalibrationMovementV1} */ (nextMovement ?? session.currentMovement),
      updatedAt: eventAt,
    };
  } else if (
    nextMovement !== undefined &&
    nextMovement !== session.currentMovement
  ) {
    nextSession = {
      ...session,
      currentMovement: /** @type {import('@crossword/domain').CalibrationMovementV1} */ (nextMovement),
      updatedAt: nondecreasingTimestamp(session.updatedAt, eventAt),
    };
  }
  return validated(nextSession);
}

/**
 * Explicitly end onboarding early. The current cursor and user-supplied setup
 * are retained, while unshown movements produce no fabricated observations.
 * @param {import('@crossword/domain').CalibrationSessionV1} session
 * @param {{reason: 'start-puzzle' | 'skip-calibration', setup: import('@crossword/domain').CalibrationSetupV1}} input
 * @param {{now?: Date | string | (() => Date | string)}} [options]
 */
export function skipCalibration(session, { reason, setup }, { now } = {}) {
  requireSession(session);
  if (session.status !== 'in-progress') {
    throw new TypeError('A terminal calibration cannot be skipped again.');
  }
  const skippedAt = nondecreasingTimestamp(session.updatedAt, isoTimestamp(now));
  return validated({
    ...session,
    setup: { ...setup },
    status: 'skipped',
    updatedAt: skippedAt,
    skip: { movement: session.currentMovement, reason, skippedAt },
  });
}

/**
 * Complete calibration only after the fifth movement and explicit setup.
 * @param {import('@crossword/domain').CalibrationSessionV1} session
 * @param {{setup: import('@crossword/domain').CalibrationSetupV1}} input
 * @param {{now?: Date | string | (() => Date | string)}} [options]
 */
export function completeCalibration(session, { setup }, { now } = {}) {
  requireSession(session);
  if (session.status !== 'in-progress') {
    throw new TypeError('A terminal calibration cannot be completed again.');
  }
  if (session.currentMovement !== 5) {
    throw new TypeError('Calibration can only be completed from movement 5.');
  }
  const events = orderedCalibrationEvents(session);
  if (!events) throw new TypeError('The calibration event stream is invalid.');
  const observationsById = new Map();
  const activeObservationIds = new Set();
  for (const event of events) {
    if (event.kind === 'observation') {
      observationsById.set(event.value.observationId, event.value);
      activeObservationIds.add(event.value.observationId);
    } else if (event.value.action === 'retract') {
      activeObservationIds.delete(event.value.targetObservationId);
    } else {
      activeObservationIds.add(event.value.targetObservationId);
    }
  }
  const answeredMovements = new Set(
    [...activeObservationIds].map(
      (observationId) => observationsById.get(observationId)?.movement,
    ),
  );
  if (![1, 2, 3, 4].every((movement) => answeredMovements.has(movement))) {
    throw new TypeError('Movements 1 through 4 need a current response before completion.');
  }
  const completedAt = nondecreasingTimestamp(session.updatedAt, isoTimestamp(now));
  return validated({
    ...session,
    setup: { ...setup },
    status: 'completed',
    updatedAt: completedAt,
    completedAt,
  });
}
