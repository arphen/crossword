/**
 * End-to-end original construction (docs/plans/02 pipeline):
 *
 *   recipe + seed -> template -> topology -> model candidate bag ->
 *   lexicon resolution (+ theme locks) -> deterministic CSP fill ->
 *   clue ladder -> validators -> immutable manifest
 *
 * The model supplies candidates and clue language; the deterministic engine
 * owns topology, crossings, eligibility, and the publish gate. Every failure
 * is a typed diagnostic, never a playable half-puzzle.
 */
import {
  adaptiveScore,
  blendScore,
  curatedTemplateBank,
  deriveTopology,
  scoreFill,
  type FillCandidate,
  type FillRequest,
  type FillResult,
  type LearnerProfile,
  type Lexicon
} from '@crossword/construction';
import type { CandidateRequest, CandidateSuggestion, ClueDraft, ModelBroker } from '@crossword/model-runtime';
import type { PuzzleDocument, ProvenanceRecord } from '@crossword/domain';

import { assembleDraftManifest, finalizeIntegrity } from './manifest';
import type { DayRecipe } from './recipes';

export interface PuzzleFillGrid {
  solve: (request: FillRequest, options?: { signal?: AbortSignal }) => FillResult | Promise<FillResult>;
}

export type ConstructPuzzleRequest = Readonly<{
  recipe: DayRecipe;
  seed: string;
  lexicon: Lexicon;
  modelId: string;
  /** Surfaces to exclude (recent answers, household exclusions). */
  excludedAnswers?: readonly string[];
  audienceSummary?: string;
  /**
   * Optional household learner profile (docs/crossword research.md): shifts
   * candidate preference toward due-for-review, ability-aligned, affordant
   * vocabulary. Local data only; never sent anywhere.
   */
  learnerProfile?: LearnerProfile;
}>;

export type ConstructionStage = 'model' | 'lexicon' | 'topology' | 'fill' | 'clues';

export type ConstructFailure = Readonly<{
  stage: ConstructionStage;
  code: string;
  message: string;
}>;

export type ConstructResult =
  | { ok: true; puzzle: PuzzleDocument; templateId: string; restartCount: number }
  | { ok: false; error: ConstructFailure };

const SOLVER_VERSION = 'csp-mac-1';
const PROMPT_VERSION = 'candidates-v1';

/** Numeric seed from an arbitrary string, stable across calls. */
export function numericSeed(seed: string): number {
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash >>> 0;
}

export async function constructPuzzle(
  broker: ModelBroker,
  fillGrid: PuzzleFillGrid,
  request: ConstructPuzzleRequest,
  signal?: AbortSignal
): Promise<ConstructResult> {
  const { recipe, lexicon, seed, learnerProfile } = request;

  if (!recipe.available) {
    return { ok: false, error: { stage: 'topology', code: 'recipe-unavailable', message: recipe.note } };
  }
  if (recipe.templateIds.length === 0) {
    return { ok: false, error: { stage: 'topology', code: 'no-templates', message: 'The recipe has no curated templates' } };
  }

  const baseSeed = numericSeed(seed);

  // 0. Pre-derive every recipe template: the requested candidate lengths come
  // from the templates the day can actually use (review P1: requested lengths
  // must not make theme-lock days fail by asking only 3-10).
  const recipeTopologies = recipe.templateIds
    .map((templateId) => curatedTemplateBank().find((entry) => entry.id === templateId))
    .map((template) => (template ? deriveTopology(template.mask, { templateId: template.id }) : undefined))
    .map((derived) => (derived && derived.ok ? derived.topology : undefined))
    .filter((topology): topology is NonNullable<typeof topology> => topology !== undefined);
  if (recipeTopologies.length === 0) {
    return { ok: false, error: { stage: 'topology', code: 'template-missing', message: 'No recipe template derived successfully' } };
  }
  const targetLengths = [...new Set(recipeTopologies.flatMap((topology) => topology.slots.map((slot) => slot.length)))]
    .sort((left, right) => left - right);

  // 1. Candidate bag from the required local model.
  const candidateRequest: CandidateRequest = {
    seed: `${seed}:${recipe.day}`,
    audienceSummary: request.audienceSummary ?? 'household blend, broad interests',
    requestedRoles: recipe.themeLocks > 0 ? ['theme', 'long', 'general', 'glue'] : ['general', 'glue', 'stretch'],
    excludedAnswers: [...(request.excludedAnswers ?? [])],
    maxSuggestions: recipe.themeLocks > 0 ? 48 : 24,
    targetLengths
  };
  const generated = await broker.generateCandidates(candidateRequest, signal);
  if (!generated.ok) {
    return { ok: false, error: { stage: 'model', code: String(generated.error.code), message: generated.error.message } };
  }
  const suggestions = generated.value;

  // 2. Lexicon resolution: the lexicon is authoritative for eligibility.
  const resolvedSuggestions: FillCandidate[] = [];
  for (const suggestion of suggestions) {
    const candidate = lexicon.resolve(suggestion.surface);
    if (candidate !== undefined) resolvedSuggestions.push(candidate);
  }

  // 3. Seeded attempts over the recipe's templates.
  let lastDiagnostic = 'unknown';
  for (let attempt = 0; attempt < recipe.maxRestarts; attempt += 1) {
    const templateId = recipe.templateIds[(baseSeed + attempt) % recipe.templateIds.length]!;
    const template = curatedTemplateBank().find((entry) => entry.id === templateId);
    if (!template) {
      return { ok: false, error: { stage: 'topology', code: 'template-missing', message: `Template ${templateId} is not in the curated bank` } };
    }
    const topology = recipeTopologies.find((entry) => entry.templateId === templateId);
    if (!topology) {
      lastDiagnostic = `topology: ${templateId} failed derivation`;
      continue;
    }
    if (topology.width !== recipe.width || topology.height !== recipe.height) {
      lastDiagnostic = `format: template ${template.id} is ${topology.width}x${topology.height}, recipe wants ${recipe.width}x${recipe.height}`;
      continue;
    }

    // 3a. Lab lexicon slice for the slot lengths, plus resolved model ideas.
    const neededLengths = [...new Set(topology.slots.map((slot) => slot.length))];
    const lexiconCandidates: FillCandidate[] = [];
    for (const length of neededLengths) {
      for (const word of lexicon.wordsOfLength(length, Number.POSITIVE_INFINITY)) {
        const candidate = lexicon.resolve(word);
        if (candidate !== undefined) lexiconCandidates.push(candidate);
      }
    }
    const deduped = dedupeCandidates([...resolvedSuggestions, ...lexiconCandidates]);
    // Quality scoring consumes the base crossword-quality score, never the
    // learner-blended preference.
    const baseScoreByWord = new Map(deduped.map((candidate) => [candidate.word, candidate.score] as const));
    const candidates = applyLearnerPreferences(deduped, learnerProfile);

    // 3b. Theme locks for gimmick days.
    const locks = bindThemeLocks(recipe, topology.slots, suggestions);
    if (!locks.ok) return { ok: false, error: locks.error };

    // 4. Deterministic fill.
    const fillResult = await fillGrid.solve(
      {
        slots: topology.slots,
        intersections: topology.intersections,
        candidates,
        lockedWords: locks.value,
        seed: baseSeed + attempt,
        maxNodes: recipe.maxNodes,
        excludedWords: request.excludedAnswers
      },
      { signal }
    );
    if (fillResult.status !== 'solved' || !fillResult.solution) {
      lastDiagnostic = `fill: ${fillResult.failure?.code ?? 'unknown'}`;
      continue;
    }

    const words: Record<string, string> = {};
    const wordScores: Record<string, number> = {};
    for (const [slotId, candidate] of Object.entries(fillResult.solution.assignments)) {
      words[slotId] = candidate.word;
      wordScores[slotId] = baseScoreByWord.get(candidate.word) ?? candidate.score;
    }

    // 4. Editorial quality gate on the normalized 0..1 score: a complete
    // fill that misses the recipe's bar is a diagnostic, never a puzzle.
    const baseScoreForQuality = (slotId: string): number =>
      baseScoreByWord.get(words[slotId] ?? '') ?? 0;
    const quality = scoreFill({
      assignments: topology.slots.map((slot) => ({
        word: words[slot.id] ?? '',
        score: baseScoreForQuality(slot.id),
        crossings: crossingsForSlot(topology, slot.id)
      })),
      whiteCellCount: topology.whiteCellCount,
      crossingCellCount: topology.intersections.length
    });
    if (quality.score < recipe.qualityThreshold) {
      lastDiagnostic = `quality: ${quality.score.toFixed(3)} < ${recipe.qualityThreshold}`;
      continue;
    }

    // 5. Clue ladder per entry; model composition is required.
    const clueVariants: Record<string, ClueDraft[]> = {};
    for (const entry of topology.entries) {
      const word = words[entry.id]!;
      const drafts = await broker.composeClues({ answer: word, intendedSense: `web2:${word}` }, signal);
      if (!drafts.ok) {
        return { ok: false, error: { stage: 'clues', code: String(drafts.error.code), message: drafts.error.message } };
      }
      if (drafts.value.length === 0) {
        return { ok: false, error: { stage: 'clues', code: 'empty-clue-ladder', message: `The model produced no clue drafts for ${word}` } };
      }
      clueVariants[entry.id] = [...drafts.value];
    }

    // 5. Provenance, quality, manifest, integrity.
    const provenance: ProvenanceRecord[] = [
      lexicon.provenance,
      {
        id: `model-candidates-${baseSeed}-r${attempt}`,
        kind: 'model',
        source: 'local model candidate bag (structured JSON, deterministic seed)',
        license: 'Local inference; no external distribution',
        digest: `seed-${baseSeed}-r${attempt}`
      },
      ...Object.entries(locks.value).map(([slotId, word]) => ({
        id: `theme-lock-${slotId}`,
        kind: 'model' as const,
        source: `theme lock ${slotId} from model candidate bag`,
        license: 'Local model output; validated in-grid',
        digest: word
      }))
    ];

    const manifest = assembleDraftManifest({
      seed: `${seed}:${recipe.day}:r${attempt}`,
      title: titleFor(recipe),
      subtitle: subtitleFor(recipe, template),
      topology,
      words,
      wordScores,
      clueVariants,
      provenanceRecords: provenance,
      generation: {
        modelId: request.modelId,
        promptVersion: PROMPT_VERSION,
        lexiconVersion: lexicon.id,
        solverVersion: SOLVER_VERSION,
        generatedAt: new Date().toISOString(),
        restartCount: attempt
      },
      quality: {
        score: quality.score,
        thresholds: { qualityThreshold: recipe.qualityThreshold },
        validators: ['topology', 'crossings', 'all-different', 'lexicon-membership', 'provenance', 'integrity']
      },
      source: 'local-construction',
      recipeId: recipe.day,
      createdBy: 'local-construction' as const
    });

    const puzzle = await finalizeIntegrity(manifest);
    return { ok: true, puzzle, templateId: template.id, restartCount: attempt };
  }

  return {
    ok: false,
    error: {
      stage: 'fill',
      code: 'exhausted-restarts',
      message: `Fill failed after ${recipe.maxRestarts} attempts (last: ${lastDiagnostic})`
    }
  };
}

type SlotLike = Readonly<{ id: string; length: number }>;

function bindThemeLocks(
  recipe: DayRecipe,
  slots: readonly SlotLike[],
  suggestions: readonly CandidateSuggestion[]
): { ok: true; value: Record<string, string> } | { ok: false; error: ConstructFailure } {
  if (recipe.themeLocks === 0) return { ok: true, value: {} };
  const longSlots = [...slots].sort((left, right) => right.length - left.length).slice(0, recipe.themeLocks);
  const used = new Set<string>();
  const value: Record<string, string> = {};
  for (const slot of longSlots) {
    const match = suggestions.find((suggestion) =>
      suggestion.role === 'theme'
      && !used.has(suggestion.surface.toUpperCase())
      && /^[A-Z]+$/.test(suggestion.surface.toUpperCase())
      && suggestion.surface.toUpperCase().length === slot.length
    );
    if (!match) {
      return {
        ok: false,
        error: {
          stage: 'model',
          code: 'theme-unresolved',
          message: `The model produced no ${slot.length}-letter theme entry for slot ${slot.id}`
        }
      };
    }
    const word = match.surface.toUpperCase();
    used.add(word);
    value[slot.id] = word;
  }
  return { ok: true, value };
}

function crossingsForSlot(topology: { intersections: readonly { slotId: string; otherSlotId: string }[] }, slotId: string): number {
  let count = 0;
  for (const intersection of topology.intersections) {
    if (intersection.slotId === slotId || intersection.otherSlotId === slotId) count += 1;
  }
  return count;
}

/**
 * Blend learner-profile preference into the static crossword-quality score
 * (docs/crossword research.md). `filledCrossLetters` stays 0: in the MAC
 * engine, crossing-letter pressure is handled by domain propagation, so the
 * static preference ranks the unassisted-recall (k = 0) priority the document
 * calls out. Base surprisal is derived from staple familiarity: household
 * staples are low-surprisal, obscure web2 entries high-surprisal.
 */
export function applyLearnerPreferences(
  candidates: readonly FillCandidate[],
  profile: LearnerProfile | undefined,
  adaptWeight = 0.35
): FillCandidate[] {
  if (!profile || candidates.length === 0) return [...candidates];

  // Branching index: (length, position, letter) -> how many pool candidates
  // carry that letter there. Higher branching = a letter that keeps crossing
  // slots flexible (the doc's affordance metric).
  const branching = new Map<string, number>();
  for (const candidate of candidates) {
    for (let position = 0; position < candidate.word.length; position += 1) {
      const key = `${candidate.word.length}:${position}:${candidate.word[position]!}`;
      branching.set(key, (branching.get(key) ?? 0) + 1);
    }
  }

  return candidates.map((candidate) => {
    const baseSurprisal = 6 * (1 - Math.min(1, Math.max(0, candidate.score))) + 1;
    const adaptive = adaptiveScore(
      { lemma: candidate.word, baseSurprisal },
      0,
      profile,
      (position, letter) => branching.get(`${candidate.word.length}:${position}:${letter}`) ?? 0
    );
    // Logistic squash to 0..1; the raw score spans roughly [-2, +2].
    const adaptive01 = 1 / (1 + Math.exp(-adaptive / 2));
    return { ...candidate, score: blendScore(candidate.score, adaptive01, adaptWeight) };
  });
}

function dedupeCandidates(candidates: readonly FillCandidate[]): FillCandidate[] {
  const seen = new Set<string>();
  const out: FillCandidate[] = [];
  for (const candidate of candidates) {
    const key = candidate.word.toUpperCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(candidate);
  }
  return out;
}

function titleFor(recipe: DayRecipe): string {
  const day = recipe.day.charAt(0).toUpperCase() + recipe.day.slice(1);
  return `${day} Crossword`;
}

function subtitleFor(recipe: DayRecipe, template: Readonly<{ id: string; style: string }>): string {
  return `Locally constructed ${recipe.width}x${recipe.height} · ${template.id}`;
}
