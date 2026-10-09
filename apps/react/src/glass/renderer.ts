// The narrow surface every glass backend implements. The React layer only
// talks to this, so a different backend (WebGL2 today, a Rust/wgpu build
// compiled to WASM later) can replace the WebGPU one without touching it.

import { PALETTE_SLOTS } from './palette';

/** Floats in the globals block every backend receives. */
export const GLOBAL_FLOATS = 6 * 4 + PALETTE_SLOTS * 4;

/** Where each value sits in the globals block. */
export const GLOBAL = {
  /** Canvas width and height in CSS px, device pixels per CSS px, time (s). */
  view: 0,
  /** The board's frame in canvas CSS px: x, y, width, height. */
  board: 4,
  /** Key light: from x, y and to x, y (CSS px). */
  light: 8,
  /** Light change time (s), its duration (s), cell size (px), square count. */
  lightTiming: 12,
  /** Direction (0 Across, 1 Down), paper (0/1), reduced motion (0/1), more contrast (0/1). */
  mode: 16,
  /** Ceremony start time (s, or -1000), ambient (0/1), exposure, combo heat. */
  events: 20,
  /** The palette, PALETTE_SLOTS vec4s (palette.ts order). */
  palette: 24,
} as const;

export interface GlassScene {
  /** Cell floats (cellState.ts layout) and how many squares they describe. */
  cells?: Float32Array;
  count?: number;
  /** The whole globals block (GLOBAL layout). */
  globals?: Float32Array;
}

export interface GlassStats {
  backend: 'webgpu' | 'webgl2';
  /** Last measured GPU time per frame in ms, when the backend can tell. */
  gpuMs: number | null;
  /** Render scale applied to the drawing buffer (dynamic resolution). */
  scale: number;
  /** Drawing buffer size in device pixels. */
  width: number;
  height: number;
}

export interface GlassRenderer {
  readonly kind: 'webgpu' | 'webgl2';
  /** Size of the canvas in CSS px and the pixel ratio to draw at. */
  resize(width: number, height: number, pixelRatio: number): void;
  /** Replace the cells and/or the globals. */
  setScene(scene: GlassScene): void;
  /** Update one square's floats in place. */
  setCellState(index: number, floats: Float32Array): void;
  /** Draw one frame at `time` seconds. */
  frame(time: number): void;
  stats(): GlassStats;
  destroy(): void;
}

/** Called when a backend's device is lost (or its context is), so the layer
 *  can rebuild without a reload. `final` means: do not try this backend again. */
export type LostHandler = (reason: string, final: boolean) => void;
