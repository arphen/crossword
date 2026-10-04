import { describe, expect, it } from 'vitest';
import type { CellId, EntryId } from './puzzle';
import {
  applyEpistemeUpdate,
  createEpistemeProfile
} from './episteme';
import type {
  EpistemeEvidenceV1,
  EpistemeProfileV1,
  EpistemeUpdateCommandV1,
  KnowledgeTaskV1,
  PreferenceMappingV1,
  SessionAnalysisEvidenceV1
} from './episteme';
import {
  compileEpistemeBrief,
  EPISTEME_BRIEF_BROAD_FLOOR
} from './epistemeBrief';
import type { EligibleLexiconCandidateV1 } from './epistemeBrief';
import type { EntryObservation } from './solveV2';

const at = (day: number) => `2026-01-${String(day).padStart(2, '0')}T12:00:00.000Z`;
const cells = (...ids: string[]) => ids as CellId[];

const task: KnowledgeTaskV1 = {
  taskId: 'sense:echo',
  taskKind: 'sense',
  direction: 'clue-to-answer',
  language: 'en',
  clueFamily: 'wordplay',
  contentReview: 'approved'
};

function observation(sessionId: string): EntryObservation {
  return {
    sessionId,
    puzzleHash: `hash-${sessionId}`,
    entryId: `entry-${sessionId}` as EntryId,
    finalState: 'correct',
    outcome: 'independent-retrieval',
    inputMode: 'manual',
    prefilledFraction: 0,
    supportCellIds: [],
    revealedCellIds: [],
    correctnessShownCellIds: [],
    unknownProvenanceCellIds: [],
    attemptedCellIds: cells(`cell-${sessionId}`),
    checkCorrectedCellIds: [],
    revealCorrectedCellIds: [],
    incorrectAttemptCount: 0,
    independentSuccessWeight: 1,
    supportedSuccessWeight: 0,
    failureWeight: 0
  };
}

function sessionEvidence(evidenceId: string, sessionId: string, day: number): SessionAnalysisEvidenceV1 {
  const seen = observation(sessionId);
  return {
    evidenceId,
    recordedAt: at(day),
    type: 'session-analysis',
    analysis: {
      schemaVersion: 1,
      analysisVersion: 'knowledge-reducer-v1',
      sessionId,
      puzzleHash: seen.puzzleHash,
      observations: [seen]
    },
    taskLinks: [{ entryId: seen.entryId, tasks: [task] }]
  };
}

function explicit(evidenceId: string, conceptId: string, action: 'seek' | 'exclude'): EpistemeEvidenceV1 {
  return {
    evidenceId,
    recordedAt: at(1),
    type: 'explicit-preference',
    concept: { conceptId, label: conceptId },
    kind: 'taste',
    action,
    scope: {},
    supersedesEvidenceIds: []
  };
}

function proposal(): EpistemeEvidenceV1 {
  return {
    evidenceId: 'proposal-ocean',
    recordedAt: at(1),
    type: 'association-proposal',
    associationId: 'association-ocean',
    phrase: 'a tide in a glass',
    language: 'en',
    relation: 'metaphor',
    parentConceptIds: ['ocean'],
    explanation: 'An untested image linked to an explicit seed',
    origin: 'model-proposal'
  };
}

function proposalFrom(conceptId: string, associationId: string): EpistemeEvidenceV1 {
  return {
    evidenceId: `proposal-${associationId}`,
    recordedAt: at(1),
    type: 'association-proposal',
    associationId,
    phrase: `a path from ${conceptId}`,
    language: 'en',
    relation: 'metaphor',
    parentConceptIds: [conceptId],
    explanation: 'An untested path that remains a candidate',
    origin: 'model-proposal'
  };
}

function mapping(conceptId: string, stance: 'seek' | 'avoid'): PreferenceMappingV1 {
  return {
    mappingId: `map-${conceptId}`,
    concept: { conceptId, label: conceptId },
    kind: 'taste',
    stance,
    weight: 0.2,
    scope: {}
  };
}

function profile(evidence: readonly EpistemeEvidenceV1[] = []): EpistemeProfileV1 {
  const initial = createEpistemeProfile('profile-brief', at(1));
  if (evidence.length === 0) return initial;
  const command: EpistemeUpdateCommandV1 = {
    updateId: 'brief-evidence',
    profileId: initial.profileId,
    baseRevision: 0,
    recordedAt: at(8),
    evidence,
    evidenceActions: []
  };
  return applyEpistemeUpdate(initial, command).profile;
}

function candidate(
  candidateId: string,
  overrides: Partial<EligibleLexiconCandidateV1> = {}
): EligibleLexiconCandidateV1 {
  return {
    candidateId,
    answer: candidateId.toUpperCase(),
    language: 'en',
    conceptIds: [],
    knowledgeTaskIds: [],
    associationIds: [],
    pool: 'broad',
    eligibility: {
      status: 'eligible',
      packId: 'test-pack-fixture',
      packVersion: 'fixture-v1',
      sourceIds: [`source:${candidateId}`]
    },
    ...overrides
  };
}

const options = {
  asOf: at(8),
  mode: 'play',
  language: 'en'
} as const;

describe('episteme brief compiler', () => {
  it('keeps lanes distinct, links selected evidence/sources, and makes explicit exclusions absolute', () => {
    const source = profile([
      explicit('favorite-evidence', 'curiosity', 'seek'),
      explicit('excluded-evidence', 'officeholder-trivia', 'exclude'),
      {
        evidenceId: 'ocean-seed-evidence',
        recordedAt: at(1),
        type: 'explicit-preference',
        concept: { conceptId: 'ocean', label: 'ocean' },
        kind: 'taste',
        action: 'clear',
        scope: {},
        supersedesEvidenceIds: []
      },
      proposal(),
      proposalFrom('officeholder-trivia', 'association-excluded-seed'),
      sessionEvidence('retrieval-1', 'session-1', 2),
      sessionEvidence('retrieval-2', 'session-2', 3),
      sessionEvidence('retrieval-3', 'session-3', 4),
      {
        evidenceId: 'soft-avoid-evidence',
        recordedAt: at(5),
        type: 'preference-signal',
        source: 'reflection-card',
        response: 'keep',
        ambiguity: 'clear',
        stimulusId: 'quiet-card',
        stimulusVersion: '1',
        mappings: { keep: [mapping('velvet', 'avoid')] }
      }
    ]);
    const results = compileEpistemeBrief(source, [
      candidate('curiosity-term', { conceptIds: ['curiosity'], pool: 'exploration' }),
      candidate('known-echo', { knowledgeTaskIds: ['sense:echo'], pool: 'exploration' }),
      candidate('ocean-association', { conceptIds: ['unrelated'], associationIds: ['association-ocean'], pool: 'exploration' }),
      candidate('softly-avoided', { conceptIds: ['velvet'], pool: 'broad' }),
      candidate('blocked-but-relevant', {
        conceptIds: ['curiosity', 'officeholder-trivia'],
        associationIds: ['association-ocean'],
        knowledgeTaskIds: ['sense:echo'],
        pool: 'broad'
      }),
      candidate('blocked-through-association', {
        associationIds: ['association-excluded-seed'],
        pool: 'broad'
      }),
      candidate('wide-a'),
      candidate('wide-b'),
      candidate('new-path', { pool: 'exploration' })
    ], { ...options, selectionLimit: 7 });

    expect(results.hardExclusions).toContainEqual({
      conceptId: 'officeholder-trivia',
      scope: {},
      evidenceIds: ['excluded-evidence']
    });
    const blocked = results.selectionLog.find((item) => item.candidateId === 'blocked-but-relevant');
    expect(blocked).toMatchObject({
      selected: false,
      decision: 'hard-exclusion',
      hardExcludedConceptIds: ['officeholder-trivia'],
      evidenceIds: expect.arrayContaining(['excluded-evidence', 'favorite-evidence', 'ocean-seed-evidence', 'proposal-ocean'])
    });
    expect(blocked?.evidenceIds.some((id) => id.startsWith('retrieval-1/entry/'))).toBe(true);
    expect(results.selected.map((item) => item.candidate.candidateId)).not.toContain('blocked-but-relevant');
    expect(results.selectionLog.find((item) => item.candidateId === 'blocked-through-association')).toMatchObject({
      decision: 'hard-exclusion',
      selected: false,
      hardExcludedConceptIds: ['officeholder-trivia']
    });

    const explicitPick = results.selected.find((item) => item.candidate.candidateId === 'curiosity-term');
    expect(explicitPick?.selectedLane).toBe('explicit-preference');
    expect(explicitPick?.evidenceIds).toContain('favorite-evidence');
    expect(explicitPick?.sourceIds).toEqual(['source:curiosity-term']);

    const known = results.selected.find((item) => item.candidate.candidateId === 'known-echo');
    expect(known?.selectedLane).toBe('confirmed-knowledge');
    for (const evidenceId of ['retrieval-1', 'retrieval-2', 'retrieval-3']) {
      expect(known?.evidenceIds.some((id) => id.startsWith(`${evidenceId}/entry/`))).toBe(true);
    }

    const association = results.selected.find((item) => item.candidate.candidateId === 'ocean-association');
    expect(association?.selectedLane).toBe('provisional-association');
    expect(association?.matchedLanes).toContain('provisional-association');
    expect(association?.evidenceIds).toEqual(expect.arrayContaining(['proposal-ocean', 'ocean-seed-evidence']));

    const softAvoid = results.selected.find((item) => item.candidate.candidateId === 'softly-avoided');
    expect(softAvoid?.matchedLanes).toContain('inferred-preference');
    expect(softAvoid?.scoreComponents.inferredPreference).toBeLessThan(0);
    expect(results.selectionLog.find((item) => item.candidateId === 'softly-avoided')?.decision).not.toBe('hard-exclusion');

    expect(results.broadFloorRequested).toBe(3);
    expect(results.broadFloorMet).toBe(3);
    expect(results.lanes.broad).toHaveLength(3);
    expect(results.selectionLog).toHaveLength(9);
    expect(results.selectionLog.every((item) => item.sourceIds.length > 0)).toBe(true);
    expect(results.profileRevision).toBe(source.revision);
  });

  it('returns broad material on cold start and applies the broad floor when available', () => {
    const cold = profile();
    const result = compileEpistemeBrief(cold, [
      candidate('glue-a'),
      candidate('glue-b'),
      candidate('glue-c'),
      candidate('curious-a', { pool: 'exploration' }),
      candidate('curious-b', { pool: 'exploration' })
    ], { ...options, selectionLimit: 4 });
    expect(result.selected).toHaveLength(4);
    expect(result.selected.filter((item) => item.selectedLane === 'broad').length).toBeGreaterThanOrEqual(2);
    expect(result.broadFloorRequested).toBe(Math.ceil(4 * EPISTEME_BRIEF_BROAD_FLOOR));
    expect(result.hardExclusions).toEqual([]);
    expect(result.selected.every((item) => item.evidenceIds.length === 0)).toBe(true);
    expect(result.selected.every((item) => item.sourceIds.length === 1)).toBe(true);
  });

  it('does not call sparse, supported-only, or low-success history confirmed knowledge', () => {
    const sparse = profile([
      sessionEvidence('sparse-1', 'sparse-1', 2),
      sessionEvidence('sparse-2', 'sparse-2', 3)
    ]);
    const result = compileEpistemeBrief(sparse, [
      candidate('maybe-known', { knowledgeTaskIds: ['sense:echo'], pool: 'exploration' }),
      candidate('broad-answer')
    ], { ...options, selectionLimit: 2 });
    const maybeKnown = result.selected.find((item) => item.candidate.candidateId === 'maybe-known');
    expect(maybeKnown?.matchedLanes).not.toContain('confirmed-knowledge');
    expect(maybeKnown?.selectedLane).toBe('exploration');
    expect(maybeKnown?.evidenceIds).toEqual([]);
  });

  it('fails closed on candidates that do not carry eligibility and source links', () => {
    const malformed = candidate('unsourced') as unknown as Record<string, unknown>;
    malformed.eligibility = { status: 'eligible', packId: 'test', packVersion: '1', sourceIds: [] };
    expect(() => compileEpistemeBrief(profile(), [malformed as unknown as EligibleLexiconCandidateV1], {
      ...options,
      selectionLimit: 1
    })).toThrow(/source links/);
  });

  it('rebuilds exclusions from active evidence, so a retracted control no longer filters the brief', () => {
    const excluded = profile([explicit('temporary-exclusion', 'regional-politics', 'exclude')]);
    const option = candidate('regional-answer', { conceptIds: ['regional-politics'] });
    const before = compileEpistemeBrief(excluded, [option], { ...options, selectionLimit: 1 });
    expect(before.selectionLog[0]?.decision).toBe('hard-exclusion');

    const corrected = applyEpistemeUpdate(excluded, {
      updateId: 'retract-brief-exclusion',
      profileId: excluded.profileId,
      baseRevision: excluded.revision,
      recordedAt: at(9),
      evidence: [],
      evidenceActions: [{
        actionId: 'retract-brief-exclusion-action',
        targetEvidenceId: 'temporary-exclusion',
        action: 'retract',
        recordedAt: at(9)
      }]
    }).profile;
    const after = compileEpistemeBrief(corrected, [option], { ...options, selectionLimit: 1 });
    expect(after.hardExclusions).toEqual([]);
    expect(after.selected[0]?.candidate.candidateId).toBe('regional-answer');
  });

  it('applies an explicit exclusion only within its declared mode scope', () => {
    const scoped = profile([{
      evidenceId: 'learn-only-exclusion',
      recordedAt: at(1),
      type: 'explicit-preference',
      concept: { conceptId: 'learn-topic', label: 'learn topic' },
      kind: 'taste',
      action: 'exclude',
      scope: { mode: 'learn' },
      supersedesEvidenceIds: []
    }]);
    const item = candidate('topic-entry', { conceptIds: ['learn-topic'] });
    const play = compileEpistemeBrief(scoped, [item], { ...options, selectionLimit: 1 });
    const learn = compileEpistemeBrief(scoped, [item], { ...options, mode: 'learn', selectionLimit: 1 });
    expect(play.selected).toHaveLength(1);
    expect(play.hardExclusions).toEqual([]);
    expect(learn.selected).toEqual([]);
    expect(learn.selectionLog[0]?.decision).toBe('hard-exclusion');
  });

  it('bounds the requested selection count and logs language mismatches without selecting them', () => {
    expect(() => compileEpistemeBrief(profile(), [candidate('one')], { ...options, selectionLimit: 101 })).toThrow(/selection limit/);
    const oversizedPool = Array.from({ length: 5_001 }, (_, index) => candidate(`pool-${index}`));
    expect(() => compileEpistemeBrief(profile(), oversizedPool, { ...options, selectionLimit: 1 })).toThrow(/candidate pool/);
    const result = compileEpistemeBrief(profile(), [
      candidate('english'),
      candidate('wrong-language', { language: 'fr' })
    ], { ...options, selectionLimit: 2 });
    expect(result.selected.map((item) => item.candidate.candidateId)).toEqual(['english']);
    expect(result.selectionLog.find((item) => item.candidateId === 'wrong-language')).toMatchObject({
      selected: false,
      decision: 'language-mismatch',
      sourceIds: ['source:wrong-language']
    });
  });
});
