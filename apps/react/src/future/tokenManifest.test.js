// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import {
  adaptFutureTokenPuzzle,
  createFutureTokenManifestDraft,
  FUTURE_TOKEN_CELL_POLICY,
  FUTURE_TOKEN_MANIFEST_VERSION,
  FUTURE_TOKEN_PRODUCER_VERSION,
  createFutureTokenPuzzleDraft,
  produceFutureTokenPuzzle,
  sealFutureTokenManifest,
  validateFutureTokenManifest,
  verifyFutureTokenManifestIntegrity,
} from './tokenManifest';
import { restorePrivatePuzzle, savePrivatePuzzle } from './privatePuzzleStore';

beforeAll(() => {
  vi.stubGlobal('crypto', webcrypto);
});

function puzzle() {
  return {
    metadata: {
      date: '260927',
      title: 'Token field',
      authors: ['Local model'],
      width: 3,
      height: 3,
    },
    puzzleManifest: {
      schemaVersion: 1,
      integrity: { algorithm: 'sha256', value: 'a'.repeat(64) },
    },
    entries: [
      {
        clue_number: 1,
        clue_text: 'German greeting start',
        direction: 'across',
        start_x: 0,
        start_y: 0,
        characters: [{ letters: 'ß' }, { letters: 'A' }],
      },
      {
        clue_number: 1,
        clue_text: 'A vertical token crossing',
        direction: 'down',
        start_x: 0,
        start_y: 0,
        characters: [{ letters: 'ß' }, { letters: 'O' }],
      },
    ],
  };
}

function nativeTokenPuzzle() {
  return {
    metadata: {
      date: '260927',
      title: 'Token producer field',
      authors: ['Local model'],
      width: 7,
      height: 2,
    },
    puzzleManifest: {
      schemaVersion: 1,
      integrity: { algorithm: 'sha256', value: 'b'.repeat(64) },
    },
    entries: [
      {
        clue_number: 1,
        clue_text: 'A street in German spelling',
        direction: 'across',
        start_x: 0,
        start_y: 0,
      // The producer boundary is a cell-level task: the native ASCII
      // constructor cannot collapse two geometric cells into one rebus cell.
      // It may, however, hand this adapter an explicit canonical `SS` token
      // selected by a future language-aware producer.
      characters: ['S', 'T', 'R', 'A', 'SS', 'E'].map((letters) => ({ letters })),
      },
      {
        clue_number: 1,
        clue_text: 'A crossing',
        direction: 'down',
        start_x: 4,
        start_y: 0,
        characters: [{ letters: 'SS' }, { letters: 'O' }],
      },
    ],
  };
}

describe('future token manifest sidecar', () => {
  it('produces a sealed display-token sidecar from an explicit native fill hint', async () => {
    const source = nativeTokenPuzzle();
    const draft = createFutureTokenPuzzleDraft(source, {
      language: 'de',
      tokenHints: [
        { entryId: 'across-1', cellIndex: 4, displayToken: 'ß' },
      ],
    });
    expect(draft.tokenProducer).toMatchObject({
      version: FUTURE_TOKEN_PRODUCER_VERSION,
      hintCount: 1,
      status: 'explicit-fill-equivalence',
    });
    expect(draft.entries[0].characters.map((item) => item.letters).join('')).toBe(
      'STRAßE',
    );
    expect(draft.entries[1].characters[0].letters).toBe('ß');

    const produced = await produceFutureTokenPuzzle(source, {
      language: 'de',
      tokenHints: [
        { entryId: 'across-1', cellIndex: 4, displayToken: 'ß' },
      ],
    });
    expect(validateFutureTokenManifest(produced.tokenManifest, produced).valid).toBe(
      true,
    );
    expect(produced.tokenManifest.cells.find((cell) => cell.id === 'r0c4')).toMatchObject({
      displayToken: 'ß',
      fillToken: 'SS',
      rebus: true,
    });
    expect(produced.entries[0].characters[4]).toMatchObject({
      letters: 'SS',
      tokenMetadata: { displayToken: 'ß', fillToken: 'SS' },
    });
    expect(produced.entries[1].characters[0].letters).toBe('SS');
  });

  it('rejects a hint that would change the generated fill or geometry', () => {
    expect(() => createFutureTokenPuzzleDraft(nativeTokenPuzzle(), {
      language: 'de',
      tokenHints: [
        { entryId: 'across-1', cellIndex: 3, displayToken: 'ß' },
      ],
    })).toThrow(/fill does not match/i);
  });

  it('seals and round-trips a declared multi-character token without changing V2', async () => {
    const source = puzzle();
    const manifest = await sealFutureTokenManifest(source, { language: 'de' });
    const tokenPuzzle = { ...source, tokenManifest: manifest };

    expect(manifest).toMatchObject({
      schemaVersion: FUTURE_TOKEN_MANIFEST_VERSION,
      languagePolicy: {
        cellTokenPolicy: FUTURE_TOKEN_CELL_POLICY,
        language: 'de',
      },
    });
    expect(manifest.cells.find((cell) => cell.id === 'r0c0')).toMatchObject({
      displayToken: 'ß',
      fillToken: 'SS',
      displayUnits: ['ß'],
      fillUnits: ['S', 'S'],
      rebus: true,
    });
    expect(validateFutureTokenManifest(manifest, source)).toEqual({
      valid: true,
      issues: [],
    });
    expect(await verifyFutureTokenManifestIntegrity(manifest)).toBe(true);

    const serialized = JSON.parse(JSON.stringify(tokenPuzzle));
    const restored = adaptFutureTokenPuzzle(serialized);
    expect(restored.entries[0].characters[0]).toMatchObject({
      letters: 'SS',
      tokenMetadata: {
        displayToken: 'ß',
        fillToken: 'SS',
        fillUnits: ['S', 'S'],
        rebus: true,
      },
    });
    expect(restored.entries[1].characters[0].letters).toBe('SS');
    expect(restored.tokenManifest).toEqual(manifest);
  });

  it('requires crossing equality and rejects a tampered token map', async () => {
    const source = puzzle();
    const manifest = await sealFutureTokenManifest(source, { language: 'de' });
    const tampered = structuredClone(manifest);
    tampered.cells.find((cell) => cell.id === 'r0c0').fillToken = 'S';
    expect(validateFutureTokenManifest(tampered, source).valid).toBe(false);
    expect(() => adaptFutureTokenPuzzle({ ...source, tokenManifest: tampered }))
      .toThrow(/token/i);
  });

  it('does not invent support for an undeclared language', () => {
    expect(() => createFutureTokenManifestDraft(puzzle(), { language: 'xx' }))
      .toThrow(/supported language/i);
  });

  it('is consumed by the future restore path with canonical fill values', async () => {
    const source = puzzle();
    const manifest = await sealFutureTokenManifest(source, { language: 'de' });
    const storageValues = new Map();
    const storage = {
      getItem: (key) => storageValues.get(key) ?? null,
      setItem: (key, value) => storageValues.set(key, value),
    };
    const profileId = '69d47142-fb69-4134-a96f-c7dab7051661';
    const payload = {
      ...source,
      tokenManifest: manifest,
      provenance: {
        source: 'local-ollama-xfill',
        seed: 7,
        weekday: 'thursday',
      },
    };
    expect(savePrivatePuzzle(profileId, payload, storage)).toBe(true);
    const app = { isValidPuzzle: vi.fn(() => true), init: vi.fn() };
    expect(restorePrivatePuzzle(app, profileId, storage)).toBe(true);
    expect(app.currentPuzzleTokenManifest).toEqual(manifest);
    expect(app.crossword[0].characters[0].letters).toBe('SS');
    expect(app.init).toHaveBeenCalledOnce();
  });
});
