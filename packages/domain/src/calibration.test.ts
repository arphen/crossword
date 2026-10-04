import { describe, expect, it } from 'vitest';
import {
  CALIBRATION_MAX_OBSERVATIONS,
  CALIBRATION_MAX_OFFERED_STIMULI,
  orderedCalibrationEvents,
  validateCalibrationSession,
} from './calibration';
import type {
  CalibrationObservationActionV1,
  CalibrationObservationV1,
  CalibrationSessionV1,
} from './calibration';

const at = (second: number) => `2026-09-26T10:00:${String(second).padStart(2, '0')}.000Z`;

function offer(stimulusId: string, position: number, stimulusVersion = '1') {
  return { stimulusId, stimulusVersion, position };
}

function observation(
  overrides: Partial<CalibrationObservationV1> = {},
): CalibrationObservationV1 {
  return {
    sequence: 1,
    observationId: 'obs-1',
    trialId: 'trial-1',
    movement: 1,
    offered: [offer('thread', 0), offer('stone', 1)],
    response: { kind: 'choose', chosenIds: ['thread'] },
    presentedAt: at(0),
    recordedAt: at(0),
    ...overrides,
  };
}

function session(overrides: Partial<CalibrationSessionV1> = {}): CalibrationSessionV1 {
  return {
    schemaVersion: 1,
    calibrationId: 'calibration-1',
    scope: { kind: 'profile', profileId: 'profile-1' },
    bankVersion: 'stimuli-2026-09',
    selectorVersion: 'selector-v1',
    seed: 1_823_562_923,
    presentationMode: 'visual',
    currentMovement: 1,
    observations: [],
    actions: [],
    status: 'in-progress',
    createdAt: at(0),
    updatedAt: at(0),
    ...overrides,
  };
}

function action(
  overrides: Partial<CalibrationObservationActionV1> = {},
): CalibrationObservationActionV1 {
  return {
    sequence: 2,
    actionId: 'action-1',
    targetObservationId: 'obs-1',
    action: 'retract',
    recordedAt: at(2),
    ...overrides,
  };
}

describe('personal episteme calibration contract', () => {
  it('accepts a completed calibration with explicit challenge/language and reproducible offers', () => {
    const first = observation();
    const second = observation({
      sequence: 2,
      observationId: 'obs-2',
      trialId: 'trial-2',
      movement: 2,
      offered: [offer('fork', 0), offer('paper-map', 1)],
      response: { kind: 'choose', chosenIds: ['fork'] },
      relation: {
        kind: 'place-beside',
        fromStimulusId: 'thread',
        toStimulusId: 'fork',
      },
      presentedAt: at(2),
      recordedAt: at(2),
    });
    const third = observation({
      sequence: 3,
      observationId: 'obs-3',
      trialId: 'trial-3',
      movement: 3,
      offered: [offer('bell', 0), offer('thread', 1)],
      response: { kind: 'pass' },
      presentedAt: at(3),
      recordedAt: at(3),
    });
    const fourth = observation({
      sequence: 4,
      observationId: 'obs-4',
      trialId: 'trial-4',
      movement: 4,
      offered: [offer('moon', 0), offer('stone', 1)],
      response: { kind: 'pass' },
      presentedAt: at(4),
      recordedAt: at(4),
    });
    const value = session({
      currentMovement: 5,
      observations: [first, second, third, fourth],
      setup: { weekday: 'Wednesday', language: 'de-DE' },
      status: 'completed',
      updatedAt: at(5),
      completedAt: at(5),
    });

    expect(validateCalibrationSession(value)).toBe(true);
    expect(orderedCalibrationEvents(value)?.map((event) => event.kind)).toEqual([
      'observation',
      'observation',
      'observation',
      'observation',
    ]);
  });

  it('accepts a pass as a recorded observation without treating it as rejection evidence', () => {
    const passed = observation({
      response: { kind: 'pass' },
      elapsedMs: 3_599_999,
    });
    expect(validateCalibrationSession(session({ observations: [passed] }))).toBe(true);
  });

  it('accepts immutable retract and restore actions in a globally sequenced stream', () => {
    const first = observation({ movement: 2 });
    const revisitedEarlierMovement = observation({
      sequence: 4,
      observationId: 'obs-2',
      trialId: 'trial-2',
      movement: 1,
      response: { kind: 'choose', chosenIds: ['stone'] },
      presentedAt: at(4),
      recordedAt: at(4),
    });
    const value = session({
      updatedAt: at(4),
      observations: [first, revisitedEarlierMovement],
      actions: [
        action({ sequence: 2, action: 'retract', recordedAt: at(2) }),
        action({
          sequence: 3,
          actionId: 'action-2',
          action: 'restore',
          recordedAt: at(3),
        }),
      ],
    });

    expect(validateCalibrationSession(value)).toBe(true);
    expect(orderedCalibrationEvents(value)?.map((event) => event.kind)).toEqual([
      'observation',
      'action',
      'action',
      'observation',
    ]);
  });

  it('rejects duplicate ids, gaps, and out-of-order array entries', () => {
    const first = observation();
    const second = observation({
      sequence: 3,
      observationId: 'obs-2',
      trialId: 'trial-2',
      movement: 2,
      presentedAt: at(3),
      recordedAt: at(3),
    });
    const withGap = session({
      observations: [first, { ...second, sequence: 4 }],
      actions: [action({ sequence: 2 })],
      updatedAt: at(3),
    });
    expect(orderedCalibrationEvents(withGap)).toBeNull();
    expect(validateCalibrationSession(withGap)).toBe(false);

    const outOfOrder = session({
      observations: [second, first],
      updatedAt: at(3),
    });
    expect(orderedCalibrationEvents(outOfOrder)).toBeNull();
    expect(validateCalibrationSession(outOfOrder)).toBe(false);

    expect(
      validateCalibrationSession(
        session({ observations: [first, observation({ observationId: 'obs-1', sequence: 2, trialId: 'trial-2' })] }),
      ),
    ).toBe(false);
  });

  it('rejects a choice that was not offered and incomplete or duplicate positions', () => {
    const missingOffer = observation({
      response: { kind: 'choose', chosenIds: ['unknown'] },
    });
    const duplicatePosition = observation({
      offered: [offer('thread', 0), offer('stone', 0)],
    });
    const missingPosition = observation({
      offered: [offer('thread', 0), offer('stone', 2)],
    });
    expect(validateCalibrationSession(session({ observations: [missingOffer] }))).toBe(false);
    expect(validateCalibrationSession(session({ observations: [duplicatePosition] }))).toBe(false);
    expect(validateCalibrationSession(session({ observations: [missingPosition] }))).toBe(false);
  });

  it('requires relation endpoints to be chosen now or remain active from an earlier observation', () => {
    const unrelated = observation({
      sequence: 2,
      observationId: 'obs-2',
      trialId: 'trial-2',
      movement: 2,
      offered: [offer('fork', 0), offer('map', 1)],
      response: { kind: 'choose', chosenIds: ['fork'] },
      relation: { kind: 'pair', fromStimulusId: 'key', toStimulusId: 'fork' },
      presentedAt: at(2),
      recordedAt: at(2),
    });
    expect(
      validateCalibrationSession(
        session({ observations: [observation(), unrelated], updatedAt: at(2) }),
      ),
    ).toBe(false);

    const retractedThenRelated = session({
      currentMovement: 2,
      observations: [observation(), { ...unrelated, sequence: 3 }],
      actions: [action({ sequence: 2, recordedAt: at(1) })],
      updatedAt: at(2),
    });
    expect(validateCalibrationSession(retractedThenRelated)).toBe(false);
  });

  it('requires undo/restore actions to target a prior choice and alternate per target', () => {
    const first = observation();
    expect(
      validateCalibrationSession(
        session({
          observations: [first],
          actions: [action({ action: 'restore' })],
          updatedAt: at(2),
        }),
      ),
    ).toBe(false);
    expect(
      validateCalibrationSession(
        session({
          observations: [first],
          actions: [
            action({ sequence: 2 }),
            action({ sequence: 3, actionId: 'action-2', action: 'retract', recordedAt: at(3) }),
          ],
          updatedAt: at(3),
        }),
      ),
    ).toBe(false);
    expect(
      validateCalibrationSession(
        session({
          observations: [observation({ response: { kind: 'pass' } })],
          actions: [action()],
          updatedAt: at(2),
        }),
      ),
    ).toBe(false);
  });

  it('validates terminal state, scope, seed, versions, and language as explicit bounded values', () => {
    const answered = [1, 2, 3, 4].map((movement, index) =>
      observation({
        sequence: index + 1,
        observationId: `complete-obs-${movement}`,
        trialId: `complete-trial-${movement}`,
        movement: movement as 1 | 2 | 3 | 4,
        response: { kind: 'pass' },
        presentedAt: at(index),
        recordedAt: at(index),
      }),
    );
    const value = session({
      currentMovement: 5,
      observations: answered,
      status: 'completed',
      setup: { weekday: 'Thursday', language: 'fr' },
      updatedAt: at(4),
      completedAt: at(4),
    });
    expect(validateCalibrationSession(value)).toBe(true);
    expect(validateCalibrationSession({ ...value, setup: undefined })).toBe(false);
    expect(validateCalibrationSession({ ...value, seed: -1 })).toBe(false);
    expect(validateCalibrationSession({ ...value, seed: 0x1_0000_0000 })).toBe(false);
    expect(validateCalibrationSession({ ...value, scope: { kind: 'profile', profileId: '' } })).toBe(false);
    expect(validateCalibrationSession({ ...value, setup: { weekday: 'Thursday', language: 'not a tag' } })).toBe(false);
    expect(validateCalibrationSession({ ...value, extra: true })).toBe(false);
  });

  it('requires an active response for each stimulus movement to call calibration completed', () => {
    const answered = [1, 2, 3, 4].map((movement, index) =>
      observation({
        sequence: index + 1,
        observationId: `answer-obs-${movement}`,
        trialId: `answer-trial-${movement}`,
        movement: movement as 1 | 2 | 3 | 4,
        response: { kind: 'pass' },
        presentedAt: at(index),
        recordedAt: at(index),
      }),
    );
    const completed = session({
      currentMovement: 5,
      observations: answered,
      setup: { weekday: 'Thursday', language: 'fr' },
      status: 'completed',
      updatedAt: at(4),
      completedAt: at(4),
    });
    expect(validateCalibrationSession(completed)).toBe(true);
    expect(
      validateCalibrationSession({
        ...completed,
        observations: answered.filter((item) => item.movement !== 3),
        updatedAt: at(4),
        completedAt: at(4),
      }),
    ).toBe(false);

    const retractedLastMovement = session({
      ...completed,
      observations: answered.map((item) =>
        item.movement === 4
          ? { ...item, response: { kind: 'choose' as const, chosenIds: ['thread'] } }
          : item,
      ),
      actions: [
        action({
          sequence: 5,
          actionId: 'action-5',
          targetObservationId: 'answer-obs-4',
          recordedAt: at(5),
        }),
      ],
      updatedAt: at(6),
      completedAt: at(6),
    });
    expect(validateCalibrationSession(retractedLastMovement)).toBe(false);
  });

  it('requires stable versions for a stimulus throughout its frozen bank session', () => {
    const first = observation();
    const second = observation({
      sequence: 2,
      observationId: 'obs-2',
      trialId: 'trial-2',
      movement: 2,
      offered: [offer('thread', 0, '2'), offer('fork', 1)],
      response: { kind: 'choose', chosenIds: ['fork'] },
      presentedAt: at(2),
      recordedAt: at(2),
    });
    expect(
      validateCalibrationSession(
        session({ observations: [first, second], updatedAt: at(2) }),
      ),
    ).toBe(false);
  });

  it('enforces observation, offer, and serialized session bounds', () => {
    const offeredTooMany = observation({
      offered: Array.from({ length: CALIBRATION_MAX_OFFERED_STIMULI + 1 }, (_, index) =>
        offer(`item-${index}`, index),
      ),
    });
    expect(validateCalibrationSession(session({ observations: [offeredTooMany] }))).toBe(false);

    const tooManyObservations = Array.from(
      { length: CALIBRATION_MAX_OBSERVATIONS + 1 },
      (_, index) =>
        observation({
          sequence: index + 1,
          observationId: `obs-${index}`,
          trialId: `trial-${index}`,
          presentedAt: at(0),
          recordedAt: at(0),
        }),
    );
    expect(validateCalibrationSession(session({ observations: tooManyObservations }))).toBe(false);

    const oversized = Array.from({ length: CALIBRATION_MAX_OBSERVATIONS }, (_, index) =>
      observation({
        sequence: index + 1,
        observationId: `obs-${index}`,
        trialId: `trial-${index}`,
        offered: Array.from({ length: CALIBRATION_MAX_OFFERED_STIMULI }, (_, slot) =>
          offer(`stimulus-${String(slot).padStart(3, '0')}-${'x'.repeat(125)}`, slot),
        ),
        presentedAt: at(0),
        recordedAt: at(0),
      }),
    );
    expect(validateCalibrationSession(session({ observations: oversized }))).toBe(false);
  });

  it('represents a skipped setup distinctly from a completed setup', () => {
    const skipped = session({
      currentMovement: 1,
      status: 'skipped',
      skip: { movement: 1, reason: 'start-puzzle', skippedAt: at(1) },
      updatedAt: at(1),
    });
    expect(validateCalibrationSession(skipped)).toBe(true);
    expect(
      validateCalibrationSession({
        ...skipped,
        completedAt: at(1),
      }),
    ).toBe(false);
  });
});
