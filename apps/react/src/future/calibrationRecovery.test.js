import { describe, expect, it } from 'vitest';
import {
  CALIBRATION_RECOVERY_VERSION,
  createCalibrationRecoveryDraft,
  describeCalibrationConflict,
} from './calibrationRecovery';

const profile = {
  id: '4e1091f5-e7ea-48cd-8f99-b56151f8c20f',
  calibrationId: 'e4cab20a-c164-45c2-8d4e-c2fe07e75f7a',
  weekday: 'thursday',
  learningLanguage: 'German',
  presentationMode: 'monochrome',
  profileUpdatedAt: '2026-09-26T12:00:00.000Z',
};

function deterministicRandom(uuid) {
  return { randomUUID: () => uuid };
}

describe('calibration recovery', () => {
  it('keeps conflict presentation explicit and offers only safe branch actions', () => {
    expect(
      describeCalibrationConflict({
        syncStatus: 'conflict',
        revision: 4,
        hostRevision: 3,
      }),
    ).toEqual({
      version: CALIBRATION_RECOVERY_VERSION,
      title: 'This opening has two branches.',
      message:
        'Your choices are still safe on this device. The local server has a different saved branch, so the two journals stay separate.',
      localRevision: 4,
      hostRevision: 3,
      actions: [
        {
          id: 'keep-local',
          label: 'Keep this opening here',
          description: 'Continue on this device and leave the saved branch untouched.',
        },
        {
          id: 'new-branch',
          label: 'Start a fresh opening',
          description: 'Begin again with a new journal while this branch remains preserved.',
        },
      ],
    });
    expect(describeCalibrationConflict({ syncStatus: 'pending' })).toBeNull();
    expect(describeCalibrationConflict(null, 'conflict').actions).toHaveLength(2);
  });

  it('creates a new branch without changing the profile or setup choices', () => {
    const next = createCalibrationRecoveryDraft(profile, {
      random: deterministicRandom('d4d5d6d7-d8d9-4da0-8da1-d2d3d4d5d6d7'),
    });

    expect(next).toEqual({
      version: 1,
      id: profile.id,
      calibrationId: 'd4d5d6d7-d8d9-4da0-8da1-d2d3d4d5d6d7',
      step: 0,
      object: null,
      firstStimulus: null,
      companion: null,
      variation: null,
      presentationMode: 'monochrome',
      traces: [],
      weekday: 'thursday',
      learningLanguage: 'German',
      excluded: [],
      reflection: null,
      complete: false,
      profileUpdatedAt: profile.profileUpdatedAt,
    });
    expect(next.calibrationId).not.toBe(profile.calibrationId);
  });

  it('does not synthesize a recovery draft without a profile identity', () => {
    expect(() => createCalibrationRecoveryDraft({})).toThrow(/profile id/);
  });
});
