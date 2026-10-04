import { describe, expect, it } from 'vitest';
import {
  orderedCalibrationEvents,
  validateCalibrationSession,
} from '@crossword/domain';
import {
  appendCalibrationObservation,
  completeCalibration,
  createInitialCalibrationSession,
  skipCalibration,
  updateCalibrationCursor,
} from './calibrationRuntime';
import { CALIBRATION_SELECTOR_VERSION_V2 } from './calibrationPresentation.js';

const uuid = (tail) => `00000000-0000-4000-8000-${String(tail).padStart(12, '0')}`;
const at = (second) => new Date(`2026-09-26T10:00:${String(second).padStart(2, '0')}.000Z`);

function randomIds() {
  let next = 1;
  return { randomUUID: () => uuid(next++) };
}

function initial(options = {}) {
  return createInitialCalibrationSession({
    draft: {
      id: uuid(90),
      calibrationId: uuid(91),
      presentationMode: 'monochrome',
    },
    now: at(0),
    random: randomIds(),
    ...options,
  });
}

const offer = [
  { stimulusId: 'thread-knot', stimulusVersion: '1', position: 0 },
  { stimulusId: 'river-stone', stimulusVersion: '1', position: 1 },
];

function choose(session, chosenIds, second, extra = {}) {
  return appendCalibrationObservation(
    session,
    {
      movement: 1,
      offered: offer,
      response: { kind: 'choose', chosenIds },
      presentedAt: at(second),
      ...extra,
    },
    { now: at(second), random: randomIds() },
  );
}

describe('calibration runtime event helpers', () => {
  it('creates a valid, reproducible empty profile session', () => {
    const session = initial();
    expect(validateCalibrationSession(session)).toBe(true);
    expect(session).toMatchObject({
      schemaVersion: 1,
      calibrationId: uuid(91),
      scope: { kind: 'profile', profileId: uuid(90) },
      bankVersion: '1',
      selectorVersion: CALIBRATION_SELECTOR_VERSION_V2,
      presentationMode: 'monochrome',
      currentMovement: 1,
      observations: [],
      actions: [],
      status: 'in-progress',
      createdAt: at(0).toISOString(),
      updatedAt: at(0).toISOString(),
    });
    expect(session.seed).toBeGreaterThanOrEqual(0);
    expect(session.seed).toBeLessThanOrEqual(0xffffffff);
  });

  it('moves the cursor backward and advances one movement at a time without touching evidence', () => {
    const started = initial();
    const second = updateCalibrationCursor(started, 2, { now: at(2) });
    const third = updateCalibrationCursor(second, 3, { now: at(8) });
    const later = updateCalibrationCursor(third, 4, { now: at(9) });
    const revisited = updateCalibrationCursor(later, 2, { now: at(3) });
    expect(later.currentMovement).toBe(4);
    expect(revisited.currentMovement).toBe(2);
    expect(revisited.observations).toBe(started.observations);
    expect(revisited.updatedAt).toBe(at(9).toISOString());
    expect(validateCalibrationSession(revisited)).toBe(true);
  });

  it('appends a chosen response and retracts the previous chosen observation on revision', () => {
    const first = choose(initial(), ['thread-knot'], 1, { nextMovement: 2 });
    const revised = choose(first, ['river-stone'], 2);
    expect(first.observations).toHaveLength(1);
    expect(revised.observations).toHaveLength(2);
    expect(revised.actions).toHaveLength(1);
    expect(revised.actions[0]).toMatchObject({
      sequence: 2,
      targetObservationId: first.observations[0].observationId,
      action: 'retract',
      recordedAt: at(2).toISOString(),
    });
    expect(revised.observations[1]).toMatchObject({
      sequence: 3,
      movement: 1,
      response: { kind: 'choose', chosenIds: ['river-stone'] },
    });
    expect(
      orderedCalibrationEvents(revised)?.map(({ kind, sequence }) => [kind, sequence]),
    ).toEqual([
      ['observation', 1],
      ['action', 2],
      ['observation', 3],
    ]);
    expect(validateCalibrationSession(revised)).toBe(true);
  });

  it('retracts active choices from selected movements before appending a new response', () => {
    const random = randomIds();
    const respond = (session, movement, chosenId, second, extra = {}) =>
      appendCalibrationObservation(
        session,
        {
          movement,
          offered: offer,
          response: { kind: 'choose', chosenIds: [chosenId] },
          presentedAt: at(second),
          ...extra,
        },
        { now: at(second), random },
      );

    const movementOne = respond(initial(), 1, 'thread-knot', 1);
    const movementTwo = respond(movementOne, 2, 'river-stone', 2);
    const movementThree = respond(movementTwo, 3, 'thread-knot', 3);
    const revisedMovementOne = respond(
      movementThree,
      1,
      'river-stone',
      4,
      { retractMovements: [2, 3] },
    );

    expect(revisedMovementOne.actions.map((action) => [
      action.sequence,
      action.targetObservationId,
      action.action,
    ])).toEqual([
      [4, movementOne.observations[0].observationId, 'retract'],
      [5, movementTwo.observations[1].observationId, 'retract'],
      [6, movementThree.observations[2].observationId, 'retract'],
    ]);
    expect(revisedMovementOne.observations[3]).toMatchObject({
      sequence: 7,
      movement: 1,
      response: { kind: 'choose', chosenIds: ['river-stone'] },
    });
    expect(
      orderedCalibrationEvents(revisedMovementOne)?.map(({ sequence }) => sequence),
    ).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(validateCalibrationSession(revisedMovementOne)).toBe(true);
  });

  it('does not append an identical active response, offer, and relation on retry', () => {
    const relation = {
      kind: 'contrast',
      fromStimulusId: 'thread-knot',
      toStimulusId: 'river-stone',
    };
    const first = appendCalibrationObservation(
      initial(),
      {
        movement: 1,
        offered: offer,
        response: { kind: 'choose', chosenIds: ['river-stone', 'thread-knot'] },
        relation,
        presentedAt: at(1),
      },
      { now: at(1), random: randomIds() },
    );
    const retried = appendCalibrationObservation(
      first,
      {
        movement: 1,
        offered: offer.map((item) => ({ ...item })),
        response: { kind: 'choose', chosenIds: ['thread-knot', 'river-stone'] },
        relation: { ...relation },
        presentedAt: at(2),
      },
      { now: at(2), random: randomIds() },
    );
    expect(retried).toBe(first);
    expect(retried.observations).toHaveLength(1);
    expect(retried.actions).toHaveLength(0);
  });

  it('records a pass and retracts earlier chosen evidence without treating the pass as a choice', () => {
    const chosen = choose(initial(), ['thread-knot'], 1);
    const passed = appendCalibrationObservation(
      chosen,
      {
        movement: 1,
        offered: offer,
        response: { kind: 'pass' },
        presentedAt: at(2),
      },
      { now: at(2), random: randomIds() },
    );
    expect(passed.observations).toHaveLength(2);
    expect(passed.observations[1]).toMatchObject({
      sequence: 3,
      response: { kind: 'pass' },
    });
    expect(passed.actions).toMatchObject([
      {
        sequence: 2,
        targetObservationId: chosen.observations[0].observationId,
        action: 'retract',
      },
    ]);
    const retry = appendCalibrationObservation(
      passed,
      {
        movement: 1,
        offered: offer,
        response: { kind: 'pass' },
        presentedAt: at(3),
      },
      { now: at(3), random: randomIds() },
    );
    expect(retry).toBe(passed);
    expect(validateCalibrationSession(passed)).toBe(true);
  });

  it('skips without inventing observations and retains the explicit setup and current movement', () => {
    const atMovementTwo = updateCalibrationCursor(initial(), 2, { now: at(1) });
    const atMovementThree = updateCalibrationCursor(atMovementTwo, 3, { now: at(2) });
    const skipped = skipCalibration(
      atMovementThree,
      {
        reason: 'start-puzzle',
        setup: { weekday: 'Wednesday', language: 'de-DE' },
      },
      { now: at(3) },
    );
    expect(skipped).toMatchObject({
      currentMovement: 3,
      setup: { weekday: 'Wednesday', language: 'de-DE' },
      status: 'skipped',
      skip: {
        movement: 3,
        reason: 'start-puzzle',
        skippedAt: at(3).toISOString(),
      },
      observations: [],
      actions: [],
    });
    expect(validateCalibrationSession(skipped)).toBe(true);
  });

  it('completes only from movement five with explicit setup', () => {
    let atMovementFive = initial();
    const random = randomIds();
    for (let movement = 1; movement <= 4; movement += 1) {
      atMovementFive = appendCalibrationObservation(
        atMovementFive,
        {
          movement,
          offered: offer,
          response: { kind: 'pass' },
          presentedAt: at(movement),
          nextMovement: movement + 1,
        },
        { now: at(movement), random },
      );
    }
    const completed = completeCalibration(
      atMovementFive,
      { setup: { weekday: 'Thursday', language: 'fr' } },
      { now: at(5) },
    );
    expect(completed).toMatchObject({
      currentMovement: 5,
      setup: { weekday: 'Thursday', language: 'fr' },
      status: 'completed',
      completedAt: at(5).toISOString(),
      updatedAt: at(5).toISOString(),
    });
    expect(completed.observations.map((item) => item.movement)).toEqual([1, 2, 3, 4]);
    expect(validateCalibrationSession(completed)).toBe(true);
  });

  it('rejects invalid movements, malformed evidence, and invalid terminal transitions', () => {
    const started = initial();
    expect(() => updateCalibrationCursor(started, 6, { now: at(1) })).toThrow();
    expect(() => updateCalibrationCursor(started, 5, { now: at(1) })).toThrow(/skip a movement/);
    expect(() => updateCalibrationCursor(started, 2, { now: at(1) })).not.toThrow();
    expect(() =>
      appendCalibrationObservation(
        started,
        {
          movement: 1,
          offered: offer,
          response: { kind: 'pass' },
          nextMovement: 5,
        },
        { now: at(1), random: randomIds() },
      ),
    ).toThrow(/skip a movement/);
    expect(() =>
      appendCalibrationObservation(
        started,
        {
          movement: 7,
          offered: offer,
          response: { kind: 'choose', chosenIds: ['thread-knot'] },
        },
        { now: at(1), random: randomIds() },
      ),
    ).toThrow();
    expect(() =>
      appendCalibrationObservation(
        started,
        {
          movement: 1,
          offered: offer,
          response: { kind: 'choose', chosenIds: ['not-offered'] },
        },
        { now: at(1), random: randomIds() },
      ),
    ).toThrow();
    expect(() =>
      completeCalibration(
        started,
        { setup: { weekday: 'Wednesday', language: 'en' } },
        { now: at(1) },
      ),
    ).toThrow(/movement 5/);
    const emptyAtMovementFive = updateCalibrationCursor(
      updateCalibrationCursor(
        updateCalibrationCursor(
          updateCalibrationCursor(started, 2, { now: at(1) }),
          3,
          { now: at(2) },
        ),
        4,
        { now: at(3) },
      ),
      5,
      { now: at(4) },
    );
    expect(() =>
      completeCalibration(
        emptyAtMovementFive,
        { setup: { weekday: 'Wednesday', language: 'en' } },
        { now: at(5) },
      ),
    ).toThrow(/Movements 1 through 4/);
    const skipped = skipCalibration(
      started,
      {
        reason: 'skip-calibration',
        setup: { weekday: 'Wednesday', language: 'en' },
      },
      { now: at(1) },
    );
    expect(() => updateCalibrationCursor(skipped, 2, { now: at(2) })).toThrow();
    expect(() => completeCalibration(skipped, { setup: { weekday: 'Wednesday', language: 'en' } })).toThrow();
  });
});
