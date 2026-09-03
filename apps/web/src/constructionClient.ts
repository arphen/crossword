/**
 * Browser construction client: loads the lab lexicon and frequency prior,
 * adapts the worker clients to the constructPuzzle ports, and runs the
 * end-to-end construction pipeline. All data is local; asset fetches come
 * from the app's own origin only.
 */
import { loadLexicon, type Lexicon } from '@crossword/construction';
import { constructPuzzle, type ConstructResult } from '@crossword/application';
import type { DayRecipe } from '@crossword/application';
import { browserRuntimeProbe } from './modelConfig';
import type { ModelWorkerClient } from './workers/modelClient';
import type { ConstructorWorkerClient } from './workers/constructorClient';

export type ConstructionClient = Readonly<{
  /** True when the lexicon artifacts are loaded and ready. */
  ready: () => boolean;
  /** Runs one construction; fails typed when the model is not enabled. */
  run: (request: { seed: string; day: string }, signal?: AbortSignal) => Promise<ConstructResult>;
}>;

export async function loadConstructionAssets(baseUrl = ''): Promise<Lexicon> {
  const [lexiconText, priorText] = await Promise.all([
    fetch(`${baseUrl}/data/fill-lexicon-v1.txt`).then((response) => {
      if (!response.ok) throw new Error(`Lexicon artifact unavailable (${response.status})`);
      return response.text();
    }),
    fetch(`${baseUrl}/data/freq-prior-v1.txt`)
      .then((response) => (response.ok ? response.text() : ''))
      .catch(() => '')
  ]);
  return loadLexicon(lexiconText, { frequencyPrior: priorText || undefined });
}

export function createConstructionClient(
  modelClient: ModelWorkerClient,
  constructorClient: ConstructorWorkerClient,
  lexicon: Lexicon,
  recipeByDay: Readonly<Record<string, DayRecipe>>,
  modelId: string
): ConstructionClient {
  return {
    ready: () => lexicon.wordCount > 0,
    async run(request, signal) {
      return constructPuzzle(
        {
          state: modelClient.state,
          probe: () => browserRuntimeProbe(),
          install: (installSignal) => modelClient.install(installSignal),
          load: (loadSignal) => modelClient.load(loadSignal),
          generateCandidates: (candidateRequest, candidateSignal) => modelClient.generateCandidates(candidateRequest, candidateSignal),
          composeClues: (clueRequest, clueSignal) => modelClient.composeClues(clueRequest, clueSignal),
          unload: () => modelClient.unload()
        },
        {
          solve: (fillRequest, options) => constructorClient.solve(fillRequest, options)
        },
        {
          recipe: recipeByDay[request.day]!,
          seed: request.seed,
          lexicon,
          modelId
        },
        signal
      );
    }
  };
}
