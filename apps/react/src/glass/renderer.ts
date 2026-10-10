// The narrow surface every glass backend implements. The React layer only
// talks to this, so a different backend (WebGL2 today, a Rust/wgpu build
// compiled to WASM later) can replace the WebGPU one without touching it.

/** Impulses the gel remembers at once (typing, verdicts, the ceremony). */
export const IMPULSES = 6;

/** Floats in the globals block every backend receives. */
export const GLOBAL_FLOATS = 17 * 4 + IMPULSES * 4;

/** Where each value sits in the globals block (vec4 slots). */
export const GLOBAL = {
  /** Canvas (the viewport) width and height in CSS px, device pixels per CSS px, time (s). */
  view: 0,
  /** The squares' extent in viewport CSS px: x, y, width, height. */
  board: 4,
  /** Grid origin x, y (CSS px), pitch (px between squares), columns. */
  grid: 8,
  /** Rows, square count, ceremony start (s, or -1000), ambient motion (0/1). */
  dims: 12,
  /** Direction (0 Across, 1 Down), paper (0/1), reduced motion (0/1), more contrast (0/1). */
  mode: 16,
  /** Across lane's live light, Down's, warmth (1 warm … 0 cool), board charge. */
  lane: 20,
  /** Spill alpha, room wash, flame alpha, cursor alpha (CSS shares, 0..1). */
  spill: 24,
  /** Key light x, y (CSS px), its height (px), hover (0/1). */
  key: 28,
  /** Linear RGB colours (w unused unless noted). */
  orange: 32,
  blue: 36,
  /** The active word's flame; w is 1 while a word is lit. */
  flame: 40,
  black: 44,
  cell: 48,
  shaded: 52,
  /** Red (wrong). */
  red: 56,
  /** The Across and Down lanes' visible areas (answer boxes are clipped to
   *  them as the lanes scroll): x, y, width, height. */
  clipAcross: 60,
  clipDown: 64,
  /** IMPULSES vec4s: x, y (CSS px), start time (s), strength. */
  impulse: 68,
} as const;

export interface GlassScene {
  /** Cell floats (cellState.ts layout) and how many squares they describe. */
  cells?: Float32Array;
  count?: number;
  /** Answer-box floats (boxes.ts layout) and how many boxes they describe. */
  boxes?: Float32Array;
  boxCount?: number;
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
