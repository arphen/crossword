import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { loadLexicon, solveFill, type FillRequest, type Lexicon } from '@crossword/construction';
import { createFakeLocalModelAdapter, type ModelBroker } from '@crossword/model-runtime';
import { constructPuzzle } from './constructPuzzle';
import { DAY_RECIPES } from './recipes';

const CLUE_DRAFTS = [
  { mechanism: 'direct' as const, text: 'Fixture direct clue', difficulty: 0.2 },
  { mechanism: 'standard' as const, text: 'Fixture standard clue', difficulty: 0.4 },
  { mechanism: 'oblique' as const, text: 'Fixture oblique clue', difficulty: 0.7 }
] as const;

const SUGGESTIONS = [
  { surface: 'ARIA', intendedSense: 'fixture', associations: [] as const, role: 'general' as const, confidence: 0.6 },
  { surface: 'ERA', intendedSense: 'fixture', associations: [] as const, role: 'general' as const, confidence: 0.6 },
  { surface: 'STARE', intendedSense: 'fixture', associations: [] as const, role: 'general' as const, confidence: 0.6 },
  { surface: 'TREATS', intendedSense: 'fixture', associations: [] as const, role: 'general' as const, confidence: 0.6 }
] as const;

function labLexicon(maxLength = 15): Lexicon {
  const text = readFileSync(path.resolve(__dirname, '../../construction/data/fill-lexicon-v1.txt'), 'utf8');
  return loadLexicon(text, { maxLength });
}

function brokerFor(onGenerate?: () => void): ModelBroker {
  const adapter = createFakeLocalModelAdapter({
    suggestions: [...SUGGESTIONS],
    clueDrafts: [...CLUE_DRAFTS]
  });
  return {
    state: () => 'loaded',
    probe: () => ({ webgpu: true, availableMemoryMb: 1, storageQuotaBytes: 1, storageUsageBytes: 0 }),
    install: async () => ({ ok: true, value: undefined }),
    load: async () => ({ ok: true, value: undefined }),
    generateCandidates: async (request, signal) => {
      onGenerate?.();
      void signal;
      const value = (await adapter.generateCandidates(request)) as readonly import('@crossword/model-runtime').CandidateSuggestion[];
      return { ok: true as const, value };
    },
    composeClues: async (request, signal) => {
      void signal;
      const value = (await adapter.composeClues(request)) as readonly import('@crossword/model-runtime').ClueDraft[];
      return { ok: true as const, value };
    },
    unload: async () => ({ ok: true, value: undefined })
  };
}

function solveSync(request: FillRequest) {
  return solveFill({ ...request, maxNodes: 60_000 });
}

describe('constructPuzzle end to end (fake model, lab lexicon)', () => {
  it('publishes a valid, integrity-pinned manifest through the whole pipeline', async () => {
    const lexicon = labLexicon();
    const result = await constructPuzzle(
      brokerFor(),
      { solve: solveSync },
      {
        recipe: {
          ...DAY_RECIPES.monday,
          templateIds: ['human-15x15'],
          maxNodes: 60_000,
          qualityThreshold: 0.4,
          maxRestarts: 1
        },
        seed: 'fixture-e2e',
        lexicon,
        modelId: 'fake-adapter'
      }
    );

    if (!result.ok) throw new Error(`expected ok, got ${JSON.stringify(result.error)}`);
    expect(result.puzzle.provenance.source).toBe('local-construction');
    expect(result.puzzle.integrity.algorithm).toBe('sha256');
    expect(result.puzzle.entries.length).toBeGreaterThan(50);
    expect(result.puzzle.clues).toHaveLength(result.puzzle.entries.length);
    expect(result.puzzle.quality.score).toBeGreaterThan(0);
    expect(result.templateId).toBe('human-15x15');
  }, 120_000);

  it('rejects a fill whose editorial score misses the recipe bar (P0 gate regression)', async () => {
    const result = await constructPuzzle(
      brokerFor(),
      { solve: solveSync },
      {
        recipe: {
          ...DAY_RECIPES.monday,
          templateIds: ['human-15x15'],
          maxNodes: 60_000,
          qualityThreshold: 0.99, // unreachable editorial bar
          maxRestarts: 1
        },
        seed: 'fixture-e2e',
        lexicon: labLexicon(),
        modelId: 'fake-adapter'
      }
    );
    expect(result.ok).toBe(false);
    if (!result.ok) {
      // The CSP DID solve (fill budget was not the failure); the normalized
      // editorial gate is what rejected the candidate.
      expect(result.error.stage).toBe('fill');
      expect(result.error.code).toBe('exhausted-restarts');
      expect(result.error.message).toContain('quality:');
    }
  }, 120_000);

  it('refuses an unavailable recipe without calling the model', async () => {
    let calls = 0;
    const result = await constructPuzzle(
      brokerFor(() => { calls += 1; }),
      { solve: solveSync },
      {
        recipe: DAY_RECIPES.sunday,
        seed: 'fixture-e2e',
        lexicon: labLexicon(),
        modelId: 'fake-adapter'
      }
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe('recipe-unavailable');
    expect(calls).toBe(0);
  });
});
