// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import {
  createPublicPuzzleDocumentV2,
  validatePuzzleDocumentV2,
} from '@crossword/domain';
import reviewCandidateFixture from '../../../../tests/fixtures/personalized-review-v2.json';
import {
  adaptPublishedPuzzleV2Envelope,
  projectValidatedPuzzleDocumentV2,
} from './puzzleV2Adapter.js';

const reviewCandidate = reviewCandidateFixture;
const fixtureOnlyReceipt = digest => ({
  version: 'puzzle-v2-publication-receipt-v1',
  candidateDigest: digest,
  publishedAt: '2026-09-26T12:00:00Z',
  reviewerId: 'synthetic-fixture-reviewer',
});

beforeAll(() => {
  vi.stubGlobal('crypto', webcrypto);
});

function envelopeFor(puzzle = structuredClone(reviewCandidate), overrides = {}) {
  const candidateDigest = puzzle.integrity.value;
  return {
    status: 'published',
    candidateDigest,
    puzzle,
    publicationReceipt: fixtureOnlyReceipt(candidateDigest),
    ...overrides,
  };
}

describe('published PuzzleDocumentV2 solver adapter', () => {
  it('rejects the valid synthetic review candidate even when wrapped in a spoofed published envelope', async () => {
    expect(reviewCandidate.quality.verdict).toBe('review');
    expect(await validatePuzzleDocumentV2(reviewCandidate)).toEqual({ valid: true, issues: [] });

    // Public-copy construction removes the private profile projection and
    // reseals the fixture, so this exercises the quality gate independently.
    const publicReviewFixture = await createPublicPuzzleDocumentV2(reviewCandidate);
    expect(publicReviewFixture.quality.verdict).toBe('review');
    await expect(adaptPublishedPuzzleV2Envelope(envelopeFor(publicReviewFixture)))
      .rejects.toMatchObject({ code: 'puzzle-not-accepted' });
  });

  it('rejects a document containing private profile-projection metadata', async () => {
    expect(reviewCandidate.receipt.profileProjection).toBeDefined();
    expect(await validatePuzzleDocumentV2(reviewCandidate)).toEqual({ valid: true, issues: [] });

    await expect(adaptPublishedPuzzleV2Envelope(envelopeFor()))
      .rejects.toMatchObject({ code: 'private-generation-receipt' });
  });

  it('rejects every non-published status', async () => {
    await expect(adaptPublishedPuzzleV2Envelope(
      envelopeFor(reviewCandidate, { status: 'review' }),
    )).rejects.toMatchObject({ code: 'not-published' });
  });

  it('requires the exact publication receipt shape', async () => {
    const missing = envelopeFor();
    delete missing.publicationReceipt;
    await expect(adaptPublishedPuzzleV2Envelope(missing))
      .rejects.toMatchObject({ code: 'invalid-envelope' });

    const extra = envelopeFor();
    extra.publicationReceipt.untrusted = true;
    await expect(adaptPublishedPuzzleV2Envelope(extra))
      .rejects.toMatchObject({ code: 'invalid-publication-receipt' });
  });

  it('binds the receipt and envelope to the exact candidate digest', async () => {
    const receiptMismatch = envelopeFor();
    receiptMismatch.publicationReceipt.candidateDigest = `sha256:${'0'.repeat(64)}`;
    await expect(adaptPublishedPuzzleV2Envelope(receiptMismatch))
      .rejects.toMatchObject({ code: 'publication-receipt-mismatch' });

    const candidateMismatch = envelopeFor();
    candidateMismatch.candidateDigest = `sha256:${'0'.repeat(64)}`;
    candidateMismatch.publicationReceipt.candidateDigest = candidateMismatch.candidateDigest;
    await expect(adaptPublishedPuzzleV2Envelope(candidateMismatch))
      .rejects.toMatchObject({ code: 'candidate-digest-mismatch' });
  });

  it('rejects a tampered document before projecting it', async () => {
    const tampered = structuredClone(reviewCandidate);
    tampered.clues[0].text += ' altered';
    await expect(adaptPublishedPuzzleV2Envelope(envelopeFor(tampered)))
      .rejects.toMatchObject({ code: 'invalid-puzzle-document' });
  });

  it('projects every entry and clue ID, answer and coordinate from a real-validated review fixture', async () => {
    // The domain validator correctly forbids synthetic-source content from
    // receiving quality=accept. Exercise mapping separately with its internal
    // helper and a real-valid review candidate; this is not publication proof.
    expect(await validatePuzzleDocumentV2(reviewCandidate)).toEqual({ valid: true, issues: [] });
    const model = projectValidatedPuzzleDocumentV2(
      reviewCandidate,
      reviewCandidate.integrity.value,
    );
    const cellsById = new Map(reviewCandidate.cells.map(cell => [cell.id, cell]));
    const cluesByEntryId = new Map(reviewCandidate.clues.map(clue => [clue.entryId, clue]));
    const mappedByV2Id = new Map(model.crossword.map(entry => [entry.v2_entry_id, entry]));
    const idsByV2Id = new Map(model.idMappings.map(mapping => [mapping.v2EntryId, mapping]));

    expect(model.crossword).toHaveLength(reviewCandidate.entries.length);
    expect(model.idMappings).toHaveLength(reviewCandidate.entries.length);
    for (const sourceEntry of reviewCandidate.entries) {
      const clue = cluesByEntryId.get(sourceEntry.id);
      const firstCell = cellsById.get(sourceEntry.cellIds[0]);
      const mappedEntry = mappedByV2Id.get(sourceEntry.id);
      const solverEntryId = `${sourceEntry.direction}-${sourceEntry.number}`;

      expect(clue).toBeDefined();
      expect(firstCell).toBeDefined();
      expect(mappedEntry).toBeDefined();
      expect(mappedEntry).toMatchObject({
        clue_number: sourceEntry.number,
        clue_text: clue.text,
        direction: sourceEntry.direction,
        start_x: firstCell.column,
        start_y: firstCell.row,
        solver_entry_id: solverEntryId,
        v2_entry_id: sourceEntry.id,
        clue_variant_id: clue.clueVariantId,
      });
      expect(mappedEntry.characters.map(character => character.letters).join(''))
        .toBe(sourceEntry.answer);
      expect(idsByV2Id.get(sourceEntry.id)).toEqual({
        solverEntryId,
        v2EntryId: sourceEntry.id,
        clueVariantId: clue.clueVariantId,
      });
    }

    expect(model.crossword.some(entry => entry.direction === 'down' && entry.start_x > 0)).toBe(true);
    expect(model.crossword.some(entry => entry.start_y > 0)).toBe(true);
    expect(model.grid).toHaveLength(15);
    expect(model.grid.flat()).toHaveLength(225);
    for (const cell of reviewCandidate.cells) {
      expect(model.grid[cell.row][cell.column]).toBe(cell.block ? null : '');
    }
  });

  it('indexes grid cells by coordinates and excludes private generation metadata from the projection', async () => {
    expect(await validatePuzzleDocumentV2(reviewCandidate)).toEqual({ valid: true, issues: [] });
    const shuffled = {
      ...reviewCandidate,
      cells: [...reviewCandidate.cells].reverse(),
    };
    // The adapter itself requires the schema-valid row-major document. This
    // direct projection check guards its geometry mapping against array-order
    // assumptions if the validated contract ever changes.
    expect((await validatePuzzleDocumentV2(shuffled)).issues.some(issue => issue.code === 'cell-order'))
      .toBe(true);
    const projected = projectValidatedPuzzleDocumentV2(shuffled, reviewCandidate.integrity.value);
    const ordered = projectValidatedPuzzleDocumentV2(reviewCandidate, reviewCandidate.integrity.value);

    expect(projected.grid).toEqual(ordered.grid);
    expect(projected).not.toHaveProperty('receipt');
    expect(projected).not.toHaveProperty('profileProjection');
    expect(JSON.stringify(projected)).not.toContain(reviewCandidate.receipt.profileProjection.digest);
    expect(JSON.stringify(projected)).not.toContain('profileProjection');
  });
});
