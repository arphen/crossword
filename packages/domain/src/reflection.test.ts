import { describe, expect, it } from 'vitest';
import {
  AMBIGUOUS_REFLECTION_BUDGET,
  isPlayableReflectionCard,
  reflectionActionToEvidenceAction,
  reflectionResponseToEvidence,
  validateReflectionCard,
  validateReflectionResponse,
  validateReflectionResponseAction
} from './reflection';
import type { ReflectionCardV1, ReflectionResponseActionV1, ReflectionResponseV1 } from './reflection';
import { validateEpistemeEvidence } from './episteme';
import type { PreferenceMappingV1 } from './episteme';

const createdAt = '2026-01-01T12:00:00.000Z';

function mapping(overrides: Partial<PreferenceMappingV1> = {}): PreferenceMappingV1 {
  return {
    mappingId: 'keep-etymology',
    concept: { conceptId: 'etymology:borrowings', label: 'borrowed-word histories' },
    kind: 'taste',
    stance: 'seek',
    weight: 0.2,
    scope: { mode: 'play' },
    ...overrides
  };
}

function card(overrides: Partial<ReflectionCardV1> = {}): ReflectionCardV1 {
  return {
    schemaVersion: 1,
    cardId: 'word-journey',
    version: 3,
    createdAt,
    text: "A word's journey can be more interesting than its destination.",
    language: 'en',
    relatedEntryIds: ['across-12'],
    source: 'authored',
    status: 'approved',
    tone: 'curious',
    ambiguity: 'clear',
    interpretation: {
      keep: 'Bring in more etymology and borrowed-word histories.',
      notForMe: 'Reduce this etymology direction in Play for up to 90 days.',
      pass: 'No profile change.'
    },
    keepMappings: [mapping()],
    notForMeMappings: [mapping({
      mappingId: 'avoid-etymology',
      stance: 'avoid',
      weight: 0.2,
      scope: { mode: 'play', expiresAt: '2026-03-01T12:00:00.000Z' }
    })],
    groundingRefs: ['entry:across-12'],
    generationReceipt: null,
    ...overrides
  };
}

function response(overrides: Partial<ReflectionResponseV1> = {}): ReflectionResponseV1 {
  return {
    schemaVersion: 1,
    responseId: 'response-1',
    cardId: 'word-journey',
    cardVersion: 3,
    sessionId: 'session-9',
    shownPosition: 0,
    recordedAt: '2026-01-02T12:00:00.000Z',
    response: 'keep',
    ...overrides
  };
}

describe('reflection card and response contracts', () => {
  it('validates a reviewed card with separate player-visible interpretations', () => {
    const value = card();
    expect(validateReflectionCard(value)).toBe(true);
    expect(isPlayableReflectionCard(value)).toBe(true);
    expect(value.interpretation.keep).toContain('etymology');
    expect(value.interpretation.notForMe).toContain('90 days');
  });

  it('converts keep into only its predeclared map and valid evidence', () => {
    const evidence = reflectionResponseToEvidence(card(), response({ response: 'keep' }));
    expect(evidence.mappings).toEqual({ keep: card().keepMappings });
    expect(Object.hasOwn(evidence.mappings, 'not-for-me')).toBe(false);
    expect(validateEpistemeEvidence(evidence)).toBe(true);
  });

  it('uses only the independent narrow negative map, never the positive-map inverse', () => {
    const value = card({
      keepMappings: [mapping({ concept: { conceptId: 'etymology:borrowings', label: 'borrowed-word histories' } })],
      notForMeMappings: [mapping({
        mappingId: 'avoid-one-direction',
        concept: { conceptId: 'etymology:latin-loans', label: 'Latin loanword history' },
        stance: 'avoid',
        weight: 0.12,
        scope: { mode: 'play', expiresAt: '2026-03-01T12:00:00.000Z' }
      })]
    });
    const evidence = reflectionResponseToEvidence(value, response({ response: 'not-for-me' }));
    expect(evidence.mappings).toEqual({ 'not-for-me': value.notForMeMappings });
    expect(evidence.mappings['not-for-me']?.[0]?.concept.conceptId).toBe('etymology:latin-loans');
    expect(evidence.mappings['not-for-me']?.[0]?.stance).toBe('avoid');
    expect(Object.hasOwn(evidence.mappings, 'keep')).toBe(false);
  });

  it('records pass with exactly zero preference maps', () => {
    const evidence = reflectionResponseToEvidence(card(), response({ response: 'pass' }));
    expect(evidence.mappings).toEqual({});
    expect(evidence.response).toBe('pass');
    expect(validateEpistemeEvidence(evidence)).toBe(true);
  });

  it('caps each clear card response at .20 across all mappings', () => {
    const tooMuch = card({
      keepMappings: [
        mapping({ mappingId: 'one', weight: 0.13 }),
        mapping({ mappingId: 'two', weight: 0.08, concept: { conceptId: 'wordplay', label: 'wordplay' } })
      ]
    });
    expect(validateReflectionCard(tooMuch)).toBe(false);
  });

  it('caps ambiguous cards at .05, including negative responses', () => {
    const valid = card({
      ambiguity: 'ambiguous',
      keepMappings: [mapping({ weight: AMBIGUOUS_REFLECTION_BUDGET })],
      notForMeMappings: [mapping({
        mappingId: 'avoid-ambiguous',
        stance: 'avoid',
        weight: AMBIGUOUS_REFLECTION_BUDGET,
        scope: { mode: 'play', expiresAt: '2026-03-01T12:00:00.000Z' }
      })]
    });
    const invalid = card({
      ambiguity: 'ambiguous',
      keepMappings: [mapping({ weight: AMBIGUOUS_REFLECTION_BUDGET + 0.001 })]
    });
    expect(validateReflectionCard(valid)).toBe(true);
    expect(validateReflectionCard(invalid)).toBe(false);
  });

  it('rejects broad or durable negative maps and more than one negative target', () => {
    const broad = card({ notForMeMappings: [mapping({
      mappingId: 'broad-avoid', stance: 'avoid', scope: {}
    })] });
    const permanent = card({ notForMeMappings: [mapping({
      mappingId: 'permanent-avoid', stance: 'avoid', scope: { mode: 'play' }
    })] });
    const longLived = card({ notForMeMappings: [mapping({
      mappingId: 'long-avoid', stance: 'avoid', scope: { mode: 'play', expiresAt: '2026-05-01T12:00:00.000Z' }
    })] });
    const multiple = card({ notForMeMappings: [
      mapping({ mappingId: 'avoid-a', stance: 'avoid', scope: { mode: 'play', expiresAt: '2026-03-01T12:00:00.000Z' } }),
      mapping({ mappingId: 'avoid-b', stance: 'avoid', weight: 0.1, scope: { mode: 'play', expiresAt: '2026-03-01T12:00:00.000Z' } })
    ] });
    expect(validateReflectionCard(broad)).toBe(false);
    expect(validateReflectionCard(permanent)).toBe(false);
    expect(validateReflectionCard(longLived)).toBe(false);
    expect(validateReflectionCard(multiple)).toBe(false);
  });

  it('rejects hidden fields, duplicate map IDs, and unsupported map polarity', () => {
    expect(validateReflectionCard({ ...card(), swipeSpeed: 900 })).toBe(false);
    expect(validateReflectionCard(card({ notForMeMappings: [mapping({
      mappingId: 'keep-etymology', stance: 'avoid', scope: { mode: 'play', expiresAt: '2026-03-01T12:00:00.000Z' }
    })] }))).toBe(false);
    expect(validateReflectionCard(card({ notForMeMappings: [mapping({
      mappingId: 'wrong-direction', stance: 'seek', scope: { mode: 'play', expiresAt: '2026-03-01T12:00:00.000Z' }
    })] }))).toBe(false);
  });

  it('requires exact approved versions before accepting a response', () => {
    const proposal = card({
      source: 'model',
      status: 'pending',
      generationReceipt: {
        generationId: 'generation-1', model: 'local-model', promptVersion: 'cards-v1',
        generatedAt: createdAt, reviewStatus: 'pending'
      }
    });
    expect(validateReflectionCard(proposal)).toBe(true);
    expect(isPlayableReflectionCard(proposal)).toBe(false);
    expect(validateReflectionResponse(response(), proposal)).toBe(false);

    expect(validateReflectionResponse(response({ cardVersion: 2 }), card())).toBe(false);
    expect(validateReflectionResponse({ ...response(), elapsedMs: 4 }, card())).toBe(false);
    expect(() => reflectionResponseToEvidence(card(), response({ cardVersion: 2 }))).toThrow(/exact card version/);
  });

  it('supports reversible undo/restore links to the original evidence id', () => {
    const retract: ReflectionResponseActionV1 = {
      schemaVersion: 1,
      actionId: 'undo-1',
      targetResponseId: 'response-1',
      recordedAt: '2026-01-03T12:00:00.000Z',
      action: 'retract',
      reason: 'Changed my mind'
    };
    const restore = { ...retract, actionId: 'redo-1', action: 'restore' as const };
    expect(validateReflectionResponseAction(retract)).toBe(true);
    expect(reflectionActionToEvidenceAction(retract)).toMatchObject({
      targetEvidenceId: 'response-1', action: 'retract'
    });
    expect(reflectionActionToEvidenceAction(restore)).toMatchObject({
      targetEvidenceId: 'response-1', action: 'restore'
    });
    expect(validateReflectionResponseAction({ ...retract, targetResponseId: '' })).toBe(false);
  });
});
