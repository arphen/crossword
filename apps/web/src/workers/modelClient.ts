import { createModelWorkerClient, type ModelWorkerClient } from '@crossword/generator/model-client';

export { createModelWorkerClient };
export type { ModelWorkerClient, ModelManifest, RuntimeProbe } from '@crossword/generator/model-client';

// Keep Vite's worker entry in this application; implementation lives in the package.
export function createBrowserModelWorkerClient(): ModelWorkerClient {
  return createModelWorkerClient(new Worker(new URL('./modelWorker.ts', import.meta.url), { type: 'module' }));
}
