/**
 * Bounded postgame evaluation, deliberately separate from preference and
 * knowledge evidence. The player is reporting how this particular game felt;
 * the reducer must never turn it into a personality or mastery claim.
 */

export const PLAYTEST_PULSE_VERSION = 1 as const;

export const PLAYTEST_WORTH_VALUES = [
  'yes',
  'maybe',
  'no',
] as const;
export type PlaytestWorthV1 = (typeof PLAYTEST_WORTH_VALUES)[number];

export const PLAYTEST_RETURN_VALUES = [
  'another-like-this',
  'same-world-new-angle',
  'more-footholds',
  'harder-stretch',
  'let-it-rest',
] as const;
export type PlaytestReturnIntentV1 = (typeof PLAYTEST_RETURN_VALUES)[number];

export const PLAYTEST_ROUGH_EDGE_VALUES = [
  'none',
  'too-opaque',
  'too-obscure',
  'too-easy',
  'crossings-unhelpful',
] as const;
export type PlaytestRoughEdgeV1 = (typeof PLAYTEST_ROUGH_EDGE_VALUES)[number];

export type PlaytestPulseV1 = Readonly<{
  schemaVersion: typeof PLAYTEST_PULSE_VERSION;
  pulseId: string;
  sessionId: string;
  recordedAt: string;
  worth: PlaytestWorthV1;
  returnIntent: PlaytestReturnIntentV1;
  roughEdge: PlaytestRoughEdgeV1;
}>;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Runtime validation for the host/UI boundary. */
export function validatePlaytestPulse(value: unknown): value is PlaytestPulseV1 {
  if (!isRecord(value)) return false;
  const keys = Object.keys(value).sort().join(',');
  if (keys !== 'pulseId,recordedAt,returnIntent,roughEdge,schemaVersion,sessionId,worth') return false;
  return value.schemaVersion === PLAYTEST_PULSE_VERSION &&
    typeof value.pulseId === 'string' && UUID.test(value.pulseId) &&
    typeof value.sessionId === 'string' && UUID.test(value.sessionId) &&
    typeof value.recordedAt === 'string' && ISO.test(value.recordedAt) && Number.isFinite(Date.parse(value.recordedAt)) &&
    (PLAYTEST_WORTH_VALUES as readonly string[]).includes(value.worth as string) &&
    (PLAYTEST_RETURN_VALUES as readonly string[]).includes(value.returnIntent as string) &&
    (PLAYTEST_ROUGH_EDGE_VALUES as readonly string[]).includes(value.roughEdge as string);
}
