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
  /**
   * Legacy escape hatch, deliberately typed loosely. TODO(migration): replace
   * with a domain-backed view model; tracked debt, not a suppression directive.
   */
  app: Record<string, unknown>;
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
