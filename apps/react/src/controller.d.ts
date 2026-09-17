import type { AxiosStatic } from 'axios';
import type { Socket } from 'socket.io-client';

/**
 * Legacy boundary: the Vue-compatible options adapter adds data, methods,
 * computed properties and $refs at runtime. This declaration checks its React
 * lifecycle contract, not the dynamically assembled app implementation.
 */
export interface ControllerConfiguration {
  axios?: AxiosStatic;
  socket?: Socket;
  room?: string;
  role?: string;
}

export interface Controller {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Dynamic legacy app; replace with a domain-backed view model during migration.
  app: Record<string, any>;
  subscribe(listener: () => void): () => void;
  snapshot(): number;
  flush(): void;
  start(): void;
  dispose(): void;
}

export function createController(
  createOptions: (dependencies: object) => object,
  configuration?: ControllerConfiguration,
): Controller;
