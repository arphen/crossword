import { createConstructorWorkerClient, type ConstructorWorkerClient } from '@crossword/generator/constructor-client';

export { createConstructorWorkerClient };
export type { ConstructorWorkerClient } from '@crossword/generator/constructor-client';

// Keep Vite's worker entry in this application; implementation lives in the package.
export function createBrowserConstructorWorker(): ConstructorWorkerClient {
  return createConstructorWorkerClient(new Worker(new URL('./constructorWorker.ts', import.meta.url), { type: 'module' }));
}
