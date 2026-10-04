import { describe, expect, it } from 'vitest';
import {
  computePuzzleDocumentV2Digest,
  createPublicPuzzleDocumentV2,
  sealPuzzleDocumentV2,
  validatePuzzleDocumentV2,
  type PuzzleDocumentV2,
  type PuzzleV2ClueProvenance,
  type PuzzleV2Entry,
} from './puzzleV2.js';

const HASH = '1'.repeat(64);
type MutableRecord = Record<string, unknown>;
type MutableDraft = MutableRecord & {
  cells: MutableRecord[];
  entries: MutableRecord[];
  clues: MutableRecord[];
  receipt: MutableRecord;
  provenance: MutableRecord & { clues: MutableRecord[]; senses: MutableRecord[] };
  crossingSupport: MutableRecord & { uncertainty: MutableRecord };
  quality: MutableRecord;
};

function makeOpenGridDraft(contentClass: 'synthetic' | 'public' = 'synthetic') {
  const cells = Array.from({ length: 225 }, (_, index) => {
    const row = Math.floor(index / 15);
    const column = index % 15;
    return {
      id: `r${row}c${column}`,
      row,
      column,
      block: false,
      circled: false,
      shaded: false,
      token: 'A',
    };
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

  const sourceId = 'fixture-source';
  const source = {
    sourceId,
    version: '1',
    artifactSha256: HASH,
    spdx: 'CC0-1.0',
    attribution: 'Puzzle V2 test fixture',
    contentClass,
  } as const;
  const clues = entries.map((entry) => {
    const clueVariantId = `clue-${entry.id}`;
    const sourceClueId = `source-${clueVariantId}`;
    const text = 'A test definition';
    const evidenceRefs = [`fixture:clue-review/${clueVariantId}`];
    const linkedEvidenceProvenance = {
      source,
      evidenceRefs: [`fixture:sense/${entry.senseId}`],
      reviewerId: 'fixture-lexicon-editor',
      reviewedAt: '2026-09-25',
    };
    return {
      clue: {
        clueVariantId,
        sourceClueId,
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
        sourceClueId,
        entryId: entry.id,
        senseIds: [entry.senseId],
        factIds: [],
        sourceIds: [sourceId],
        evidenceKind: 'sense' as const,
        evidenceId: entry.senseId,
        evidenceRefs,
        evidenceProvenance: linkedEvidenceProvenance,
        reviewerId: 'fixture-clue-editor',
        reviewedAt: '2026-09-26',
        semanticTruthStatus: 'not-established-by-grammar-validator' as const,
      } satisfies PuzzleV2ClueProvenance,
    };
  });
  const edges = entries
    .filter((entry) => entry.direction === 'across')
    .flatMap((across) => entries
      .filter((entry) => entry.direction === 'down')
      .map((down) => ({
        acrossEntryId: across.id,
        downEntryId: down.id,
        cellId: across.cellIds.find((cellId) => down.cellIds.includes(cellId))!,
        score: 0.8,
        confidence: 0.5,
      })));

  return {
    schemaVersion: 2 as const,
    id: 'puzzle-v2-fixture',
    seed: 'seed-1',
    title: 'Fixture',
    subtitle: '',
    width: 15 as const,
    height: 15 as const,
    language: 'en',
    languagePolicy: {
      version: 'ascii-uppercase-v1' as const,
      cellTokenPolicy: 'single-ascii-letter-v1' as const,
    },
    cells,
    entries,
    clues: clues.map((row) => row.clue),
    mechanics: [],
    provenance: {
      sources: [{ sourceId, version: source.version, artifactSha256: HASH, spdx: source.spdx, attribution: source.attribution, contentClass }],
      lexemes: entries.map((entry) => ({ id: entry.lexemeId, sourceIds: [sourceId] })),
      senses: entries.map((entry) => ({
        id: entry.senseId,
        lexemeId: entry.lexemeId,
        sourceIds: [sourceId],
        evidenceProvenance: {
          source,
          evidenceRefs: [`fixture:sense/${entry.senseId}`],
          reviewerId: 'fixture-lexicon-editor',
          reviewedAt: '2026-09-25',
        },
      })),
      facts: [],
      clues: clues.map((row) => row.provenance),
    },
    topology: {
      width: 15 as const,
      height: 15 as const,
      blockedCellIds: [],
      minEntryLength: 3 as const,
      numbering: 'standard-row-major-v1' as const,
    },
    receipt: {
      constructionSeed: 'seed-1',
      recipe: { id: 'wednesday-balanced', version: '1', weekday: 'Wednesday' as const },
      runtime: { id: 'xfill', version: '0.1', artifactDigest: HASH },
      validators: [{ id: 'puzzle-v2-validator', version: '1' }],
      generatedAt: '2026-09-26T10:00:00Z',
    },
    crossingSupport: {
      version: 'crossing-support-v1',
      edges,
      minimumScore: 0.8,
      meanScore: 0.8,
      uncertainty: { level: 'medium' as const, notes: 'Synthetic fixture estimate.' },
    },
    quality: {
      verdict: 'review' as const,
      reasons: ['Semantic truth has not been independently established.'],
    },
  };
}

async function sealDraft(draft: ReturnType<typeof makeOpenGridDraft>): Promise<PuzzleDocumentV2> {
  return sealPuzzleDocumentV2(draft);
}

async function revalidateAfterEdit(puzzle: PuzzleDocumentV2, edit: (copy: MutableDraft) => void) {
  const copy = structuredClone(puzzle) as unknown as MutableDraft;
  edit(copy);
  const resealed = await sealDraft(copy as unknown as ReturnType<typeof makeOpenGridDraft>);
  return validatePuzzleDocumentV2(resealed);
}

describe('PuzzleDocumentV2', () => {
  it('accepts a fully numbered 15x15 one-letter grid with grammar and source-linked clue provenance', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const validation = await validatePuzzleDocumentV2(puzzle);
    expect(validation).toEqual({ valid: true, issues: [] });
  });

  it('uses canonical sorted-key JSON and verifies the digest across object key order', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const rekeyed = Object.fromEntries(Object.entries(puzzle).reverse());
    await expect(computePuzzleDocumentV2Digest(rekeyed)).resolves.toBe(puzzle.integrity.value);
  });

  it('strips private profile projection metadata before producing a newly digested public copy', async () => {
    const draft = makeOpenGridDraft();
    const puzzle = await sealPuzzleDocumentV2({
      ...draft,
      receipt: { ...draft.receipt, profileProjection: { revision: 7, digest: HASH } },
    } as unknown as Omit<PuzzleDocumentV2, 'integrity'>);
    const publicPuzzle = await createPublicPuzzleDocumentV2(puzzle);
    expect('profileProjection' in publicPuzzle.receipt).toBe(false);
    expect(publicPuzzle.integrity.value).not.toBe(puzzle.integrity.value);
    expect(await validatePuzzleDocumentV2(publicPuzzle)).toEqual({ valid: true, issues: [] });
  });

  it('rejects multi-token/rebus cells even when the document is re-digested', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const result = await revalidateAfterEdit(puzzle, (copy) => { copy.cells[0]!.token = 'AB'; });
    expect(result.issues.some((issue) => issue.code === 'cell-token')).toBe(true);
  });

  it('rejects entries that do not exactly match maximal numbered runs', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const result = await revalidateAfterEdit(puzzle, (copy) => {
      (copy.entries[0]!.cellIds as string[]).pop();
      copy.entries[0]!.answer = 'A'.repeat(14);
    });
    expect(result.issues.some((issue) => issue.code === 'run-mismatch')).toBe(true);
  });

  it('rejects normalized but impossible calendar dates in the generation receipt', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const result = await revalidateAfterEdit(puzzle, (copy) => {
      copy.receipt.generatedAt = '2026-02-30T12:00:00Z';
    });
    expect(result.issues.some((issue) => issue.code === 'receipt')).toBe(true);
  });

  it('rejects cell/entry letter mismatches and incorrect crossing aggregates', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const cellResult = await revalidateAfterEdit(puzzle, (copy) => { copy.cells[0]!.token = 'B'; });
    expect(cellResult.issues.some((issue) => issue.code === 'entry-answer')).toBe(true);

    const aggregateResult = await revalidateAfterEdit(puzzle, (copy) => { copy.crossingSupport.meanScore = 0.7; });
    expect(aggregateResult.issues.some((issue) => issue.code === 'crossing-aggregate')).toBe(true);
  });

  it('does not let structural letter agreement claim calibrated player support', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const result = await revalidateAfterEdit(puzzle, (copy) => {
      copy.crossingSupport.version = 'structural-letter-agreement-v1';
      const edges = copy.crossingSupport.edges as MutableRecord[];
      edges.forEach((edge) => { edge.score = 1; edge.confidence = 1; });
      copy.crossingSupport.minimumScore = 1;
      copy.crossingSupport.meanScore = 1;
      copy.crossingSupport.uncertainty.level = 'medium';
    });
    expect(result.issues.some((issue) => issue.code === 'structural-crossing-estimate')).toBe(true);
  });

  it('rejects clue grammar copies that disagree with the visible clue', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const result = await revalidateAfterEdit(puzzle, (copy) => { (copy.clues[0]!.grammar as MutableRecord).clueText = 'Different words'; });
    expect(result.issues.some((issue) => issue.code === 'grammar-link')).toBe(true);
  });

  it('rejects a clue whose exact sense/fact support differs from its provenance', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const result = await revalidateAfterEdit(puzzle, (copy) => { copy.provenance.clues[0]!.senseIds = ['unknown-sense']; });
    expect(result.issues.some((issue) => issue.code === 'clue-evidence-mismatch')).toBe(true);
  });

  it('rejects numeric primary evidence IDs instead of coercing them to strings', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const result = await revalidateAfterEdit(puzzle, (copy) => {
      copy.entries[0]!.senseId = '1';
      copy.provenance.senses[0]!.id = '1';
      (copy.clues[0]!.support as MutableRecord).senseIds = ['1'];
      copy.provenance.clues[0]!.senseIds = ['1'];
      copy.provenance.clues[0]!.evidenceId = 1;
    });
    expect(result.issues.some((issue) => issue.code === 'evidence-id')).toBe(true);
  });

  it('accepts copied verified fact provenance only when the fact links to the entry lexeme', async () => {
    const draft = structuredClone(makeOpenGridDraft()) as unknown as MutableDraft;
    const entry = draft.entries[0]!;
    const linkedEvidenceProvenance = structuredClone(
      (draft.provenance.senses as MutableRecord[])[0]!.evidenceProvenance,
    );
    const fact = {
      id: 'fact-for-entry-1',
      lexemeId: entry.lexemeId,
      sourceIds: ['fixture-source'],
      review: 'verified',
      evidenceProvenance: linkedEvidenceProvenance,
    };
    const clue = draft.clues[0]!;
    (clue.support as MutableRecord).factIds = [fact.id];
    const clueProvenance = draft.provenance.clues[0]!;
    clueProvenance.factIds = [fact.id];
    clueProvenance.evidenceKind = 'fact';
    clueProvenance.evidenceId = fact.id;
    clueProvenance.evidenceProvenance = linkedEvidenceProvenance;
    (draft.provenance as MutableRecord).facts = [fact];
    const factPuzzle = await sealDraft(draft as unknown as ReturnType<typeof makeOpenGridDraft>);
    expect(await validatePuzzleDocumentV2(factPuzzle)).toEqual({ valid: true, issues: [] });

    const wrongLexeme = await revalidateAfterEdit(factPuzzle, (copy) => {
      (copy.provenance.facts as MutableRecord[])[0]!.lexemeId = 'unknown-lexeme';
    });
    expect(wrongLexeme.issues.some((issue) => issue.code === 'fact-support-link')).toBe(true);
  });

  it('rejects unknown or mismatched source pins in copied clue provenance', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const result = await revalidateAfterEdit(puzzle, (copy) => {
      const evidenceProvenance = copy.provenance.clues[0]!.evidenceProvenance as MutableRecord;
      (evidenceProvenance.source as MutableRecord).artifactSha256 = '2'.repeat(64);
    });
    expect(result.issues.some((issue) => issue.code === 'evidence-source-link')).toBe(true);
  });

  it('rejects an accept verdict without a complete semantic attestation', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const result = await revalidateAfterEdit(puzzle, (copy) => { copy.quality.verdict = 'accept'; });
    expect(result.issues.some((issue) => issue.code === 'acceptance-gate')).toBe(true);
  });

  it('rejects accept for synthetic sources or high uncertainty, even with an attestation', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const syntheticResult = await revalidateAfterEdit(puzzle, (copy) => {
      copy.quality.verdict = 'accept';
      copy.quality.semanticAttestation = {
        reviewerId: 'editor', reviewedAt: '2026-09-26', clueVariantIds: copy.clues.map((clue) => String(clue.clueVariantId)), sourceIds: ['fixture-source'], evidenceRefs: ['editorial-review-1'],
      };
    });
    expect(syntheticResult.issues.some((issue) => issue.code === 'synthetic-acceptance')).toBe(true);

    const publicPuzzle = await sealDraft(makeOpenGridDraft('public'));
    const uncertainResult = await revalidateAfterEdit(publicPuzzle, (copy) => {
      copy.quality.verdict = 'accept';
      copy.quality.semanticAttestation = {
        reviewerId: 'editor', reviewedAt: '2026-09-26', clueVariantIds: copy.clues.map((clue) => String(clue.clueVariantId)), sourceIds: ['fixture-source'], evidenceRefs: ['editorial-review-1'],
      };
      copy.crossingSupport.uncertainty.level = 'high';
    });
    expect(uncertainResult.issues.some((issue) => issue.code === 'acceptance-gate')).toBe(true);
  });

  it('accepts only a public-source puzzle with complete semantic review and adequate crossing certainty', async () => {
    const draft = makeOpenGridDraft('public');
    const puzzle = await sealPuzzleDocumentV2({
      ...draft,
      quality: {
        verdict: 'accept',
        reasons: ['Clues reviewed against their cited sources.'],
        semanticAttestation: {
          reviewerId: 'editor',
          reviewedAt: '2026-09-26',
          clueVariantIds: draft.clues.map((clue) => clue.clueVariantId),
          sourceIds: ['fixture-source'],
          evidenceRefs: ['editorial-review-1'],
        },
      },
    } as unknown as Omit<PuzzleDocumentV2, 'integrity'>);
    expect(await validatePuzzleDocumentV2(puzzle)).toEqual({ valid: true, issues: [] });
  });

  it('rejects digest tampering and unknown schema fields', async () => {
    const puzzle = await sealDraft(makeOpenGridDraft());
    const tampered = structuredClone(puzzle);
    (tampered as { title: string }).title = 'Changed';
    expect((await validatePuzzleDocumentV2(tampered)).issues.some((issue) => issue.code === 'integrity-mismatch')).toBe(true);

    const result = await revalidateAfterEdit(puzzle, (copy) => { copy.experimental = true; });
    expect(result.issues.some((issue) => issue.code === 'shape')).toBe(true);
  });
});
