import {
  canonicalizePuzzleDocumentV2,
  validatePuzzleDocumentV2,
  type PuzzleDocumentV2,
  type PuzzleV2Weekday,
} from './puzzleV2.js';

export const PUZZLE_V2_PUBLICATION_REVIEW_SCHEMA = 'puzzle-v2-publication-review-v1' as const;
export const PUZZLE_V2_PUBLICATION_GATE_VERSION = 'puzzle-v2-publication-gate-v1' as const;

const SHA256_PATTERN = /^sha256:[0-9a-f]{64}$/;
const RAW_SHA256_PATTERN = /^[0-9a-f]{64}$/;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const FOOTHOLD_TARGETS: Readonly<Record<PuzzleV2Weekday, number>> = {
  Monday: 12,
  Tuesday: 10,
  Wednesday: 8,
  Thursday: 6,
  Friday: 5,
  Saturday: 4,
  Sunday: 0,
};

export type PuzzleV2PublicationEvidenceKind =
  | 'source-artifact'
  | 'license-terms-review'
  | 'clue-semantic-review'
  | 'clue-editorial-review'
  | 'challenger-run'
  | 'crossing-certificate'
  | 'solve-simulation'
  | 'weekday-review'
  | 'mechanic-route';

export type PuzzleV2PublicationEvidenceRef = Readonly<{
  artifactId: string;
  sha256: string;
  kind: PuzzleV2PublicationEvidenceKind;
}>;

export type PuzzleV2PublicationSourceAttestation = Readonly<{
  sourceId: string;
  artifactSha256: string;
  spdx: string;
  decision: 'approved' | 'rejected' | 'unresolved';
  reviewerId: string;
  reviewedAt: string;
  evidenceRefs: readonly PuzzleV2PublicationEvidenceRef[];
}>;

export type PuzzleV2ClueAdjudication = Readonly<{
  clueVariantId: string;
  semanticDecision: 'pass' | 'fail' | 'unresolved';
  editorialDecision: 'pass' | 'fail' | 'unresolved';
  reviewerId: string;
  reviewedAt: string;
  evidenceRefs: readonly PuzzleV2PublicationEvidenceRef[];
  challenger: Readonly<{
    methodId: string;
    methodVersion: string;
    independentOfGenerator: boolean;
    answerHiddenDuringChallenge: boolean;
    decision: 'no-unresolved-alternative' | 'unresolved-alternative' | 'not-run';
    evidenceRefs: readonly PuzzleV2PublicationEvidenceRef[];
  }>;
}>;

export type PuzzleV2SupportAssignment = Readonly<{
  targetPosition: number;
  supportEntryId: string;
}>;

export type PuzzleV2CrossingCertificate = Readonly<{
  targetEntryId: string;
  /** Layer zero is an independently reviewed opening foothold; parents must be in lower layers. */
  supportLayer: number;
  targetClass: 'ordinary' | 'difficult-noninferable';
  routeOutcome: 'retrieval' | 'recognition' | 'exposure' | 'prepared-hint' | 'unresolved';
  targetExcludedFromSupportSearch: boolean;
  supportAssignments: readonly PuzzleV2SupportAssignment[];
  topologyConstraint?: Readonly<{
    rationale: string;
    evidenceRefs: readonly PuzzleV2PublicationEvidenceRef[];
  }>;
  unresolvedDualObscurityCells: number;
  reviewerId: string;
  reviewedAt: string;
  evidenceRefs: readonly PuzzleV2PublicationEvidenceRef[];
}>;

export type PuzzleV2SolveSimulationReceipt = Readonly<{
  simulatorId: string;
  simulatorVersion: string;
  policyId: string;
  policyVersion: string;
  seed: string;
  trajectoryCount: number;
  completionRate: number;
  maxNonAnswerNudges: number;
  directAnswerReveals: number;
  decision: 'pass' | 'fail' | 'unresolved';
  evidenceRefs: readonly PuzzleV2PublicationEvidenceRef[];
}>;

export type PuzzleV2CrossingReview = Readonly<{
  candidateDigest: string;
  evaluatorId: string;
  evaluatorVersion: string;
  allEntriesReviewed: boolean;
  unresolvedDualObscurityCells: number;
  certificates: readonly PuzzleV2CrossingCertificate[];
  simulation: PuzzleV2SolveSimulationReceipt;
}>;

export type PuzzleV2BlindWeekdayReview = Readonly<{
  reviewerId: string;
  classifiedWeekday: PuzzleV2Weekday;
  rationale: PuzzleV2PublicationEvidenceRef;
}>;

export type PuzzleV2MechanicRouteReview = Readonly<{
  mechanicId: string;
  affectedEntryIds: readonly string[];
  independentRouteCount: number;
  discoverable: boolean;
  evidenceRefs: readonly PuzzleV2PublicationEvidenceRef[];
}>;

export type PuzzleV2WeekdayReview = Readonly<{
  candidateDigest: string;
  recipeId: string;
  recipeVersion: string;
  weekday: PuzzleV2Weekday;
  decision: 'pass' | 'fail' | 'unresolved';
  ordinaryFootholdEntryIds: readonly string[];
  blindClassifications: readonly PuzzleV2BlindWeekdayReview[];
  mechanicRoute?: PuzzleV2MechanicRouteReview;
  reviewerId: string;
  reviewedAt: string;
  evidenceRefs: readonly PuzzleV2PublicationEvidenceRef[];
}>;

/**
 * Immutable review input for a later host publication transaction. This packet
 * is evidence metadata, not a signature, publication receipt, or playable flag.
 */
export type PuzzleV2PublicationReviewPacketV1 = Readonly<{
  schema: typeof PUZZLE_V2_PUBLICATION_REVIEW_SCHEMA;
  reviewId: string;
  candidateDigest: string;
  createdAt: string;
  sourceAttestations: readonly PuzzleV2PublicationSourceAttestation[];
  clueAdjudications: readonly PuzzleV2ClueAdjudication[];
  crossingReview: PuzzleV2CrossingReview;
  weekdayReview: PuzzleV2WeekdayReview;
  packetDigest: string;
}>;

export type PuzzleV2PublicationGateReasonCode =
  | 'candidate-invalid'
  | 'candidate-rejected-by-quality'
  | 'packet-missing-or-invalid'
  | 'packet-digest-invalid'
  | 'candidate-digest-mismatch'
  | 'candidate-has-synthetic-source'
  | 'source-attestation-missing'
  | 'source-attestation-invalid'
  | 'clue-adjudication-missing'
  | 'clue-adjudication-failed'
  | 'challenger-evidence-missing'
  | 'challenger-review-failed'
  | 'crossing-certificates-missing'
  | 'crossing-certificate-failed'
  | 'crossing-certificate-non-layered'
  | 'simulation-evidence-missing'
  | 'simulation-gate-failed'
  | 'weekday-evidence-missing'
  | 'weekday-recipe-mismatch'
  | 'weekday-foothold-target-missed'
  | 'weekday-quadrant-evidence-missing'
  | 'weekday-quadrant-foothold-target-missed'
  | 'weekday-classification-failed'
  | 'weekday-mechanic-route-missing'
  | 'reviewer-evidence-unverified'
  | 'unsupported-sunday-size';

export type PuzzleV2PublicationGateReason = Readonly<{
  code: PuzzleV2PublicationGateReasonCode;
  path: string;
  message: string;
}>;

export type PuzzleV2PublicationGateEvaluation = Readonly<{
  gateVersion: typeof PUZZLE_V2_PUBLICATION_GATE_VERSION;
  candidateDigest: string | null;
  status: 'blocked' | 'evidence-unverified';
  reasons: readonly PuzzleV2PublicationGateReason[];
}>;

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: unknown, required: readonly string[], optional: readonly string[] = []): value is UnknownRecord {
  if (!isRecord(value)) return false;
  const allowed = new Set([...required, ...optional]);
  const keys = Object.keys(value);
  const prototype = Object.getPrototypeOf(value);
  return (prototype === Object.prototype || prototype === null) &&
    required.every((key) => Object.hasOwn(value, key) && keys.includes(key)) &&
    keys.every((key) => allowed.has(key)) &&
    optional.every((key) => !(key in value) || Object.hasOwn(value, key));
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isDate(value: unknown): value is string {
  if (typeof value !== 'string' || !DATE_PATTERN.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function isUniqueNonEmptyStrings(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.every(isNonEmptyString) && new Set(value).size === value.length;
}

function addReason(
  reasons: PuzzleV2PublicationGateReason[],
  code: PuzzleV2PublicationGateReasonCode,
  path: string,
  message: string,
): void {
  if (!reasons.some((reason) => reason.code === code && reason.path === path)) reasons.push({ code, path, message });
}

function refsHaveKinds(value: unknown, kinds: readonly PuzzleV2PublicationEvidenceKind[]): value is readonly PuzzleV2PublicationEvidenceRef[] {
  return Array.isArray(value) && value.length > 0 && value.every((raw) =>
    hasExactKeys(raw, ['artifactId', 'sha256', 'kind']) &&
    isNonEmptyString(raw.artifactId) && RAW_SHA256_PATTERN.test(String(raw.sha256)) &&
    kinds.includes(raw.kind as PuzzleV2PublicationEvidenceKind),
  ) && new Set(value.map((raw) => (raw as UnknownRecord).artifactId)).size === value.length;
}

function refsHaveAllKinds(value: unknown, kinds: readonly PuzzleV2PublicationEvidenceKind[]): value is readonly PuzzleV2PublicationEvidenceRef[] {
  return refsHaveKinds(value, kinds) && kinds.every((kind) => value.some((ref) => ref.kind === kind));
}

function validateSourceAttestations(
  candidate: PuzzleDocumentV2,
  rawPacket: UnknownRecord,
  reasons: PuzzleV2PublicationGateReason[],
): void {
  const sources = candidate.provenance.sources;
  if (sources.some((source) => source.contentClass !== 'public')) {
    addReason(reasons, 'candidate-has-synthetic-source', 'candidate.provenance.sources', 'Publication requires public, explicitly admitted source artifacts.');
  }
  const rawAttestations = rawPacket.sourceAttestations;
  if (!Array.isArray(rawAttestations) || rawAttestations.length === 0) {
    addReason(reasons, 'source-attestation-missing', 'sourceAttestations', 'Every pinned source needs a separate license and terms attestation.');
    return;
  }
  const seen = new Set<string>();
  for (const [index, raw] of rawAttestations.entries()) {
    const path = `sourceAttestations[${index}]`;
    if (!hasExactKeys(raw, ['sourceId', 'artifactSha256', 'spdx', 'decision', 'reviewerId', 'reviewedAt', 'evidenceRefs']) ||
      !isNonEmptyString(raw.sourceId) || !RAW_SHA256_PATTERN.test(String(raw.artifactSha256)) || !isNonEmptyString(raw.spdx) ||
      !['approved', 'rejected', 'unresolved'].includes(String(raw.decision)) || !isNonEmptyString(raw.reviewerId) || !isDate(raw.reviewedAt) ||
      !refsHaveAllKinds(raw.evidenceRefs, ['source-artifact', 'license-terms-review'])) {
      addReason(reasons, 'source-attestation-invalid', path, 'Source attestation must bind the exact artifact and license/terms decision to review evidence.');
      continue;
    }
    const source = sources.find((item) => item.sourceId === raw.sourceId);
    const sourceArtifactRef = raw.evidenceRefs.find((reference) => reference.kind === 'source-artifact');
    if (!source || source.contentClass !== 'public' || source.artifactSha256 !== raw.artifactSha256 || sourceArtifactRef?.sha256 !== raw.artifactSha256 || source.spdx !== raw.spdx || raw.decision !== 'approved' || seen.has(raw.sourceId)) {
      addReason(reasons, 'source-attestation-invalid', path, 'Source attestation must approve one exact public source pin without duplicates.');
    }
    seen.add(raw.sourceId);
  }
  if (seen.size !== sources.length || sources.some((source) => !seen.has(source.sourceId))) {
    addReason(reasons, 'source-attestation-missing', 'sourceAttestations', 'Source attestations must cover each candidate source exactly once.');
  }
}

function validateClueAdjudications(
  candidate: PuzzleDocumentV2,
  rawPacket: UnknownRecord,
  reasons: PuzzleV2PublicationGateReason[],
): void {
  const rawReviews = rawPacket.clueAdjudications;
  if (!Array.isArray(rawReviews) || rawReviews.length === 0) {
    addReason(reasons, 'clue-adjudication-missing', 'clueAdjudications', 'Every exact clue variant needs semantic and editorial adjudication.');
    addReason(reasons, 'challenger-evidence-missing', 'clueAdjudications', 'Every clue needs an independent answer-blind alternative-answer challenge.');
    return;
  }
  const seen = new Set<string>();
  for (const [index, raw] of rawReviews.entries()) {
    const path = `clueAdjudications[${index}]`;
    if (!hasExactKeys(raw, ['clueVariantId', 'semanticDecision', 'editorialDecision', 'reviewerId', 'reviewedAt', 'evidenceRefs', 'challenger']) ||
      !isNonEmptyString(raw.clueVariantId) || !['pass', 'fail', 'unresolved'].includes(String(raw.semanticDecision)) ||
      !['pass', 'fail', 'unresolved'].includes(String(raw.editorialDecision)) || !isNonEmptyString(raw.reviewerId) || !isDate(raw.reviewedAt) ||
      !refsHaveAllKinds(raw.evidenceRefs, ['clue-semantic-review', 'clue-editorial-review'])) {
      addReason(reasons, 'clue-adjudication-failed', path, 'Clue review must contain exact semantic and editorial outcomes with evidence.');
      continue;
    }
    const clue = candidate.clues.find((item) => item.clueVariantId === raw.clueVariantId);
    if (!clue || seen.has(raw.clueVariantId) || raw.semanticDecision !== 'pass' || raw.editorialDecision !== 'pass') {
      addReason(reasons, 'clue-adjudication-failed', path, 'Clue adjudication must pass for one exact candidate clue variant.');
    }
    seen.add(raw.clueVariantId);

    const challenger = raw.challenger;
    if (!hasExactKeys(challenger, ['methodId', 'methodVersion', 'independentOfGenerator', 'answerHiddenDuringChallenge', 'decision', 'evidenceRefs']) ||
      !isNonEmptyString(challenger.methodId) || !isNonEmptyString(challenger.methodVersion) ||
      challenger.independentOfGenerator !== true || challenger.answerHiddenDuringChallenge !== true ||
      challenger.decision !== 'no-unresolved-alternative' || !refsHaveKinds(challenger.evidenceRefs, ['challenger-run'])) {
      addReason(reasons, 'challenger-review-failed', `${path}.challenger`, 'The independent challenger must test the clue without seeing the answer and resolve alternatives.');
    }
  }
  if (seen.size !== candidate.clues.length || candidate.clues.some((clue) => !seen.has(clue.clueVariantId))) {
    addReason(reasons, 'clue-adjudication-missing', 'clueAdjudications', 'Clue adjudications must cover every candidate clue variant exactly once.');
  }
  if (reasons.some((reason) => reason.code === 'challenger-review-failed')) {
    addReason(reasons, 'challenger-evidence-missing', 'clueAdjudications', 'At least one clue lacks a passing independent challenger record.');
  }
}

function validateCrossingReview(
  candidate: PuzzleDocumentV2,
  rawPacket: UnknownRecord,
  reasons: PuzzleV2PublicationGateReason[],
): ReadonlySet<string> | null {
  const rawReview = rawPacket.crossingReview;
  if (!hasExactKeys(rawReview, ['candidateDigest', 'evaluatorId', 'evaluatorVersion', 'allEntriesReviewed', 'unresolvedDualObscurityCells', 'certificates', 'simulation'])) {
    addReason(reasons, 'crossing-certificates-missing', 'crossingReview', 'A versioned crossing review with a certificate for every entry is required.');
    addReason(reasons, 'simulation-evidence-missing', 'crossingReview.simulation', 'A seeded route simulation is required.');
    return null;
  }
  if (rawReview.candidateDigest !== candidate.integrity.value || !isNonEmptyString(rawReview.evaluatorId) || !isNonEmptyString(rawReview.evaluatorVersion) ||
    rawReview.allEntriesReviewed !== true || !Number.isInteger(rawReview.unresolvedDualObscurityCells) || rawReview.unresolvedDualObscurityCells !== 0 ||
    !Array.isArray(rawReview.certificates)) {
    addReason(reasons, 'crossing-certificate-failed', 'crossingReview', 'Crossing review must be bound to this candidate, cover all entries, and resolve every dual-obscurity crossing.');
  }

  const rawCertificates = Array.isArray(rawReview.certificates) ? rawReview.certificates : [];
  const seen = new Set<string>();
  const layerByEntry = new Map<string, number>();
  const layeredCertificates: Array<{
    targetEntryId: string;
    supportLayer: number;
    routeOutcome: string;
    targetExcludedFromSupportSearch: boolean;
    supportAssignments: readonly unknown[];
  }> = [];
  for (const [index, raw] of rawCertificates.entries()) {
    const path = `crossingReview.certificates[${index}]`;
    if (!hasExactKeys(raw, ['targetEntryId', 'supportLayer', 'targetClass', 'routeOutcome', 'targetExcludedFromSupportSearch', 'supportAssignments', 'unresolvedDualObscurityCells', 'reviewerId', 'reviewedAt', 'evidenceRefs'], ['topologyConstraint']) ||
      !isNonEmptyString(raw.targetEntryId) || !['ordinary', 'difficult-noninferable'].includes(String(raw.targetClass)) ||
      !['retrieval', 'recognition', 'exposure', 'prepared-hint', 'unresolved'].includes(String(raw.routeOutcome)) ||
      !Number.isInteger(raw.supportLayer) || Number(raw.supportLayer) < 0 || Number(raw.supportLayer) > candidate.entries.length ||
      typeof raw.targetExcludedFromSupportSearch !== 'boolean' || !Array.isArray(raw.supportAssignments) ||
      !Number.isInteger(raw.unresolvedDualObscurityCells) || !isNonEmptyString(raw.reviewerId) || !isDate(raw.reviewedAt) ||
      !refsHaveKinds(raw.evidenceRefs, ['crossing-certificate'])) {
      addReason(reasons, 'crossing-certificate-failed', path, 'Support certificate is malformed or lacks versioned review evidence.');
      continue;
    }
    const target = candidate.entries.find((entry) => entry.id === raw.targetEntryId);
    if (target) {
      layerByEntry.set(target.id, Number(raw.supportLayer));
      layeredCertificates.push({
        targetEntryId: target.id,
        supportLayer: Number(raw.supportLayer),
        routeOutcome: String(raw.routeOutcome),
        targetExcludedFromSupportSearch: raw.targetExcludedFromSupportSearch,
        supportAssignments: raw.supportAssignments,
      });
    }
    let assignmentsValid = true;
    const positions = new Set<number>();
    const supportingEntries = new Set<string>();
    for (const assignment of raw.supportAssignments) {
      if (!hasExactKeys(assignment, ['targetPosition', 'supportEntryId']) || !Number.isInteger(assignment.targetPosition) ||
        Number(assignment.targetPosition) < 1 || !isNonEmptyString(assignment.supportEntryId) || assignment.supportEntryId === raw.targetEntryId ||
        !candidate.entries.some((entry) => entry.id === assignment.supportEntryId) || positions.has(Number(assignment.targetPosition))) {
        assignmentsValid = false;
        continue;
      }
      const supportEntry = candidate.entries.find((entry) => entry.id === assignment.supportEntryId);
      const targetCellId = target?.cellIds[Number(assignment.targetPosition) - 1];
      if (!supportEntry || !targetCellId || !supportEntry.cellIds.includes(targetCellId) || supportEntry.direction === target?.direction) {
        assignmentsValid = false;
      }
      positions.add(Number(assignment.targetPosition));
      supportingEntries.add(String(assignment.supportEntryId));
    }
    if (!target || raw.unresolvedDualObscurityCells !== 0 || raw.routeOutcome === 'unresolved' || seen.has(raw.targetEntryId) || !assignmentsValid ||
      (target && [...positions].some((position) => position > target.answer.length))) {
      addReason(reasons, 'crossing-certificate-failed', path, 'Certificate must describe a resolved route over valid cells/entries with no unresolved dual-obscurity crossing.');
    }
    if (raw.targetClass === 'difficult-noninferable' &&
      (raw.targetExcludedFromSupportSearch !== true || supportingEntries.size === 0 || positions.size < 1 || Number(raw.supportLayer) === 0)) {
      addReason(reasons, 'crossing-certificate-failed', path, 'A difficult target needs a non-circular, evidenced crossing route.');
    }
    if (raw.targetClass === 'difficult-noninferable' && supportingEntries.size < 2) {
      const exception = raw.topologyConstraint;
      if (supportingEntries.size !== 1 || !hasExactKeys(exception, ['rationale', 'evidenceRefs']) || !isNonEmptyString(exception.rationale) ||
        !refsHaveKinds(exception.evidenceRefs, ['crossing-certificate'])) {
        addReason(reasons, 'crossing-certificate-failed', path, 'A difficult target needs two independently reachable support entries unless topology limitations are individually evidenced.');
      }
    }
    seen.add(raw.targetEntryId);
  }
  if (seen.size !== candidate.entries.length || candidate.entries.some((entry) => !seen.has(entry.id))) {
    addReason(reasons, 'crossing-certificates-missing', 'crossingReview.certificates', 'Crossing certificates must cover every entry exactly once.');
  }
  for (const certificate of layeredCertificates) {
    const path = `crossingReview.certificates.${certificate.targetEntryId}`;
    const layer = certificate.supportLayer;
    if (certificate.targetExcludedFromSupportSearch !== true ||
      (layer === 0 && certificate.supportAssignments.length > 0) ||
      (layer === 0 && !['retrieval', 'recognition'].includes(certificate.routeOutcome)) ||
      (layer > 0 && certificate.supportAssignments.length === 0)) {
      addReason(reasons, 'crossing-certificate-non-layered', path, 'Every route must exclude its target; only unassisted retrieval/recognition entries may be layer-zero footholds, and later layers need parents.');
    }
    for (const assignment of certificate.supportAssignments) {
      if (!isRecord(assignment) || typeof assignment.supportEntryId !== 'string') continue;
      const parentLayer = layerByEntry.get(assignment.supportEntryId);
      if (parentLayer === undefined || parentLayer >= layer) {
        addReason(reasons, 'crossing-certificate-non-layered', path, 'Every support edge must point strictly to a lower, independently reachable layer; same-layer and cyclic support is forbidden.');
      }
    }
  }

  const simulation = rawReview.simulation;
  if (!hasExactKeys(simulation, ['simulatorId', 'simulatorVersion', 'policyId', 'policyVersion', 'seed', 'trajectoryCount', 'completionRate', 'maxNonAnswerNudges', 'directAnswerReveals', 'decision', 'evidenceRefs']) ||
    !isNonEmptyString(simulation.simulatorId) || !isNonEmptyString(simulation.simulatorVersion) || !isNonEmptyString(simulation.policyId) ||
    !isNonEmptyString(simulation.policyVersion) || !isNonEmptyString(simulation.seed) || !Number.isInteger(simulation.trajectoryCount) ||
    Number(simulation.trajectoryCount) < 64 || typeof simulation.completionRate !== 'number' || !Number.isFinite(simulation.completionRate) ||
    simulation.completionRate < 0 || simulation.completionRate > 1 || !Number.isInteger(simulation.maxNonAnswerNudges) ||
    Number(simulation.maxNonAnswerNudges) < 0 || !Number.isInteger(simulation.directAnswerReveals) || Number(simulation.directAnswerReveals) !== 0 ||
    !['pass', 'fail', 'unresolved'].includes(String(simulation.decision)) || !refsHaveKinds(simulation.evidenceRefs, ['solve-simulation'])) {
    addReason(reasons, 'simulation-evidence-missing', 'crossingReview.simulation', 'Simulation must be seeded, versioned, evidenced, use at least 64 trajectories, and contain no direct answer reveals.');
  } else {
    if (simulation.decision !== 'pass') addReason(reasons, 'simulation-gate-failed', 'crossingReview.simulation.decision', 'The route simulation did not pass its versioned policy.');
    if (candidate.receipt.recipe.weekday === 'Monday' && (Number(simulation.completionRate) < 0.9 || Number(simulation.maxNonAnswerNudges) > 3)) {
      addReason(reasons, 'simulation-gate-failed', 'crossingReview.simulation', 'Monday screening requires at least 90% completion with no more than three non-answer nudges.');
    }
  }
  return new Set(layeredCertificates.filter((certificate) => certificate.supportLayer === 0).map((certificate) => certificate.targetEntryId));
}

function validateWeekdayReview(
  candidate: PuzzleDocumentV2,
  rawPacket: UnknownRecord,
  rootFootholds: ReadonlySet<string> | null,
  reasons: PuzzleV2PublicationGateReason[],
): void {
  const rawReview = rawPacket.weekdayReview;
  if (!hasExactKeys(rawReview, ['candidateDigest', 'recipeId', 'recipeVersion', 'weekday', 'decision', 'ordinaryFootholdEntryIds', 'blindClassifications', 'reviewerId', 'reviewedAt', 'evidenceRefs'], ['mechanicRoute'])) {
    addReason(reasons, 'weekday-evidence-missing', 'weekdayReview', 'Weekday recipe and blind day-classification evidence are required.');
    return;
  }
  const recipe = candidate.receipt.recipe;
  if (rawReview.candidateDigest !== candidate.integrity.value || rawReview.recipeId !== recipe.id || rawReview.recipeVersion !== recipe.version || rawReview.weekday !== recipe.weekday) {
    addReason(reasons, 'weekday-recipe-mismatch', 'weekdayReview', 'Weekday evidence must bind the exact recipe and candidate receipt.');
  }
  if (recipe.weekday === 'Sunday') addReason(reasons, 'unsupported-sunday-size', 'receipt.recipe.weekday', 'A 15×15 PuzzleDocumentV2 cannot be published as Sunday; the plan requires a separately gated 21×21 format.');
  const ordinaryFootholdEntryIds = isUniqueNonEmptyStrings(rawReview.ordinaryFootholdEntryIds)
    ? rawReview.ordinaryFootholdEntryIds
    : null;
  const footholdIdsValid = ordinaryFootholdEntryIds !== null &&
    ordinaryFootholdEntryIds.every((entryId) => candidate.entries.some((entry) => entry.id === entryId));
  const footholdsMatchLayers = ordinaryFootholdEntryIds !== null && rootFootholds !== null &&
    ordinaryFootholdEntryIds.length === rootFootholds.size &&
    ordinaryFootholdEntryIds.every((entryId) => rootFootholds.has(entryId));
  if (!['pass', 'fail', 'unresolved'].includes(String(rawReview.decision)) || rawReview.decision !== 'pass' ||
    !footholdIdsValid || ordinaryFootholdEntryIds === null || ordinaryFootholdEntryIds.length < FOOTHOLD_TARGETS[recipe.weekday] || !footholdsMatchLayers ||
    !isNonEmptyString(rawReview.reviewerId) || !isDate(rawReview.reviewedAt) || !refsHaveKinds(rawReview.evidenceRefs, ['weekday-review'])) {
    addReason(reasons, 'weekday-foothold-target-missed', 'weekdayReview', 'Weekday editorial review must pass, match the independently reachable layer-zero footholds, and meet the recipe target.');
  }
  if (recipe.weekday === 'Monday') {
    if (rootFootholds === null) {
      addReason(reasons, 'weekday-quadrant-evidence-missing', 'crossingReview.certificates', 'Monday quadrant evidence requires complete, layered entry certificates.');
    } else {
      const quadrants = ['northwest', 'northeast', 'southwest', 'southeast'] as const;
      const slots: Record<(typeof quadrants)[number], number> = { northwest: 0, northeast: 0, southwest: 0, southeast: 0 };
      const footholds: Record<(typeof quadrants)[number], number> = { northwest: 0, northeast: 0, southwest: 0, southeast: 0 };
      const cellById = new Map(candidate.cells.map((cell) => [cell.id, cell]));
      let quadrantEvidenceComplete = true;
      for (const entry of candidate.entries) {
        const start = cellById.get(entry.cellIds[0] ?? '');
        if (!start) {
          quadrantEvidenceComplete = false;
          continue;
        }
        // Use the numbered entry's start cell, so one long answer cannot masquerade as footholds in multiple regions.
        const quadrant = `${start.row < 7.5 ? 'north' : 'south'}${start.column < 7.5 ? 'west' : 'east'}` as (typeof quadrants)[number];
        slots[quadrant] += 1;
        if (rootFootholds.has(entry.id)) footholds[quadrant] += 1;
      }
      if (!quadrantEvidenceComplete) {
        addReason(reasons, 'weekday-quadrant-evidence-missing', 'candidate.entries', 'Every entry needs a valid numbered start cell to verify quadrant foothold coverage.');
      } else {
        for (const quadrant of quadrants) {
          const required = Math.min(2, slots[quadrant]);
          if (footholds[quadrant] < required) {
            addReason(reasons, 'weekday-quadrant-foothold-target-missed', `weekdayReview.quadrants.${quadrant}`, `Monday needs ${required} layer-zero foothold(s) in ${quadrant} when that region has enough entry slots.`);
          }
        }
      }
    }
  }
  const classifications = rawReview.blindClassifications;
  if (!Array.isArray(classifications) || classifications.length < 2) {
    addReason(reasons, 'weekday-classification-failed', 'weekdayReview.blindClassifications', 'At least two independent blind day classifications are required.');
  } else {
    const reviewerIds = new Set<string>();
    for (const [index, raw] of classifications.entries()) {
      if (!hasExactKeys(raw, ['reviewerId', 'classifiedWeekday', 'rationale']) || !isNonEmptyString(raw.reviewerId) ||
        !isNonEmptyString(raw.classifiedWeekday) || !hasExactKeys(raw.rationale, ['artifactId', 'sha256', 'kind']) ||
        !isNonEmptyString(raw.rationale.artifactId) || !RAW_SHA256_PATTERN.test(String(raw.rationale.sha256)) || raw.rationale.kind !== 'weekday-review') {
        addReason(reasons, 'weekday-classification-failed', `weekdayReview.blindClassifications[${index}]`, 'Blind classification must include a reviewer, day label, and hashed rationale artifact.');
        continue;
      }
      if (reviewerIds.has(raw.reviewerId) || raw.classifiedWeekday !== recipe.weekday) {
        addReason(reasons, 'weekday-classification-failed', `weekdayReview.blindClassifications[${index}]`, 'Blind reviewers must be distinct and identify the requested day.');
      }
      reviewerIds.add(raw.reviewerId);
    }
  }
  if (recipe.weekday === 'Thursday') {
    const route = rawReview.mechanicRoute;
    const mechanic = isRecord(route) ? candidate.mechanics.find((item) => item.id === route.mechanicId) : undefined;
    if (!hasExactKeys(route, ['mechanicId', 'affectedEntryIds', 'independentRouteCount', 'discoverable', 'evidenceRefs']) ||
      !isNonEmptyString(route.mechanicId) || !isUniqueNonEmptyStrings(route.affectedEntryIds) || route.affectedEntryIds.length < 2 ||
      !route.affectedEntryIds.every((entryId) => candidate.entries.some((entry) => entry.id === entryId)) ||
      !mechanic || route.affectedEntryIds.length !== mechanic.affectedEntryIds.length ||
      !route.affectedEntryIds.every((entryId) => mechanic.affectedEntryIds.includes(entryId)) ||
      !Number.isInteger(route.independentRouteCount) || Number(route.independentRouteCount) < 2 || route.discoverable !== true ||
      !refsHaveKinds(route.evidenceRefs, ['mechanic-route'])) {
      addReason(reasons, 'weekday-mechanic-route-missing', 'weekdayReview.mechanicRoute', 'Thursday requires one coherent, discoverable mechanic with at least two independent routes and evidence.');
    }
  }
}

async function digestPacket(packet: Omit<PuzzleV2PublicationReviewPacketV1, 'packetDigest'>): Promise<string> {
  const cryptoApi = globalThis.crypto;
  if (!cryptoApi?.subtle) throw new Error('Web Crypto SHA-256 is unavailable');
  const bytes = new TextEncoder().encode(canonicalizePuzzleDocumentV2(packet));
  const digest = await cryptoApi.subtle.digest('SHA-256', bytes);
  return `sha256:${[...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}

/** Seal a typed review packet; the digest detects edits but does not authenticate its author. */
export async function sealPuzzleV2PublicationReviewPacket(
  packet: Omit<PuzzleV2PublicationReviewPacketV1, 'packetDigest'>,
): Promise<PuzzleV2PublicationReviewPacketV1> {
  return { ...packet, packetDigest: await digestPacket(packet) };
}

/**
 * Pure, fail-closed assessment of review evidence. This slice has no trusted
 * reviewer/evidence verifier, so the evaluator returns only blocked or
 * evidence-unverified; it never grants transaction eligibility or publishes a
 * playable candidate.
 */
export async function evaluatePuzzleV2PublicationGate(
  candidateValue: unknown,
  packetValue: unknown,
): Promise<PuzzleV2PublicationGateEvaluation> {
  const reasons: PuzzleV2PublicationGateReason[] = [];
  const candidateValidation = await validatePuzzleDocumentV2(candidateValue);
  if (!candidateValidation.valid) {
    addReason(reasons, 'candidate-invalid', 'candidate', 'Candidate must pass the complete V2 structural and integrity validator before publication review.');
  }
  const candidate = candidateValidation.valid ? candidateValue as PuzzleDocumentV2 : null;
  if (candidate?.quality.verdict === 'reject') {
    addReason(reasons, 'candidate-rejected-by-quality', 'candidate.quality.verdict', 'A rejected candidate cannot advance to publication, regardless of attached review evidence.');
  }
  const candidateDigest = candidate?.integrity.value ?? (isRecord(candidateValue) && isRecord(candidateValue.integrity) && typeof candidateValue.integrity.value === 'string' ? candidateValue.integrity.value : null);
  if (!candidate) {
    addReason(reasons, 'packet-missing-or-invalid', 'packet', 'A complete immutable publication-review packet is required.');
    return { gateVersion: PUZZLE_V2_PUBLICATION_GATE_VERSION, candidateDigest, status: 'blocked', reasons };
  }

  const rawPacket: UnknownRecord = isRecord(packetValue) ? packetValue : {};
  if (!isRecord(packetValue)) addReason(reasons, 'packet-missing-or-invalid', 'packet', 'A complete immutable publication-review packet is required.');

  const packetKeys = ['schema', 'reviewId', 'candidateDigest', 'createdAt', 'sourceAttestations', 'clueAdjudications', 'crossingReview', 'weekdayReview', 'packetDigest'];
  if (!hasExactKeys(rawPacket, packetKeys) || rawPacket.schema !== PUZZLE_V2_PUBLICATION_REVIEW_SCHEMA || !isNonEmptyString(rawPacket.reviewId) ||
    !isDate(rawPacket.createdAt) || !SHA256_PATTERN.test(String(rawPacket.candidateDigest)) || !SHA256_PATTERN.test(String(rawPacket.packetDigest))) {
    addReason(reasons, 'packet-missing-or-invalid', 'packet', 'Review packet shape, identity, date, schema, or digest is invalid.');
  }
  if (rawPacket.candidateDigest !== candidate.integrity.value) {
    addReason(reasons, 'candidate-digest-mismatch', 'packet.candidateDigest', 'Review evidence must name this exact immutable candidate digest.');
  }
  if (typeof rawPacket.packetDigest === 'string') {
    try {
      const { packetDigest: _packetDigest, ...packetWithoutDigest } = rawPacket as UnknownRecord & { packetDigest?: unknown };
      const expected = await digestPacket(packetWithoutDigest as Omit<PuzzleV2PublicationReviewPacketV1, 'packetDigest'>);
      if (rawPacket.packetDigest !== expected) addReason(reasons, 'packet-digest-invalid', 'packet.packetDigest', 'Review packet content does not match its immutable SHA-256 digest.');
    } catch {
      addReason(reasons, 'packet-digest-invalid', 'packet.packetDigest', 'Review packet digest could not be verified.');
    }
  } else {
    addReason(reasons, 'packet-digest-invalid', 'packet.packetDigest', 'Review packet digest is missing.');
  }

  validateSourceAttestations(candidate, rawPacket, reasons);
  validateClueAdjudications(candidate, rawPacket, reasons);
  const rootFootholds = validateCrossingReview(candidate, rawPacket, reasons);
  validateWeekdayReview(candidate, rawPacket, rootFootholds, reasons);

  addReason(reasons, 'reviewer-evidence-unverified', 'publicationReview', 'Reviewer IDs, decisions, and artifact hashes are untrusted claims because no trusted host verifier is implemented yet.');

  return {
    gateVersion: PUZZLE_V2_PUBLICATION_GATE_VERSION,
    candidateDigest,
    status: reasons.every((reason) => reason.code === 'reviewer-evidence-unverified') ? 'evidence-unverified' : 'blocked',
    reasons,
  };
}
