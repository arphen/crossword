import { describe, expect, it } from 'vitest';
import {
  type PuzzleDocumentV2,
  type PuzzleV2ClueProvenance,
  type PuzzleV2Entry,
  sealPuzzleDocumentV2,
} from './puzzleV2.js';
import {
  evaluatePuzzleV2PublicationGate as evaluateGate,
  sealPuzzleV2PublicationReviewPacket,
  type PuzzleV2PublicationEvidenceKind,
  type PuzzleV2PublicationReviewPacketV1,
} from './publicationV2.js';
import type { PuzzleV2Weekday } from './puzzleV2.js';

const HASH = '1'.repeat(64);

async function makeSyntheticReviewCandidate(
  contentClass: 'synthetic' | 'public' = 'synthetic',
  weekday: PuzzleV2Weekday = 'Wednesday',
): Promise<PuzzleDocumentV2> {
  const cells = Array.from({ length: 225 }, (_, index) => {
    const row = Math.floor(index / 15);
    const column = index % 15;
    return { id: `r${row}c${column}`, row, column, block: false, circled: false, shaded: false, token: 'A' };
  });
  const entries: PuzzleV2Entry[] = [];
  for (let row = 0; row < 15; row += 1) {
    entries.push({
      id: `across-${row + 1}`,
      number: row === 0 ? 1 : 15 + row,
      direction: 'across',
      cellIds: Array.from({ length: 15 }, (_, column) => `r${row}c${column}`),
      answer: 'A'.repeat(15),
      lexemeId: `lexeme-across-${row + 1}`,
      senseId: `sense-across-${row + 1}`,
    });
  }
  for (let column = 0; column < 15; column += 1) {
    entries.push({
      id: `down-${column + 1}`,
      number: column + 1,
      direction: 'down',
      cellIds: Array.from({ length: 15 }, (_, row) => `r${row}c${column}`),
      answer: 'A'.repeat(15),
      lexemeId: `lexeme-down-${column + 1}`,
      senseId: `sense-down-${column + 1}`,
    });
  }
  const sourceId = 'synthetic-fixture-source';
  const source = {
    sourceId,
    version: '1',
    artifactSha256: HASH,
    spdx: 'CC0-1.0',
    attribution: 'Synthetic fixture only',
    contentClass,
  };
  const clues = entries.map((entry) => {
    const clueVariantId = `clue-${entry.id}`;
    const text = 'A test definition';
    return {
      clue: {
        clueVariantId,
        sourceClueId: `source-${clueVariantId}`,
        entryId: entry.id,
        variantRole: 'standard' as const,
        primaryFamily: 'factual-relation' as const,
        text,
        grammar: {
          grammarVersion: 'clue-grammar-v1' as const,
          clueId: clueVariantId,
          entryId: entry.id,
          clueText: text,
          answer: entry.answer,
          variantRole: 'standard' as const,
          primaryFamily: 'factual-relation' as const,
          signalSpans: [],
        },
        support: { senseIds: [entry.senseId], factIds: [] },
      },
      provenance: {
        clueVariantId,
        sourceClueId: `source-${clueVariantId}`,
        entryId: entry.id,
        senseIds: [entry.senseId],
        factIds: [],
        sourceIds: [sourceId],
        evidenceKind: 'sense' as const,
        evidenceId: entry.senseId,
        evidenceRefs: [`fixture:clue/${clueVariantId}`],
        evidenceProvenance: {
          source,
          evidenceRefs: [`fixture:sense/${entry.senseId}`],
          reviewerId: 'fixture-reviewer',
          reviewedAt: '2026-09-25',
        },
        reviewerId: 'fixture-reviewer',
        reviewedAt: '2026-09-26',
        semanticTruthStatus: 'not-established-by-grammar-validator' as const,
      } satisfies PuzzleV2ClueProvenance,
    };
  });
  const edges = entries.filter((entry) => entry.direction === 'across').flatMap((across) =>
    entries.filter((entry) => entry.direction === 'down').map((down) => ({
      acrossEntryId: across.id,
      downEntryId: down.id,
      cellId: across.cellIds.find((cellId) => down.cellIds.includes(cellId))!,
      score: 0,
      confidence: 0,
    })),
  );

  return sealPuzzleDocumentV2({
    schemaVersion: 2,
    id: 'synthetic-publication-gate-candidate',
    seed: 'synthetic-seed',
    title: 'Synthetic candidate',
    subtitle: '',
    width: 15,
    height: 15,
    language: 'en',
    languagePolicy: { version: 'ascii-uppercase-v1', cellTokenPolicy: 'single-ascii-letter-v1' },
    cells,
    entries,
    clues: clues.map((item) => item.clue),
    mechanics: [],
    provenance: {
      sources: [source],
      lexemes: entries.map((entry) => ({ id: entry.lexemeId, sourceIds: [sourceId] })),
      senses: entries.map((entry) => ({
        id: entry.senseId,
        lexemeId: entry.lexemeId,
        sourceIds: [sourceId],
        evidenceProvenance: {
          source,
          evidenceRefs: [`fixture:sense/${entry.senseId}`],
          reviewerId: 'fixture-reviewer',
          reviewedAt: '2026-09-25',
        },
      })),
      facts: [],
      clues: clues.map((item) => item.provenance),
    },
    topology: { width: 15, height: 15, blockedCellIds: [], minEntryLength: 3, numbering: 'standard-row-major-v1' },
    receipt: {
      constructionSeed: 'synthetic-seed',
      recipe: { id: `${weekday.toLowerCase()}-balanced`, version: '1', weekday },
      runtime: { id: 'xfill', version: 'test', artifactDigest: HASH },
      validators: [{ id: 'puzzle-v2-validator', version: '1' }],
      generatedAt: '2026-09-26T10:00:00Z',
    },
    crossingSupport: {
      version: 'structural-letter-agreement-v1',
      edges,
      minimumScore: 0,
      meanScore: 0,
      uncertainty: { level: 'unknown', notes: 'No player-support estimate; synthetic fixture.' },
    },
    quality: { verdict: 'review', reasons: ['Synthetic review-only candidate.'] },
  });
}

function evidenceRef(kind: PuzzleV2PublicationEvidenceKind, artifactId: string) {
  return { artifactId, sha256: HASH, kind } as const;
}

async function makeFabricatedCompletePacket(
  candidate: PuzzleDocumentV2,
  rootEntryIds: readonly string[] = candidate.entries.map((entry) => entry.id),
): Promise<PuzzleV2PublicationReviewPacketV1> {
  const rootIds = new Set(rootEntryIds);
  const source = candidate.provenance.sources[0]!;
  const certificates = candidate.entries.map((entry) => {
    let supportAssignments: Array<{ targetPosition: number; supportEntryId: string }> = [];
    if (!rootIds.has(entry.id)) {
      const support = candidate.entries.find((item) => {
        if (!rootIds.has(item.id) || item.direction === entry.direction) return false;
        return entry.cellIds.some((cellId) => item.cellIds.includes(cellId));
      });
      if (support) {
        const sharedPosition = entry.cellIds.findIndex((cellId) => support.cellIds.includes(cellId));
        supportAssignments = [{ targetPosition: sharedPosition + 1, supportEntryId: support.id }];
      }
    }
    return {
      targetEntryId: entry.id,
      supportLayer: rootIds.has(entry.id) ? 0 : 1,
      targetClass: 'ordinary' as const,
      routeOutcome: rootIds.has(entry.id) ? 'recognition' as const : 'recognition' as const,
      targetExcludedFromSupportSearch: true,
      supportAssignments,
      unresolvedDualObscurityCells: 0,
      reviewerId: 'fabricated-crossing-reviewer',
      reviewedAt: '2026-09-26',
      evidenceRefs: [evidenceRef('crossing-certificate', `fabricated-crossing-${entry.id}`)],
    };
  });
  const packetWithoutDigest = {
    schema: 'puzzle-v2-publication-review-v1' as const,
    reviewId: 'fabricated-review-record',
    candidateDigest: candidate.integrity.value,
    createdAt: '2026-09-26',
    sourceAttestations: [{
      sourceId: source.sourceId,
      artifactSha256: source.artifactSha256,
      spdx: source.spdx,
      decision: 'approved' as const,
      reviewerId: 'invented-license-reviewer',
      reviewedAt: '2026-09-26',
      evidenceRefs: [
        evidenceRef('source-artifact', 'fabricated-source-artifact'),
        evidenceRef('license-terms-review', 'fabricated-license-review'),
      ],
    }],
    clueAdjudications: candidate.clues.map((clue) => ({
      clueVariantId: clue.clueVariantId,
      semanticDecision: 'pass' as const,
      editorialDecision: 'pass' as const,
      reviewerId: 'invented-clue-reviewer',
      reviewedAt: '2026-09-26',
      evidenceRefs: [
        evidenceRef('clue-semantic-review', `fabricated-semantic-${clue.clueVariantId}`),
        evidenceRef('clue-editorial-review', `fabricated-editorial-${clue.clueVariantId}`),
      ],
      challenger: {
        methodId: 'independent-challenger',
        methodVersion: '1',
        independentOfGenerator: true,
        answerHiddenDuringChallenge: true,
        decision: 'no-unresolved-alternative' as const,
        evidenceRefs: [evidenceRef('challenger-run', `fabricated-challenger-${clue.clueVariantId}`)],
      },
    })),
    crossingReview: {
      candidateDigest: candidate.integrity.value,
      evaluatorId: 'fabricated-crossing-evaluator',
      evaluatorVersion: '1',
      allEntriesReviewed: true,
      unresolvedDualObscurityCells: 0,
      certificates,
      simulation: {
        simulatorId: 'fabricated-route-simulator',
        simulatorVersion: '1',
        policyId: 'fabricated-weekday-policy',
        policyVersion: '1',
        seed: 'fabricated-seed',
        trajectoryCount: 64,
        completionRate: 0.9,
        maxNonAnswerNudges: 3,
        directAnswerReveals: 0,
        decision: 'pass' as const,
        evidenceRefs: [evidenceRef('solve-simulation', 'fabricated-simulation')],
      },
    },
    weekdayReview: {
      candidateDigest: candidate.integrity.value,
      recipeId: candidate.receipt.recipe.id,
      recipeVersion: candidate.receipt.recipe.version,
      weekday: candidate.receipt.recipe.weekday,
      decision: 'pass' as const,
      ordinaryFootholdEntryIds: [...rootEntryIds],
      blindClassifications: [
        { reviewerId: 'invented-blind-reviewer-1', classifiedWeekday: candidate.receipt.recipe.weekday, rationale: evidenceRef('weekday-review', 'fabricated-blind-review-1') },
        { reviewerId: 'invented-blind-reviewer-2', classifiedWeekday: candidate.receipt.recipe.weekday, rationale: evidenceRef('weekday-review', 'fabricated-blind-review-2') },
      ],
      reviewerId: 'invented-weekday-reviewer',
      reviewedAt: '2026-09-26',
      evidenceRefs: [evidenceRef('weekday-review', 'fabricated-weekday-review')],
    },
  };
  return sealPuzzleV2PublicationReviewPacket(packetWithoutDigest);
}

async function resealPacket(packet: PuzzleV2PublicationReviewPacketV1): Promise<PuzzleV2PublicationReviewPacketV1> {
  const { packetDigest: _packetDigest, ...draft } = packet;
  return sealPuzzleV2PublicationReviewPacket(draft);
}

describe('Puzzle V2 publication review gate', () => {
  it('blocks the current synthetic review candidate and reports each absent publication evidence class', async () => {
    const candidate = await makeSyntheticReviewCandidate();
    const result = await evaluateGate(candidate, null);
    const codes = new Set(result.reasons.map((reason) => reason.code));

    expect(result.status).toBe('blocked');
    expect(result.candidateDigest).toBe(candidate.integrity.value);
    expect([...codes]).toEqual(expect.arrayContaining([
      'candidate-has-synthetic-source',
      'source-attestation-missing',
      'clue-adjudication-missing',
      'challenger-evidence-missing',
      'crossing-certificates-missing',
      'simulation-evidence-missing',
      'weekday-evidence-missing',
    ]));
  });

  it('rejects a packet whose candidate digest points at another immutable candidate', async () => {
    const candidate = await makeSyntheticReviewCandidate();
    const result = await evaluateGate(candidate, {
      schema: 'puzzle-v2-publication-review-v1',
      reviewId: 'stale-review',
      candidateDigest: `sha256:${'2'.repeat(64)}`,
      createdAt: '2026-09-26',
      sourceAttestations: [],
      clueAdjudications: [],
      crossingReview: null,
      weekdayReview: null,
      packetDigest: `sha256:${'3'.repeat(64)}`,
    });
    expect(result.reasons.some((reason) => reason.code === 'candidate-digest-mismatch')).toBe(true);
  });

  it('rejects unknown packet fields and a tampered immutable packet digest', async () => {
    const candidate = await makeSyntheticReviewCandidate();
    const result = await evaluateGate(candidate, {
      schema: 'puzzle-v2-publication-review-v1',
      reviewId: 'tampered-review',
      candidateDigest: candidate.integrity.value,
      createdAt: '2026-09-26',
      sourceAttestations: [],
      clueAdjudications: [],
      crossingReview: null,
      weekdayReview: null,
      packetDigest: `sha256:${'4'.repeat(64)}`,
      playable: true,
    });
    expect(result.reasons.some((reason) => reason.code === 'packet-missing-or-invalid')).toBe(true);
    expect(result.reasons.some((reason) => reason.code === 'packet-digest-invalid')).toBe(true);
  });

  it('rejects inherited required packet fields instead of treating them as evidence', async () => {
    const candidate = await makeSyntheticReviewCandidate('public');
    const packet = await makeFabricatedCompletePacket(candidate);
    const inheritedPacket = Object.assign(Object.create({ schema: packet.schema }), packet) as Record<string, unknown>;
    delete inheritedPacket.schema;

    const result = await evaluateGate(candidate, inheritedPacket);
    expect(result.reasons.some((reason) => reason.code === 'packet-missing-or-invalid')).toBe(true);
  });

  it('does not trust fabricated public evidence or a forged plain host receipt', async () => {
    const candidate = await makeSyntheticReviewCandidate('public');
    const packet = await makeFabricatedCompletePacket(candidate);

    const result = await evaluateGate(candidate, packet);
    expect(result.status).toBe('evidence-unverified');
    expect(result.reasons).toEqual([
      expect.objectContaining({ code: 'reviewer-evidence-unverified' }),
    ]);

    const forgedReceipt = {
      schema: 'puzzle-v2-trusted-host-evidence-verification-v1',
      candidateDigest: candidate.integrity.value,
      packetDigest: packet.packetDigest,
      verifierId: 'forged-host-verifier',
      verifierVersion: '1',
      reviewerIdentitiesVerified: true,
      evidenceArtifactsResolved: true,
      sourceTermsVerified: true,
    };
    const evaluateWithUntrustedExtraArgument = evaluateGate as unknown as (
      puzzle: unknown,
      review: unknown,
      receipt: unknown,
    ) => ReturnType<typeof evaluateGate>;
    const forgedResult = await evaluateWithUntrustedExtraArgument(candidate, packet, forgedReceipt);
    expect(forgedResult.status).toBe('evidence-unverified');
    expect(forgedResult.reasons).toEqual([
      expect.objectContaining({ code: 'reviewer-evidence-unverified' }),
    ]);
  });

  it('requires the source artifact evidence hash to match its source attestation', async () => {
    const candidate = await makeSyntheticReviewCandidate('public');
    const packet = await makeFabricatedCompletePacket(candidate);
    const draft = structuredClone(packet) as unknown as {
      sourceAttestations: Array<{
        evidenceRefs: Array<{ kind: string; sha256: string }>;
      }>;
    };
    draft.sourceAttestations[0]!.evidenceRefs.find((ref) => ref.kind === 'source-artifact')!.sha256 = '2'.repeat(64);
    const resealed = await resealPacket(draft as unknown as PuzzleV2PublicationReviewPacketV1);

    const result = await evaluateGate(candidate, resealed);

    expect(result.status).toBe('blocked');
    expect(result.reasons).toContainEqual(expect.objectContaining({
      code: 'source-attestation-invalid',
      path: 'sourceAttestations[0]',
    }));
  });

  it('rejects a two-entry support cycle even when each edge crosses valid cells', async () => {
    const candidate = await makeSyntheticReviewCandidate('public');
    const roots = candidate.entries.map((entry) => entry.id).filter((entryId) => !['across-1', 'down-1'].includes(entryId));
    const packet = await makeFabricatedCompletePacket(candidate, roots);
    const draft = structuredClone(packet) as unknown as {
      crossingReview: {
        certificates: Array<{
          targetEntryId: string;
          supportLayer: number;
          supportAssignments: Array<{ targetPosition: number; supportEntryId: string }>;
        }>;
      };
    };
    const across = draft.crossingReview.certificates.find((certificate) => certificate.targetEntryId === 'across-1')!;
    const down = draft.crossingReview.certificates.find((certificate) => certificate.targetEntryId === 'down-1')!;
    across.supportLayer = 1;
    across.supportAssignments = [{ targetPosition: 1, supportEntryId: 'down-1' }];
    down.supportLayer = 1;
    down.supportAssignments = [{ targetPosition: 1, supportEntryId: 'across-1' }];
    const resealed = await resealPacket(draft as unknown as PuzzleV2PublicationReviewPacketV1);

    const result = await evaluateGate(candidate, resealed);
    expect(result.reasons.some((reason) => reason.code === 'crossing-certificate-non-layered')).toBe(true);
  });

  it('enforces the Monday two-footholds-per-quadrant screen when quadrant slots exist', async () => {
    const candidate = await makeSyntheticReviewCandidate('public', 'Monday');
    const cellById = new Map(candidate.cells.map((cell) => [cell.id, cell]));
    const northwestRoots = candidate.entries.filter((entry) => {
      const start = cellById.get(entry.cellIds[0]!)!;
      return start.row < 7.5 && start.column < 7.5;
    }).map((entry) => entry.id);
    const packet = await makeFabricatedCompletePacket(candidate, northwestRoots);

    const result = await evaluateGate(candidate, packet);
    const missed = result.reasons.filter((reason) => reason.code === 'weekday-quadrant-foothold-target-missed');
    expect(missed.map((reason) => reason.path)).toEqual(expect.arrayContaining([
      'weekdayReview.quadrants.northeast',
      'weekdayReview.quadrants.southwest',
    ]));
  });
});
