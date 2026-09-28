/** Bounded raw calibration evidence. Choices are observations, not personality or knowledge claims. */
export const CALIBRATION_SCHEMA_VERSION = 1 as const;
export const CALIBRATION_MAX_OBSERVATIONS = 100;
export const CALIBRATION_MAX_OFFERED_STIMULI = 12;
export const CALIBRATION_MAX_SESSION_CHARS = 262_144;
export const CALIBRATION_MAX_ELAPSED_MS = 3_600_000;

export type CalibrationMovementV1 = 1 | 2 | 3 | 4 | 5;
export type CalibrationWeekdayV1 =
  | 'Monday'
  | 'Tuesday'
  | 'Wednesday'
  | 'Thursday'
  | 'Friday'
  | 'Saturday'
  | 'Sunday';
export type CalibrationPresentationModeV1 =
  | 'visual'
  | 'monochrome'
  | 'text-equivalent';

export type CalibrationScopeV1 =
  | Readonly<{ kind: 'profile'; profileId: string }>
  | Readonly<{ kind: 'guest'; guestId: string }>;

export type CalibrationStimulusPresentationV1 = Readonly<{
  stimulusId: string;
  stimulusVersion: string;
  /** Stable slot in the presented spread (zero-based); this is not a screen coordinate. */
  position: number;
}>;

export type CalibrationResponseV1 =
  | Readonly<{ kind: 'choose'; chosenIds: readonly string[] }>
  | Readonly<{ kind: 'pass' }>;

export type CalibrationRelationV1 =
  | Readonly<{
      kind: 'pair' | 'place-beside' | 'contrast';
      fromStimulusId: string;
      toStimulusId: string;
    }>
  | Readonly<{ kind: 'keep-original'; stimulusId: string }>;

/** Revisions are append-only; restore must follow a retract for the same observation. */
export type CalibrationObservationActionV1 = Readonly<{
  sequence: number;
  actionId: string;
  targetObservationId: string;
  action: 'retract' | 'restore';
  recordedAt: string;
}>;

export type CalibrationObservationV1 = Readonly<{
  sequence: number;
  observationId: string;
  trialId: string;
  movement: CalibrationMovementV1;
  offered: readonly CalibrationStimulusPresentationV1[];
  response: CalibrationResponseV1;
  relation?: CalibrationRelationV1;
  /** Usability/debugging only; never a preference, familiarity, or knowledge feature. */
  elapsedMs?: number;
  presentedAt: string;
  recordedAt: string;
}>;

export type CalibrationSkipV1 = Readonly<{
  movement: CalibrationMovementV1;
  reason: 'start-puzzle' | 'skip-calibration';
  skippedAt: string;
}>;

export type CalibrationSetupV1 = Readonly<{
  weekday: CalibrationWeekdayV1;
  language: string;
}>;

/** One bounded, reproducible opening. The practical setup is explicit and separate from traces. */
export type CalibrationSessionV1 = Readonly<{
  schemaVersion: typeof CALIBRATION_SCHEMA_VERSION;
  calibrationId: string;
  scope: CalibrationScopeV1;
  bankVersion: string;
  selectorVersion: string;
  /** Unsigned 32-bit selector seed, retained so the offered order can be reproduced. */
  seed: number;
  presentationMode: CalibrationPresentationModeV1;
  currentMovement: CalibrationMovementV1;
  observations: readonly CalibrationObservationV1[];
  actions: readonly CalibrationObservationActionV1[];
  setup?: CalibrationSetupV1;
  status: 'in-progress' | 'completed' | 'skipped';
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  skip?: CalibrationSkipV1;
}>;

export type CalibrationEventV1 =
  | Readonly<{
      kind: 'observation';
      sequence: number;
      value: CalibrationObservationV1;
    }>
  | Readonly<{
      kind: 'action';
      sequence: number;
      value: CalibrationObservationActionV1;
    }>;

type RecordValue = Record<string, unknown>;

function isRecord(value: unknown): value is RecordValue {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasExactKeys(
  value: RecordValue,
  required: readonly string[],
  optional: readonly string[] = [],
): boolean {
  const allowed = new Set([...required, ...optional]);
  return (
    required.every((key) => Object.hasOwn(value, key)) &&
    Object.keys(value).every((key) => allowed.has(key))
  );
}

function isBoundedText(value: unknown, max = 160): value is string {
  return (
    typeof value === 'string' &&
    value.length > 0 &&
    value.length <= max &&
    value.trim() === value &&
    value.normalize('NFC') === value
  );
}

function isDateTime(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.length <= 40 &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(
      value,
    ) &&
    Number.isFinite(Date.parse(value))
  );
}

function isMovement(value: unknown): value is CalibrationMovementV1 {
  return Number.isSafeInteger(value) && Number(value) >= 1 && Number(value) <= 5;
}

function isLanguageTag(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.length <= 63 &&
    /^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/.test(value)
  );
}

function isScope(value: unknown): value is CalibrationScopeV1 {
  if (!isRecord(value)) return false;
  if (value.kind === 'profile') {
    return (
      hasExactKeys(value, ['kind', 'profileId']) &&
      isBoundedText(value.profileId)
    );
  }
  if (value.kind === 'guest') {
    return (
      hasExactKeys(value, ['kind', 'guestId']) && isBoundedText(value.guestId)
    );
  }
  return false;
}

function isStimulusPresentation(
  value: unknown,
): value is CalibrationStimulusPresentationV1 {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['stimulusId', 'stimulusVersion', 'position']) &&
    isBoundedText(value.stimulusId) &&
    isBoundedText(value.stimulusVersion, 80) &&
    Number.isSafeInteger(value.position) &&
    Number(value.position) >= 0 &&
    Number(value.position) < CALIBRATION_MAX_OFFERED_STIMULI
  );
}

function isResponse(value: unknown): value is CalibrationResponseV1 {
  if (!isRecord(value)) return false;
  if (value.kind === 'pass') return hasExactKeys(value, ['kind']);
  if (
    value.kind !== 'choose' ||
    !hasExactKeys(value, ['kind', 'chosenIds']) ||
    !Array.isArray(value.chosenIds) ||
    value.chosenIds.length < 1 ||
    value.chosenIds.length > 2 ||
    !value.chosenIds.every((id) => isBoundedText(id))
  ) {
    return false;
  }
  return new Set(value.chosenIds).size === value.chosenIds.length;
}

function isRelation(value: unknown): value is CalibrationRelationV1 {
  if (!isRecord(value)) return false;
  if (value.kind === 'keep-original') {
    return (
      hasExactKeys(value, ['kind', 'stimulusId']) &&
      isBoundedText(value.stimulusId)
    );
  }
  return (
    ['pair', 'place-beside', 'contrast'].includes(value.kind as string) &&
    hasExactKeys(value, ['kind', 'fromStimulusId', 'toStimulusId']) &&
    isBoundedText(value.fromStimulusId) &&
    isBoundedText(value.toStimulusId) &&
    value.fromStimulusId !== value.toStimulusId
  );
}

function isObservationAction(value: unknown): value is CalibrationObservationActionV1 {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['sequence', 'actionId', 'targetObservationId', 'action', 'recordedAt']) &&
    Number.isSafeInteger(value.sequence) &&
    Number(value.sequence) > 0 &&
    isBoundedText(value.actionId) &&
    isBoundedText(value.targetObservationId) &&
    (value.action === 'retract' || value.action === 'restore') &&
    isDateTime(value.recordedAt)
  );
}

function validateObservation(
  value: unknown,
  previousActiveChoices: ReadonlySet<string>,
): value is CalibrationObservationV1 {
  if (
    !isRecord(value) ||
    !hasExactKeys(
      value,
      [
        'sequence',
        'observationId',
        'trialId',
        'movement',
        'offered',
        'response',
        'presentedAt',
        'recordedAt',
      ],
      ['relation', 'elapsedMs'],
    ) ||
    !Number.isSafeInteger(value.sequence) ||
    Number(value.sequence) <= 0 ||
    !isBoundedText(value.observationId) ||
    !isBoundedText(value.trialId) ||
    !isMovement(value.movement) ||
    !Array.isArray(value.offered) ||
    value.offered.length < 2 ||
    value.offered.length > CALIBRATION_MAX_OFFERED_STIMULI ||
    !value.offered.every(isStimulusPresentation) ||
    !isResponse(value.response) ||
    !isDateTime(value.presentedAt) ||
    !isDateTime(value.recordedAt) ||
    Date.parse(value.recordedAt) < Date.parse(value.presentedAt) ||
    (value.elapsedMs !== undefined &&
      (typeof value.elapsedMs !== 'number' ||
        !Number.isFinite(value.elapsedMs) ||
        value.elapsedMs < 0 ||
        value.elapsedMs > CALIBRATION_MAX_ELAPSED_MS)) ||
    (value.relation !== undefined && !isRelation(value.relation))
  ) {
    return false;
  }

  const offered = value.offered as readonly CalibrationStimulusPresentationV1[];
  const stimulusIds = offered.map((item) => item.stimulusId);
  const positions = offered.map((item) => item.position);
  if (
    new Set(stimulusIds).size !== stimulusIds.length ||
    new Set(positions).size !== positions.length ||
    positions.some((position, index) => position !== index)
  ) {
    return false;
  }

  const response = value.response as CalibrationResponseV1;
  if (response.kind === 'choose') {
    const chosenIds = response.chosenIds;
    if (!chosenIds.every((id) => stimulusIds.includes(id))) return false;
  } else if (value.relation !== undefined) {
    return false;
  }

  const relation = value.relation as CalibrationRelationV1 | undefined;
  if (relation !== undefined) {
    if (response.kind !== 'choose') return false;
    if (relation.kind === 'keep-original') {
      if (!response.chosenIds.includes(relation.stimulusId)) return false;
    } else if (
      !response.chosenIds.includes(relation.toStimulusId) ||
      (!response.chosenIds.includes(relation.fromStimulusId) &&
        !previousActiveChoices.has(relation.fromStimulusId))
    ) {
      return false;
    }
  }

  return true;
}

function isSetup(value: unknown): value is CalibrationSetupV1 {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['weekday', 'language']) &&
    [
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ].includes(value.weekday as string) &&
    isLanguageTag(value.language)
  );
}

function isSkip(value: unknown): value is CalibrationSkipV1 {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['movement', 'reason', 'skippedAt']) &&
    isMovement(value.movement) &&
    ['start-puzzle', 'skip-calibration'].includes(value.reason as string) &&
    isDateTime(value.skippedAt)
  );
}

function collectOrderedCalibrationEvents(
  value: unknown,
): readonly CalibrationEventV1[] | null {
  if (!isRecord(value) || !Array.isArray(value.observations) || !Array.isArray(value.actions)) {
    return null;
  }
  const events: CalibrationEventV1[] = [];
  for (const observation of value.observations) {
    if (!isRecord(observation) || !Number.isSafeInteger(observation.sequence) || Number(observation.sequence) <= 0) {
      return null;
    }
    events.push({
      kind: 'observation',
      sequence: Number(observation.sequence),
      value: observation as unknown as CalibrationObservationV1,
    });
  }
  for (const action of value.actions) {
    if (!isRecord(action) || !Number.isSafeInteger(action.sequence) || Number(action.sequence) <= 0) {
      return null;
    }
    events.push({
      kind: 'action',
      sequence: Number(action.sequence),
      value: action as unknown as CalibrationObservationActionV1,
    });
  }
  const areOrdered = (items: readonly unknown[]) => {
    let previous = 0;
    for (const item of items) {
      if (
        !isRecord(item) ||
        !Number.isSafeInteger(item.sequence) ||
        Number(item.sequence) <= previous
      ) {
        return false;
      }
      previous = Number(item.sequence);
    }
    return true;
  };
  if (!areOrdered(value.observations) || !areOrdered(value.actions)) return null;
  events.sort((left, right) => left.sequence - right.sequence);
  if (events.some((event, index) => event.sequence !== index + 1)) return null;
  return events;
}

/** Return a validated immutable observation/action stream in sequence order. */
export function orderedCalibrationEvents(
  value: unknown,
): readonly CalibrationEventV1[] | null {
  if (!validateCalibrationSession(value)) return null;
  return collectOrderedCalibrationEvents(value);
}

/** Strict validation of one calibration journal, including offer/response references and limits. */
export function validateCalibrationSession(
  value: unknown,
): value is CalibrationSessionV1 {
  if (
    !isRecord(value) ||
    !hasExactKeys(
      value,
      [
        'schemaVersion',
        'calibrationId',
        'scope',
        'bankVersion',
        'selectorVersion',
        'seed',
        'presentationMode',
        'currentMovement',
        'observations',
        'actions',
        'status',
        'createdAt',
        'updatedAt',
      ],
      ['setup', 'completedAt', 'skip'],
    ) ||
    value.schemaVersion !== CALIBRATION_SCHEMA_VERSION ||
    !isBoundedText(value.calibrationId) ||
    !isScope(value.scope) ||
    !isBoundedText(value.bankVersion, 80) ||
    !isBoundedText(value.selectorVersion, 80) ||
    !Number.isSafeInteger(value.seed) ||
    Number(value.seed) < 0 ||
    Number(value.seed) > 0xffff_ffff ||
    !['visual', 'monochrome', 'text-equivalent'].includes(
      value.presentationMode as string,
    ) ||
    !isMovement(value.currentMovement) ||
    !Array.isArray(value.observations) ||
    value.observations.length > CALIBRATION_MAX_OBSERVATIONS ||
    !Array.isArray(value.actions) ||
    value.actions.length > CALIBRATION_MAX_OBSERVATIONS * 4 ||
    !value.actions.every(isObservationAction) ||
    !['in-progress', 'completed', 'skipped'].includes(value.status as string) ||
    !isDateTime(value.createdAt) ||
    !isDateTime(value.updatedAt) ||
    Date.parse(value.updatedAt) < Date.parse(value.createdAt) ||
    (value.setup !== undefined && !isSetup(value.setup)) ||
    (value.completedAt !== undefined && !isDateTime(value.completedAt)) ||
    (value.skip !== undefined && !isSkip(value.skip))
  ) {
    return false;
  }

  let serialized: string;
  try {
    serialized = JSON.stringify(value);
  } catch {
    return false;
  }
  if (serialized.length > CALIBRATION_MAX_SESSION_CHARS) return false;

  const orderedEvents = collectOrderedCalibrationEvents(value);
  if (orderedEvents === null) return false;

  const sessionTimes = {
    created: Date.parse(value.createdAt as string),
    updated: Date.parse(value.updatedAt as string),
  };
  const observationIds = new Set<string>();
  const trialIds = new Set<string>();
  const observationById = new Map<string, CalibrationObservationV1>();
  const actionIds = new Set<string>();
  const actionStateByObservation = new Map<string, 'retract' | 'restore'>();
  const activeChoiceCount = new Map<string, number>();
  const activeObservationIds = new Set<string>();
  const stimulusVersions = new Map<string, string>();
  let previousEventAt = sessionTimes.created;
  for (const event of orderedEvents) {
    const recordedAt = Date.parse(event.value.recordedAt);
    if (
      recordedAt < previousEventAt ||
      recordedAt > sessionTimes.updated ||
      recordedAt < sessionTimes.created
    ) {
      return false;
    }

    if (event.kind === 'observation') {
      const item = event.value;
      const priorChoices = new Set(
        [...activeChoiceCount]
          .filter(([, count]) => count > 0)
          .map(([stimulusId]) => stimulusId),
      );
      if (
        !validateObservation(item, priorChoices) ||
        observationIds.has(item.observationId) ||
        trialIds.has(item.trialId) ||
        Date.parse(item.presentedAt) < sessionTimes.created
      ) {
        return false;
      }
      observationIds.add(item.observationId);
      observationById.set(item.observationId, item);
      trialIds.add(item.trialId);
      activeObservationIds.add(item.observationId);
      for (const presentation of item.offered) {
        const previousVersion = stimulusVersions.get(presentation.stimulusId);
        if (previousVersion !== undefined && previousVersion !== presentation.stimulusVersion) {
          return false;
        }
        stimulusVersions.set(presentation.stimulusId, presentation.stimulusVersion);
      }
      if (item.response.kind === 'choose') {
        for (const stimulusId of item.response.chosenIds) {
          activeChoiceCount.set(stimulusId, (activeChoiceCount.get(stimulusId) ?? 0) + 1);
        }
      }
    } else {
      const action = event.value;
      const target = observationById.get(action.targetObservationId);
      const expectedAction = actionStateByObservation.get(action.targetObservationId) ?? 'retract';
      if (
        !target ||
        target.response.kind !== 'choose' ||
        actionIds.has(action.actionId) ||
        action.action !== expectedAction
      ) {
        return false;
      }
      actionIds.add(action.actionId);
      actionStateByObservation.set(
        action.targetObservationId,
        action.action === 'retract' ? 'restore' : 'retract',
      );
      if (action.action === 'retract') {
        activeObservationIds.delete(action.targetObservationId);
      } else {
        activeObservationIds.add(action.targetObservationId);
      }
      const adjustment = action.action === 'retract' ? -1 : 1;
      for (const stimulusId of target.response.chosenIds) {
        const count = (activeChoiceCount.get(stimulusId) ?? 0) + adjustment;
        if (count < 0) return false;
        activeChoiceCount.set(stimulusId, count);
      }
    }
    previousEventAt = recordedAt;
  }

  if (value.status === 'in-progress') {
    return value.completedAt === undefined && value.skip === undefined;
  }
  if (value.status === 'completed') {
    const answeredMovements = new Set<number>();
    for (const observationId of activeObservationIds) {
      const item = observationById.get(observationId);
      if (item) answeredMovements.add(item.movement);
    }
    return (
      value.completedAt !== undefined &&
      Date.parse(value.completedAt as string) >= sessionTimes.updated &&
      value.skip === undefined &&
      value.setup !== undefined &&
      value.currentMovement === 5 &&
      [1, 2, 3, 4].every((movement) => answeredMovements.has(movement))
    );
  }
  const skip = value.skip as CalibrationSkipV1;
  return (
    value.status === 'skipped' &&
    skip !== undefined &&
    value.completedAt === undefined &&
    skip.movement === value.currentMovement &&
    Date.parse(skip.skippedAt) >= sessionTimes.updated
  );
}
