import { describe, expect, it } from 'vitest';
import type { CellId, EntryId } from './puzzle';
import {
  applyEpistemeUpdate,
  canonicalEpistemeUpdateHashInput,
  createEpistemeProfile,
  projectEpistemeProfile,
  stableEpistemeStringify,
  validateEpistemeEvidence
} from './episteme';
import type {
  AssociationProposalEvidenceV1,
  CalibrationAssociationProposalEvidenceV1,
  EpistemeEvidenceV1,
  EpistemeUpdateCommandV1,
  ExplicitPreferenceEvidenceV1,
  KnowledgeTaskV1,
  PreferenceMappingV1,
  PreferenceSignalEvidenceV1,
  SessionAnalysisEvidenceV1
} from './episteme';
import type { EntryObservation } from './solveV2';

const at = (day: number) => `2026-01-${String(day).padStart(2, '0')}T12:00:00.000Z`;
const cells = (...ids: string[]) => ids as CellId[];

function observation(overrides: Partial<EntryObservation> = {}): EntryObservation {
  return {
    sessionId: 'session-1',
    puzzleHash: 'hash-1',
    entryId: 'entry-1' as EntryId,
    finalState: 'correct',
    outcome: 'independent-retrieval',
    inputMode: 'manual',
    prefilledFraction: 0,
    supportCellIds: [],
    revealedCellIds: [],
    correctnessShownCellIds: [],
    unknownProvenanceCellIds: [],
    attemptedCellIds: cells('cell-1'),
    checkCorrectedCellIds: [],
    revealCorrectedCellIds: [],
    incorrectAttemptCount: 0,
    independentSuccessWeight: 1,
    supportedSuccessWeight: 0,
    failureWeight: 0,
    ...overrides
  };
}

const task: KnowledgeTaskV1 = {
  taskId: 'sense:echo',
  taskKind: 'sense',
  direction: 'clue-to-answer',
  language: 'en',
  clueFamily: 'wordplay',
  contentReview: 'approved'
};

function sessionEvidence(
  evidenceId: string,
  value: EntryObservation | readonly EntryObservation[],
  contentReview: KnowledgeTaskV1['contentReview'] = 'approved',
  day = 1
): SessionAnalysisEvidenceV1 {
  const observations = Array.isArray(value) ? value : [value];
  return {
    evidenceId,
    recordedAt: at(day),
    type: 'session-analysis',
    analysis: {
      schemaVersion: 1,
      analysisVersion: 'knowledge-reducer-v1',
      sessionId: observations[0]?.sessionId ?? 'session-1',
      puzzleHash: observations[0]?.puzzleHash ?? 'hash-1',
      observations
    },
    taskLinks: observations.map((item) => ({
      entryId: item.entryId,
      tasks: [{ ...task, contentReview }]
    }))
  };
}

function mapping(overrides: Partial<PreferenceMappingV1> = {}): PreferenceMappingV1 {
  return {
    mappingId: 'map-1',
    concept: { conceptId: 'sound-words', label: 'words about sound' },
    kind: 'taste',
    stance: 'seek',
    weight: 0.2,
    scope: {},
    ...overrides
  };
}

function calibrationProposal(overrides: Partial<CalibrationAssociationProposalEvidenceV1> = {}): CalibrationAssociationProposalEvidenceV1 {
  return {
    evidenceId: 'calibration-draft',
    recordedAt: '2026-01-01T12:00:00.000Z',
    type: 'association-proposal',
    associationId: 'cal-assoc-1',
    phrase: 'a paper moon in a blue room',
    language: 'en',
    relation: 'metaphor',
    parentConceptIds: ['paper-moon', 'blue-room'],
    explanation: 'A provisional bridge between two selected signs',
    origin: 'calibration-proposal',
    calibrationId: 'calibration-1',
    sourceObservationIds: ['observation-1', 'observation-2'],
    sourceStimulusIds: ['paper-moon', 'blue-room'],
    expiresAt: '2026-01-15T12:00:00.000Z',
    expireAfterSessions: 5,
    ...overrides
  } as CalibrationAssociationProposalEvidenceV1;
}

function responseEvidence(
  evidenceId: string,
  response: PreferenceSignalEvidenceV1['response'],
  overrides: Partial<PreferenceSignalEvidenceV1> = {}
): PreferenceSignalEvidenceV1 {
  return {
    evidenceId,
    recordedAt: at(1),
    type: 'preference-signal',
    source: 'reflection-card',
    sessionId: 'session-1',
    response,
    ambiguity: 'clear',
    stimulusId: 'card-1',
    stimulusVersion: '1',
    mappings: response === 'pass' ? {} : { [response]: [mapping()] },
    ...overrides
  };
}

function explicitEvidence(
  evidenceId: string,
  action: ExplicitPreferenceEvidenceV1['action'],
  overrides: Partial<ExplicitPreferenceEvidenceV1> = {}
): ExplicitPreferenceEvidenceV1 {
  return {
    evidenceId,
    recordedAt: at(1),
    type: 'explicit-preference',
    concept: { conceptId: 'us-officeholders', label: 'US political officeholders' },
    kind: 'taste',
    action,
    scope: { mode: 'play' },
    supersedesEvidenceIds: [],
    userText: action === 'exclude' ? 'Fewer US officeholder clues' : undefined,
    ...overrides
  };
}

function update(
  profileId: string,
  baseRevision: number,
  evidence: readonly EpistemeEvidenceV1[],
  overrides: Partial<EpistemeUpdateCommandV1> = {}
): EpistemeUpdateCommandV1 {
  return {
    updateId: `update-${baseRevision + 1}`,
    profileId,
    baseRevision,
    recordedAt: at(2),
    evidence,
    evidenceActions: [],
    ...overrides
  };
}

function apply(evidence: readonly EpistemeEvidenceV1[]) {
  const initial = createEpistemeProfile('profile-1', at(1));
  return applyEpistemeUpdate(initial, update(initial.profileId, 0, evidence)).profile;
}

describe('personal episteme evidence reducer', () => {
  it('accepts bounded private clue-surface and language-pack receipts on task links', () => {
    const extended = sessionEvidence('surface-receipt', observation());
    const extendedTask: KnowledgeTaskV1 = {
      ...task,
      surfaceFamily: 'pun',
      taskPack: {
        packId: 'synthetic-local-language-pairs-v1',
        packVersion: 'language-task-pairs-v1',
        packDigest: 'a'.repeat(64),
        pairId: 'de-en-ja-v1',
        sourceLanguage: 'en',
        targetLanguage: 'de',
        sourceText: 'yes',
        direction: 'source-to-target',
        source: { sourceId: 'synthetic-local-language-source-v1' },
        grammar: { version: 'language-task-grammar-v1' },
        reviewStatus: 'synthetic-unadmitted',
        semanticStatus: 'not-established',
        masteryClaim: 'none'
      }
    };
    const withReceipts = {
      ...extended,
      taskLinks: extended.taskLinks.map((link) => ({ ...link, tasks: [extendedTask] }))
    };

    expect(validateEpistemeEvidence(withReceipts)).toBe(true);
    expect(validateEpistemeEvidence({
      ...withReceipts,
      taskLinks: [{
        ...withReceipts.taskLinks[0],
        tasks: [{ ...extendedTask, taskPack: { ...extendedTask.taskPack, masteryClaim: 'known' } }]
      }]
    })).toBe(false);
  });

  it('uses only approved, independent manual retrieval as independent knowledge evidence', () => {
    const profile = apply([
      sessionEvidence('good', observation()),
      sessionEvidence('revealed', observation({
        entryId: 'entry-2' as EntryId,
      outcome: 'reveal-assisted-correction',
      revealedCellIds: cells('cell-2'),
        independentSuccessWeight: 0
      })),
      sessionEvidence('unknown', observation({
        entryId: 'entry-3' as EntryId,
        unknownProvenanceCellIds: cells('cell-3')
      })),
      sessionEvidence('unreviewed', observation({ entryId: 'entry-4' as EntryId }), 'unreviewed')
    ]);
    const estimate = profile.projection.knowledge[0];
    expect(estimate?.independent.successWeight).toBe(1);
    expect(estimate?.supportEvidenceIds).toEqual(['good/entry/entry-1/task/sense%3Aecho']);
    expect(estimate?.exposureEvidenceIds).toContain('revealed/entry/entry-2/task/sense%3Aecho');
    expect(estimate?.supportEvidenceIds).not.toContain('unknown/entry/entry-3/task/sense%3Aecho');
  });

  it('keeps supported retrieval separate and contributes no more than .35', () => {
    const profile = apply([sessionEvidence('supported', observation({
      outcome: 'supported-retrieval',
      prefilledFraction: 0.4,
      supportCellIds: cells('cell-0'),
      supportedSuccessWeight: 0.35,
      independentSuccessWeight: 0
    }))]);
    expect(profile.projection.knowledge[0]?.independent.successWeight).toBe(0);
    expect(profile.projection.knowledge[0]?.supported.successWeight).toBe(0.35);
    expect(profile.projection.knowledge[0]?.supported.mean).toBeCloseTo(1.35 / 2.35);
  });

  it('caps repeated success and check-supported failure at one and .5 per task/session', () => {
    const first = observation();
    const second = observation({ entryId: 'entry-2' as EntryId });
    const wrongOne = observation({
      entryId: 'entry-3' as EntryId,
      outcome: 'check-assisted-correction',
      incorrectAttemptCount: 2,
      correctnessShownCellIds: cells('cell-3'),
      independentSuccessWeight: 0,
      failureWeight: 0.5
    });
    const wrongTwo = observation({
      entryId: 'entry-4' as EntryId,
      outcome: 'incorrect-attempt',
      finalState: 'incorrect',
      incorrectAttemptCount: 3,
      correctnessShownCellIds: cells('cell-4'),
      independentSuccessWeight: 0,
      failureWeight: 0.5
    });
    const profile = apply([
      sessionEvidence('a', [first, wrongOne], 'approved', 1),
      sessionEvidence('b', [second, wrongTwo], 'approved', 2)
    ]);
    expect(profile.projection.knowledge[0]?.independent.successWeight).toBe(1);
    expect(profile.projection.knowledge[0]?.independent.failureWeight).toBe(0.5);
    expect(profile.projection.knowledge[0]?.supportEvidenceIds).toHaveLength(2);
    expect(profile.projection.knowledge[0]?.failureEvidenceIds).toHaveLength(2);
  });

  it('does not count unchecked wrong guesses or batch entry as retrieval evidence', () => {
    const profile = apply([
      sessionEvidence('unchecked', observation({
        outcome: 'incorrect-attempt',
        finalState: 'incorrect',
        incorrectAttemptCount: 1,
        independentSuccessWeight: 0,
        failureWeight: 0.5
      })),
      sessionEvidence('batch', observation({
        entryId: 'entry-2' as EntryId,
        outcome: 'batch-entry',
        inputMode: 'batch',
        attemptedCellIds: [],
        independentSuccessWeight: 0
      }))
    ]);
    expect(profile.projection.knowledge[0]?.independent.failureWeight).toBe(0);
    expect(profile.projection.knowledge[0]?.independent.successWeight).toBe(0);
    expect(profile.projection.knowledge[0]?.exposureEvidenceIds).toContain('batch/entry/entry-2/task/sense%3Aecho');
  });

  it('uses only the chosen card mapping and never derives a negative response by inversion', () => {
    const positive = mapping({
      mappingId: 'positive-map',
      concept: { conceptId: 'etymology', label: 'word histories' },
      stance: 'seek'
    });
    const authoredNegative = mapping({
      mappingId: 'negative-map',
      concept: { conceptId: 'officeholder-trivia', label: 'officeholder trivia' },
      stance: 'avoid'
    });
    const profile = apply([responseEvidence('negative', 'not-for-me', {
      mappings: { keep: [positive], 'not-for-me': [authoredNegative] }
    })]);
    expect(profile.projection.claims.map((claim) => [claim.concept.conceptId, claim.stance])).toEqual([['officeholder-trivia', 'avoid']]);
  });

  it('gives pass and performance-only evidence exactly zero preference weight', () => {
    const pass = responseEvidence('pass', 'pass');
    const performance = {
      evidenceId: 'fast-finish',
      recordedAt: at(1),
      type: 'performance',
      sessionId: 'session-1',
      measure: 'speed',
      value: 20
    } as const;
    const profile = apply([pass, performance]);
    expect(profile.projection.claims).toEqual([]);
    expect(profile.projection.policies).toEqual([]);
  });

  it('caps ambiguous signals at .05 and all inferred contributions per session/facet at .25', () => {
    const one = responseEvidence('ambiguous-a', 'keep', {
      ambiguity: 'ambiguous',
      mappings: { keep: [mapping({ mappingId: 'a', weight: 0.5 })] }
    });
    const two = responseEvidence('ambiguous-b', 'keep', {
      ambiguity: 'ambiguous',
      mappings: { keep: [mapping({ mappingId: 'b', weight: 0.5 })] }
    });
    const clear = responseEvidence('clear', 'keep', {
      mappings: { keep: [mapping({ mappingId: 'c', weight: 0.2 })] }
    });
    const profile = apply([clear, two, one]);
    const claim = profile.projection.claims[0];
    expect(claim?.strength).toBeCloseTo(0.25);
    expect(claim?.adequacy).toBe('repeated');
  });

  it('keeps positive and negative evidence separate and decays only inferred scores', () => {
    const seek = responseEvidence('seek', 'keep', {
      recordedAt: '2026-01-01T12:00:00.000Z',
      sessionId: 'session-seek',
      mappings: { keep: [mapping({ weight: 0.2 })] }
    });
    const avoid = responseEvidence('avoid', 'not-for-me', {
      recordedAt: '2026-01-01T12:00:00.000Z',
      sessionId: 'session-avoid',
      mappings: { 'not-for-me': [mapping({ stance: 'avoid', weight: 0.2 })] }
    });
    const explicit = explicitEvidence('explicit', 'seek', {
      concept: { conceptId: 'other-topic', label: 'another topic' }
    });
    const initial = createEpistemeProfile('profile-1', at(1));
    const changed = applyEpistemeUpdate(initial, update('profile-1', 0, [seek, avoid, explicit], {
      recordedAt: '2026-07-01T12:00:00.000Z'
    })).profile;
    const sound = changed.projection.claims.find((claim) => claim.concept.conceptId === 'sound-words');
    const explicitClaim = changed.projection.claims.find((claim) => claim.concept.conceptId === 'other-topic');
    expect(sound?.stance).toBe('ambivalent');
    expect(sound?.adequacy).toBe('contradictory');
    expect(sound?.evidenceIds).toEqual(['seek']);
    expect(sound?.counterEvidenceIds).toEqual(['avoid']);
    expect(explicitClaim?.strength).toBe(1);
    expect(explicitClaim?.authority).toBe('explicit');
  });

  it('keeps explicit hard controls separate, scopes them, and exposes unresolved explicit conflict', () => {
    const one = explicitEvidence('exclude-1', 'exclude');
    const two = explicitEvidence('seek-2', 'seek');
    const profile = apply([one, two]);
    expect(profile.projection.policies[0]?.mode).toBe('conflict');
    expect(profile.projection.policies[0]?.scope).toEqual({ mode: 'play' });
    expect(profile.projection.claims[0]?.stance).toBe('ambivalent');
    expect(profile.projection.claims[0]?.lockedByUser).toBe(true);
  });

  it('lets an explicit correction supersede earlier explicit evidence without erasing its record', () => {
    const first = explicitEvidence('old', 'exclude');
    const correction = explicitEvidence('new', 'seek', {
      recordedAt: at(2),
      supersedesEvidenceIds: ['old']
    });
    const profile = apply([first, correction]);
    expect(profile.evidence).toHaveLength(2);
    expect(profile.projection.policies[0]?.mode).toBe('include');
    expect(profile.projection.policies[0]?.evidenceIds).toEqual(['new']);
  });

  it('keeps model association proposals provisional until the player responds', () => {
    const seed = explicitEvidence('seed', 'seek', {
      concept: { conceptId: 'sound-words', label: 'words about sound' }
    });
    const proposal: AssociationProposalEvidenceV1 = {
      evidenceId: 'model-draft',
      recordedAt: at(2),
      type: 'association-proposal',
      associationId: 'assoc-1',
      phrase: 'rooms that keep an echo',
      language: 'en',
      relation: 'metaphor',
      parentConceptIds: ['sound-words'],
      explanation: 'A possible bridge from sound to places',
      origin: 'model-proposal'
    };
    const draft = apply([seed, proposal]);
    expect(draft.projection.associations[0]?.evidenceStatus).toBe('untested');
    expect(draft.projection.associations[0]?.explorationWeight).toBe(0);
    const endorsed = apply([seed, proposal, {
      evidenceId: 'association-keep',
      recordedAt: at(3),
      type: 'association-response',
      associationId: 'assoc-1',
      proposalEvidenceId: 'model-draft',
      response: 'keep'
    }]);
    expect(endorsed.projection.associations[0]?.supportEvidenceIds).toEqual(['association-keep']);
    expect(endorsed.projection.associations[0]?.explorationWeight).toBe(0.05);
    expect(endorsed.projection.claims.some((claim) => claim.concept.conceptId === 'rooms-that-keep-an-echo')).toBe(false);
  });

  it('expires an unendorsed model association after its bounded lifetime', () => {
    const seed = explicitEvidence('seed-expiring', 'seek', {
      concept: { conceptId: 'sound-words', label: 'words about sound' }
    });
    const proposal: AssociationProposalEvidenceV1 = {
      evidenceId: 'model-expiring',
      recordedAt: at(1),
      type: 'association-proposal',
      associationId: 'assoc-expiring',
      phrase: 'rooms that keep an echo',
      language: 'en',
      relation: 'metaphor',
      parentConceptIds: ['sound-words'],
      explanation: 'A bounded path from sound to places',
      origin: 'model-proposal',
      expiresAt: '2026-01-31T12:00:00.000Z',
      expireAfterSessions: 10
    };
    expect(validateEpistemeEvidence(proposal)).toBe(true);
    const before = projectEpistemeProfile(apply([seed, proposal]), '2026-01-30T12:00:00.000Z');
    expect(before.projection.associations[0]?.modelProvenance).toMatchObject({ expired: false, expirationReasons: [] });
    const expired = projectEpistemeProfile(apply([seed, proposal]), '2026-02-01T12:00:00.000Z');
    expect(expired.projection.associations[0]?.modelProvenance).toMatchObject({ expired: true, expirationReasons: ['age'] });
    expect(expired.projection.associations[0]?.explorationWeight).toBe(0);
  });

  it('validates calibration provenance and requires exact one-to-one stimulus parents', () => {
    const proposal = calibrationProposal();
    expect(validateEpistemeEvidence(proposal)).toBe(true);
    expect(validateEpistemeEvidence({ ...proposal, calibrationId: undefined })).toBe(false);
    expect(validateEpistemeEvidence({ ...proposal, sourceObservationIds: [] })).toBe(false);
    expect(validateEpistemeEvidence({ ...proposal, sourceObservationIds: ['same', 'same'] })).toBe(false);
    expect(validateEpistemeEvidence({ ...proposal, sourceObservationIds: ['one', 'two', 'three', 'four', 'five', 'six'] })).toBe(false);
    expect(validateEpistemeEvidence({ ...proposal, sourceStimulusIds: ['paper-moon'] })).toBe(false);
    expect(validateEpistemeEvidence({ ...proposal, parentConceptIds: ['paper-moon', 'unlinked'] })).toBe(false);
    expect(validateEpistemeEvidence({ ...proposal, parentConceptIds: ['paper-moon', 'blue-room'], sourceStimulusIds: ['paper-moon', 'blue-room', 'extra'] })).toBe(false);
    expect(validateEpistemeEvidence({ ...proposal, expiresAt: '2026-01-16T12:00:00.000Z' })).toBe(false);
    expect(validateEpistemeEvidence({ ...proposal, expireAfterSessions: 4 })).toBe(false);

    const forgedModel = {
      ...proposal,
      origin: 'model-proposal',
      calibrationId: 'calibration-1'
    };
    expect(validateEpistemeEvidence(forgedModel)).toBe(false);
    const { calibrationId, sourceObservationIds, sourceStimulusIds, expiresAt, expireAfterSessions, ...modelProposal } = proposal;
    void calibrationId;
    void sourceObservationIds;
    void sourceStimulusIds;
    void expiresAt;
    void expireAfterSessions;
    expect(validateEpistemeEvidence({ ...modelProposal, origin: 'model-proposal' })).toBe(true);
  });

  it('projects calibration associations as provisional provenance, never as taste or knowledge', () => {
    const proposal = calibrationProposal();
    const draft = apply([proposal]);
    expect(draft.projection.associationReducerVersion).toBe('association-reducer-v2');
    expect(draft.projection.associations[0]).toMatchObject({
      associationId: 'cal-assoc-1',
      origin: 'calibration-proposal',
      explorationWeight: 0,
      calibrationProvenance: {
        calibrationId: 'calibration-1',
        sourceObservationIds: ['observation-1', 'observation-2'],
        sourceStimulusIds: ['paper-moon', 'blue-room'],
        expiresAt: '2026-01-15T12:00:00.000Z',
        expireAfterSessions: 5,
        expired: false,
        expirationReasons: []
      }
    });
    const kept = apply([
      proposal,
      ...['keep-1', 'keep-2'].map((evidenceId, index) => ({
        evidenceId,
        recordedAt: at(index + 2),
        type: 'association-response' as const,
        associationId: 'cal-assoc-1',
        proposalEvidenceId: proposal.evidenceId,
        response: 'keep' as const
      }))
    ]);
    expect(kept.projection.associations[0]?.explorationWeight).toBe(0.05);
    expect(kept.projection.claims).toEqual([]);
    expect(kept.projection.knowledge).toEqual([]);
    expect(kept.projection.associations[0]?.calibrationProvenance?.expired).toBe(false);
  });

  it('expires calibration hypotheses after 14 days or five later analyzed sessions, and restores on retraction', () => {
    const proposal = calibrationProposal();
    const keep = {
      evidenceId: 'calibration-keep',
      recordedAt: '2026-01-02T12:00:00.000Z',
      type: 'association-response',
      associationId: proposal.associationId,
      proposalEvidenceId: proposal.evidenceId,
      response: 'keep'
    } as const;
    const sessions = Array.from({ length: 5 }, (_, index) => sessionEvidence(
      `later-session-${index + 1}`,
      observation({ sessionId: `session-${index + 2}` }),
      'approved',
      index + 2
    ));
    const initial = createEpistemeProfile('profile-1', at(1));
    const expired = applyEpistemeUpdate(initial, update(initial.profileId, 0, [proposal, keep, ...sessions], {
      recordedAt: '2026-01-07T12:00:00.000Z'
    })).profile;
    expect(expired.projection.associations[0]?.calibrationProvenance).toMatchObject({
      expired: true,
      expirationReasons: ['sessions']
    });
    expect(expired.projection.associations[0]?.explorationWeight).toBe(0);

    const retracted = applyEpistemeUpdate(expired, update(expired.profileId, expired.revision, [], {
      updateId: 'retract-session-five',
      recordedAt: '2026-01-08T12:00:00.000Z',
      evidenceActions: [{
        actionId: 'retract-session-five-action',
        targetEvidenceId: 'later-session-5',
        action: 'retract',
        recordedAt: '2026-01-08T12:00:00.000Z'
      }]
    })).profile;
    expect(retracted.projection.associations[0]?.calibrationProvenance).toMatchObject({ expired: false, expirationReasons: [] });
    expect(retracted.projection.associations[0]?.explorationWeight).toBe(0.05);

    const restored = applyEpistemeUpdate(retracted, update(retracted.profileId, retracted.revision, [], {
      updateId: 'restore-session-five',
      recordedAt: '2026-01-09T12:00:00.000Z',
      evidenceActions: [{
        actionId: 'restore-session-five-action',
        targetEvidenceId: 'later-session-5',
        action: 'restore',
        recordedAt: '2026-01-09T12:00:00.000Z'
      }]
    })).profile;
    expect(restored.projection.associations[0]?.calibrationProvenance).toMatchObject({ expired: true, expirationReasons: ['sessions'] });
    expect(restored.projection.associations[0]?.explorationWeight).toBe(0);

    const byAge = applyEpistemeUpdate(restored, update(restored.profileId, restored.revision, [], {
      updateId: 'advance-beyond-age-expiry',
      recordedAt: '2026-01-15T12:00:00.000Z'
    })).profile;
    expect(byAge.projection.associations[0]?.calibrationProvenance).toMatchObject({ expired: true, expirationReasons: ['age', 'sessions'] });
    expect(byAge.projection.associations[0]?.explorationWeight).toBe(0);
  });

  it('rebuilds time-sensitive expiry on read without mutating the ledger and respects active evidence actions', () => {
    const proposal = calibrationProposal();
    const keep = {
      evidenceId: 'read-time-keep',
      recordedAt: '2026-01-02T12:00:00.000Z',
      type: 'association-response',
      associationId: proposal.associationId,
      proposalEvidenceId: proposal.evidenceId,
      response: 'keep'
    } as const;
    const laterSessions = Array.from({ length: 5 }, (_, index) => sessionEvidence(
      `read-session-${index + 1}`,
      observation({ sessionId: `read-session-id-${index + 1}` }),
      'approved',
      index + 2
    ));
    const initial = createEpistemeProfile('profile-1', at(1));
    const stored = applyEpistemeUpdate(initial, update(initial.profileId, 0, [proposal, keep, ...laterSessions], {
      recordedAt: '2026-01-02T12:00:00.000Z'
    })).profile;
    expect(stored.projection.associations[0]?.calibrationProvenance?.expired).toBe(false);

    const expiredAtRead = projectEpistemeProfile(stored, '2026-01-07T12:00:00.000Z');
    expect(expiredAtRead.projection.associations[0]?.calibrationProvenance).toMatchObject({
      expired: true,
      expirationReasons: ['sessions']
    });
    expect(expiredAtRead.projection.associations[0]?.explorationWeight).toBe(0);
    expect(stored.projection.associations[0]?.calibrationProvenance?.expired).toBe(false);
    expect(expiredAtRead.evidence).toBe(stored.evidence);
    expect(expiredAtRead.evidenceActions).toBe(stored.evidenceActions);
    expect(expiredAtRead.revision).toBe(stored.revision);
    expect(expiredAtRead.updatedAt).toBe(stored.updatedAt);
    expect(expiredAtRead.updates).toBe(stored.updates);

    const retracted = applyEpistemeUpdate(stored, update(stored.profileId, stored.revision, [], {
      updateId: 'retract-for-read-project',
      recordedAt: '2026-01-08T12:00:00.000Z',
      evidenceActions: [{
        actionId: 'retract-for-read-project-action',
        targetEvidenceId: 'read-session-5',
        action: 'retract',
        recordedAt: '2026-01-08T12:00:00.000Z'
      }]
    })).profile;
    const unexpiredAtRead = projectEpistemeProfile(retracted, '2026-01-09T12:00:00.000Z');
    expect(unexpiredAtRead.projection.associations[0]?.calibrationProvenance).toMatchObject({ expired: false, expirationReasons: [] });
    expect(unexpiredAtRead.projection.associations[0]?.explorationWeight).toBe(0.05);

    const restored = applyEpistemeUpdate(retracted, update(retracted.profileId, retracted.revision, [], {
      updateId: 'restore-for-read-project',
      recordedAt: '2026-01-10T12:00:00.000Z',
      evidenceActions: [{
        actionId: 'restore-for-read-project-action',
        targetEvidenceId: 'read-session-5',
        action: 'restore',
        recordedAt: '2026-01-10T12:00:00.000Z'
      }]
    })).profile;
    const expiredAfterRestore = projectEpistemeProfile(restored, '2026-01-11T12:00:00.000Z');
    expect(expiredAfterRestore.projection.associations[0]?.calibrationProvenance).toMatchObject({
      expired: true,
      expirationReasons: ['sessions']
    });
    expect(expiredAfterRestore.projection.associations[0]?.explorationWeight).toBe(0);

    const expiredByAge = projectEpistemeProfile(apply([proposal, keep]), '2026-01-15T12:00:00.000Z');
    expect(expiredByAge.projection.associations[0]?.calibrationProvenance).toMatchObject({
      expired: true,
      expirationReasons: ['age']
    });
    expect(expiredByAge.projection.associations[0]?.explorationWeight).toBe(0);
  });

  it('restores a calibration proposal after its response is retracted', () => {
    const proposal = calibrationProposal();
    const initial = createEpistemeProfile('profile-1', at(1));
    const first = applyEpistemeUpdate(initial, update(initial.profileId, 0, [proposal, {
      evidenceId: 'calibration-keep',
      recordedAt: at(2),
      type: 'association-response',
      associationId: proposal.associationId,
      proposalEvidenceId: proposal.evidenceId,
      response: 'keep'
    }])).profile;
    expect(first.projection.associations[0]?.explorationWeight).toBe(0.05);
    const retracted = applyEpistemeUpdate(first, update(first.profileId, 1, [], {
      evidenceActions: [{ actionId: 'retract-keep', targetEvidenceId: 'calibration-keep', action: 'retract', recordedAt: at(3) }]
    })).profile;
    expect(retracted.projection.associations[0]?.evidenceStatus).toBe('untested');
    expect(retracted.projection.associations[0]?.explorationWeight).toBe(0);
    const restored = applyEpistemeUpdate(retracted, update(retracted.profileId, 2, [], {
      evidenceActions: [{ actionId: 'restore-keep', targetEvidenceId: 'calibration-keep', action: 'restore', recordedAt: at(4) }]
    })).profile;
    expect(restored.projection.associations[0]?.evidenceStatus).toBe('responded-to');
    expect(restored.projection.associations[0]?.explorationWeight).toBe(0.05);
  });

  it('rebuilds on retraction/restoration and leaves an inspectable before/after receipt', () => {
    const source = responseEvidence('source', 'keep');
    const initial = createEpistemeProfile('profile-1', at(1));
    const firstCommand = update(initial.profileId, 0, [source]);
    const first = applyEpistemeUpdate(initial, firstCommand);
    expect(first.profile.projection.claims).toHaveLength(1);
    expect(first.receipt.changes[0]?.before).toBeNull();
    expect(first.receipt.changes[0]?.after).not.toBeNull();
    const retraction = applyEpistemeUpdate(first.profile, update('profile-1', 1, [], {
      evidenceActions: [{ actionId: 'retract-1', targetEvidenceId: 'source', action: 'retract', recordedAt: at(3) }]
    }));
    expect(retraction.profile.projection.claims).toEqual([]);
    const restored = applyEpistemeUpdate(retraction.profile, update('profile-1', 2, [], {
      evidenceActions: [{ actionId: 'restore-1', targetEvidenceId: 'source', action: 'restore', recordedAt: at(4) }]
    }));
    expect(restored.profile.projection.claims).toHaveLength(1);
    expect(restored.profile.evidence).toHaveLength(1);
  });

  it('uses stable canonical idempotency input, replays exact retries, and rejects stale writes', () => {
    const a = responseEvidence('a', 'keep');
    const b = explicitEvidence('b', 'exclude');
    const command = update('profile-1', 0, [a, b]);
    expect(canonicalEpistemeUpdateHashInput(command)).toBe(canonicalEpistemeUpdateHashInput({ ...command, evidence: [b, a] }));
    expect(stableEpistemeStringify({ b: 2, a: 1 })).toBe('{"a":1,"b":2}');
    const profile = createEpistemeProfile('profile-1', at(1));
    const first = applyEpistemeUpdate(profile, command);
    const replay = applyEpistemeUpdate(first.profile, command);
    expect(replay.replayed).toBe(true);
    expect(replay.profile).toBe(first.profile);
    expect(() => applyEpistemeUpdate(first.profile, {
      ...update('profile-1', 1, [responseEvidence('different', 'pass')]),
      updateId: command.updateId
    })).toThrow(/updateId was reused/);
    expect(() => applyEpistemeUpdate(first.profile, {
      ...update('profile-1', 0, [responseEvidence('different', 'pass')]),
      updateId: 'stale-write'
    })).toThrow(/Stale profile revision/);
  });

  it('validates source events and rejects an association response detached from its proposal', () => {
    const pass = responseEvidence('pass', 'pass');
    expect(validateEpistemeEvidence(pass)).toBe(true);
    expect(validateEpistemeEvidence({ ...pass, mappings: { keep: [mapping()] } })).toBe(false);
    const detached = {
      evidenceId: 'detached',
      recordedAt: at(1),
      type: 'association-response',
      associationId: 'a',
      proposalEvidenceId: 'missing',
      response: 'keep'
    } as const;
    const profile = createEpistemeProfile('profile-1', at(1));
    expect(() => applyEpistemeUpdate(profile, update('profile-1', 0, [detached]))).toThrow(/exact proposal/);
  });
});
