/**
 * Manifest assembly: accepted fill + topology + clue ladder -> immutable
 * PuzzleDocument.
 *
 * The assembler is the only place that bridges construction values into
 * domain values; it validates the result with `validatePuzzle` before
 * returning, so no invalid grid can become a playable puzzle.
 */
import {
  assertValidPuzzle,
  type Cell,
  type CellId,
  type ClueSet,
  type Entry,
  type EntryId,
  type PuzzleDocument,
  type PuzzleId,
  type ProvenanceRecord
} from '@crossword/domain';

import type { DerivedTopology, TopologyEntry } from '@crossword/construction';

export type AssembleManifestRequest = Readonly<{
  seed: string;
  title: string;
  subtitle: string;
  recipeId: string;
  topology: DerivedTopology;
  /** Slot id -> word. */
  words: Readonly<Record<string, string>>;
  /** Slot id -> staple score (0..1). */
  wordScores: Readonly<Record<string, number>>;
  /** Entry id -> clue ladder (mechanism/text/difficulty). */
  clueVariants: Readonly<Record<string, readonly { mechanism: string; text: string; difficulty: number }[]>>;
  provenanceRecords: readonly ProvenanceRecord[];
  generation: PuzzleDocument['generation'];
  quality: PuzzleDocument['quality'];
  source: PuzzleDocument['createdBy'];
  createdBy: string;
}>;

/**
 * A draft manifest is everything except a verified integrity digest. It is
 * intentionally NOT a PuzzleDocument: only `finalizeIntegrity` — which
 * computes and re-validates the real SHA-256 — can produce one, so a
 * placeholder digest can never reach persistence.
 */
export type DraftManifest = Omit<PuzzleDocument, 'integrity'>;

export function assembleDraftManifest(request: AssembleManifestRequest): DraftManifest {
  const { topology, words, wordScores, clueVariants } = request;
  const width = topology.width;
  const height = topology.height;

  const cells: Cell[] = topology.cells.map((cell) => ({
    id: cell.id as CellId,
    row: cell.row,
    column: cell.column,
    block: cell.block,
    circled: false,
    shaded: false
  }));

  const entries: Entry[] = topology.entries.map((entry) => {
    const word = words[entry.id];
    if (word === undefined || word.length !== entry.length) {
      throw new Error(`Missing fill word for slot ${entry.id}`);
    }
    return {
      id: entry.id as EntryId,
      number: topology.numberByCellId.get(entry.cellIds[0]!) ?? 0,
      direction: entry.direction,
      cellIds: entry.cellIds.map((cellId) => cellId as CellId),
      answer: word,
      clue: primaryClue(clueVariants[entry.id] ?? [], word)
    };
  });

  const clueSets: ClueSet[] = topology.entries.map((entry) => ({
    entryId: entry.id as EntryId,
    variants: (clueVariants[entry.id] ?? []).map((variant) => ({
      mechanism: normalizeMechanism(entry, variant.mechanism),
      text: variant.text,
      difficulty: clamp01(variant.difficulty)
    }))
  }));

  const puzzle: DraftManifest = {
    schemaVersion: 1,
    id: `constructed-${request.seed}` as PuzzleId,
    seed: request.seed,
    title: request.title,
    subtitle: request.subtitle,
    width,
    height,
    cells,
    entries,
    clues: clueSets,
    provenance: {
      source: request.source,
      recipeId: `${request.recipeId}:${topology.templateId}`,
      records: [...request.provenanceRecords]
    },
    generation: request.generation,
    quality: request.quality,
    topology: {
      width,
      height,
      blockedCellIds: topology.blockedCellIds.map((cellId) => cellId as CellId),
      minEntryLength: topology.minEntryLength
    },
    createdBy: request.source
  };

  return puzzle;
}

function primaryClue(variants: readonly { mechanism: string; text: string }[], word: string): string {
  const standard = variants.find((variant) => variant.mechanism === 'standard') ?? variants[0];
  if (standard && standard.text.trim().length > 0) return standard.text;
  return `Answer of ${word.length} letters`;
}

function normalizeMechanism(entry: TopologyEntry, mechanism: string): ClueSet['variants'][number]['mechanism'] {
  return mechanism === 'direct' || mechanism === 'standard' || mechanism === 'oblique' || mechanism === 'nudge'
    ? mechanism
    : 'standard';
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0.5;
  return Math.min(1, Math.max(0, value));
}


function stableReplacer(): (this: unknown, key: string, value: unknown) => unknown {
  const seen = new WeakSet();
  return function (this: unknown, _key: string, value: unknown) {
    if (typeof value === 'object' && value !== null) {
      if (seen.has(value)) return undefined;
      seen.add(value);
      if (!Array.isArray(value)) {
        return Object.fromEntries(
          Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b))
        );
      }
    }
    return value;
  };
}

export async function finalizeIntegrity(draft: DraftManifest): Promise<PuzzleDocument> {
  // Structural validation of the draft before any digest is pinned: an
  // invalid manifest can never be published.
  assertValidPuzzle({ ...draft, integrity: { algorithm: 'sha256', value: 'finalization-pending' } });
  const serialized = JSON.stringify(draft, stableReplacer());
  const data = new TextEncoder().encode(serialized);
  const digest = await crypto.subtle.digest('SHA-256', data);
  const value = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  const finalized: PuzzleDocument = { ...draft, integrity: { algorithm: 'sha256', value } };
  assertValidPuzzle(finalized);
  return finalized;
}
