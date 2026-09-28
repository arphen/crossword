import { beforeEach, expect, it, vi } from 'vitest';
import {
  compactPuzzleForStorage,
  listPrivatePuzzles,
  loadPrivatePuzzle,
  restorePrivatePuzzle,
  savePrivatePuzzle,
} from './privatePuzzleStore';

const profileId = '69d47142-fb69-4134-a96f-c7dab7051661';
const puzzle = {
  metadata: { date: '260927', title: 'Local field', authors: ['Ollama'], width: 3, height: 3 },
  entries: [{ clue_number: 1, clue_text: 'Small feline', direction: 'across', start_x: 0, start_y: 0, characters: [{ letters: 'C' }, { letters: 'A' }, { letters: 'T' }] }],
  puzzleManifest: {
    schemaVersion: 1,
    integrity: { algorithm: 'sha256', value: 'a'.repeat(64) },
  },
  provenance: { source: 'local-ollama-xfill', model: 'gemma4:26b', seed: 42, weekday: 'thursday' },
};

let storage;
beforeEach(() => {
  const values = new Map();
  storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
});

it('saves and restores the same profile-scoped puzzle through solver init', () => {
  expect(savePrivatePuzzle(profileId, puzzle, storage)).toBe(true);
  expect(loadPrivatePuzzle(profileId, storage)?.puzzle).toEqual(puzzle);
  const app = {
    isValidPuzzle: vi.fn(() => true),
    init: vi.fn(),
  };

  expect(restorePrivatePuzzle(app, profileId, storage)).toBe(true);
  expect(app).toMatchObject({
    selectedWeekday: 'thursday',
    lastLoadedWeekday: 'thursday',
    currentPuzzleMetadata: puzzle.metadata,
    currentPuzzleManifest: puzzle.puzzleManifest,
    currentPuzzleProvenance: puzzle.provenance,
    currentPuzzleRequestSeed: 42,
    crossword: puzzle.entries,
  });
  expect(app.init).toHaveBeenCalledOnce();
});

it('does not restore another profile’s puzzle or malformed storage', () => {
  expect(savePrivatePuzzle(profileId, puzzle, storage)).toBe(true);
  expect(loadPrivatePuzzle('another-profile', storage)).toBeNull();
  storage.setItem('crossword.future.private-puzzle.v1:bad', '{');
  expect(loadPrivatePuzzle('bad', storage)).toBeNull();
});

it('persists the reviewed warm-up through the same local recovery shelf', () => {
  const sample = {
    ...puzzle,
    provenance: {
      source: 'reviewed-sample',
      version: 'reviewed-sample-v1',
      sampleId: 'sator-square-v1',
      seed: 0,
      weekday: 'monday',
    },
  };
  expect(savePrivatePuzzle(profileId, sample, storage)).toBe(true);
  expect(loadPrivatePuzzle(profileId, storage)?.puzzle.provenance).toMatchObject({
    source: 'reviewed-sample',
    sampleId: 'sator-square-v1',
  });
});

it('keeps a valid record but refuses to initialize an unsupported solver puzzle', () => {
  expect(savePrivatePuzzle(profileId, puzzle, storage)).toBe(true);
  const app = { isValidPuzzle: vi.fn(() => false), init: vi.fn() };
  expect(restorePrivatePuzzle(app, profileId, storage)).toBe(false);
  expect(app.init).not.toHaveBeenCalled();
});

it('keeps large clue diagnostics out of the browser recovery record', () => {
  const richPuzzle = {
    ...puzzle,
    provenance: {
      ...puzzle.provenance,
      clueBundle: { transcript: 'x'.repeat(600_000) },
      clueQuality: {
        checkedCount: 1,
        issueCount: 0,
        grounding: {
          entryCount: 1,
          entries: [{ id: '1A', riskFlags: ['answer-giveaway'], semanticStatus: 'not-established' }],
        },
      },
    },
  };
  const compact = compactPuzzleForStorage(richPuzzle);
  expect(JSON.stringify(compact).length).toBeLessThan(100_000);
  expect(compact.provenance.clueBundle).toBeUndefined();
  expect(compact.provenance.clueQuality.grounding.entries).toEqual([
    { id: '1A', riskFlags: ['answer-giveaway'], semanticStatus: 'not-established' },
  ]);
  expect(savePrivatePuzzle(profileId, richPuzzle, storage)).toBe(true);
  expect(loadPrivatePuzzle(profileId, storage)?.puzzle.provenance.clueBundle).toBeUndefined();
});

it('keeps a bounded shelf and restores an older exact manifest', () => {
  const makePuzzle = (seed, digest) => ({
    ...puzzle,
    metadata: { ...puzzle.metadata, title: `Local field ${seed}` },
    puzzleManifest: {
      ...puzzle.puzzleManifest,
      id: `manifest-${seed}`,
      integrity: { algorithm: 'sha256', value: digest.repeat(64) },
    },
    provenance: { ...puzzle.provenance, seed },
  });
  const first = makePuzzle(42, 'a');
  const second = makePuzzle(43, 'b');
  expect(savePrivatePuzzle(profileId, first, storage)).toBe(true);
  expect(savePrivatePuzzle(profileId, second, storage)).toBe(true);
  const shelf = listPrivatePuzzles(profileId, storage);
  expect(shelf).toHaveLength(2);
  expect(shelf[0].seed).toBe(43);
  expect(shelf[1].seed).toBe(42);

  const app = {
    isValidPuzzle: vi.fn(() => true),
    init: vi.fn(),
  };
  expect(restorePrivatePuzzle(app, profileId, storage, shelf[1])).toBe(true);
  expect(app.currentPuzzleRequestSeed).toBe(42);
  expect(app.currentPuzzleMetadata.title).toBe('Local field 42');
  expect(loadPrivatePuzzle(profileId, storage).seed).toBe(42);
});
