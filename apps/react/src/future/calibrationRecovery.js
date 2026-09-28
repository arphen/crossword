import { createProfileId } from './episteme';

export const CALIBRATION_RECOVERY_VERSION = 'calibration-conflict-recovery-v1';

/**
 * Describe a calibration conflict without interpreting any of the player's
 * choices. The journal stays the source of truth; this is only presentation
 * copy and a pair of safe actions for the onboarding surface.
 *
 * @param {{syncStatus?: string, revision?: number, hostRevision?: number}|null|undefined} record
 * @param {string|undefined} [status]
 */
export function describeCalibrationConflict(record, status = record?.syncStatus) {
  if (status !== 'conflict') return null;

  const localRevision = Number.isSafeInteger(record?.revision)
    ? record.revision
    : null;
  const hostRevision = Number.isSafeInteger(record?.hostRevision)
    ? record.hostRevision
    : null;
  const hostHasKnownProgress = hostRevision !== null && hostRevision > 0;

  return {
    version: CALIBRATION_RECOVERY_VERSION,
    title: 'This opening has two branches.',
    message: hostHasKnownProgress
      ? 'Your choices are still safe on this device. The local server has a different saved branch, so the two journals stay separate.'
      : 'Your choices are still safe on this device. The local server has a different saved branch, so the two journals stay separate.',
    localRevision,
    hostRevision,
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
  };
}

/**
 * Start a new calibration branch for the same profile. Explicit setup choices
 * remain useful, while visual responses and their calibration id are fresh.
 * The previous journal is deliberately not edited or deleted.
 *
 * @param {{id: string, weekday?: string, learningLanguage?: string, presentationMode?: string, profileUpdatedAt?: string}} draft
 * @param {{random?: Crypto}} [options]
 */
export function createCalibrationRecoveryDraft(draft, { random = globalThis.crypto } = {}) {
  if (!draft || typeof draft.id !== 'string' || draft.id.length === 0) {
    throw new TypeError('A profile id is required to start a fresh calibration branch.');
  }

  const next = {
    version: 1,
    id: draft.id,
    calibrationId: createProfileId(random),
    step: 0,
    object: null,
    firstStimulus: null,
    companion: null,
    variation: null,
    presentationMode: draft.presentationMode ?? 'visual',
    traces: [],
    weekday: draft.weekday ?? 'wednesday',
    learningLanguage: draft.learningLanguage ?? 'None for now',
    excluded: [],
    reflection: null,
    complete: false,
  };
  if (typeof draft.profileUpdatedAt === 'string') {
    next.profileUpdatedAt = draft.profileUpdatedAt;
  }
  return next;
}
