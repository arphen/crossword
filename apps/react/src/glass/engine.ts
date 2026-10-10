// The glass layer's engine, free of React: it watches the board the CSS draws
// (layout, classes, marks, focus, typing, and the root's colour tokens and
// light), keeps the cell buffer in step, picks a backend (WebGPU, then WebGL2,
// then none, which leaves the CSS board as it is), recovers from a lost
// device, and decides when a frame is worth drawing. The DOM is the source of
// truth; this only ever reads it.

import { emptyBoxes, readBoxes } from './boxes';
import { CELL_FLOATS, CellBook, FLAG, SLOT, readCellCues, readCellFacts, sweepPositions, type CellCues } from './cellState';
import type { GlassFlag } from './flag';
import { gpuEntry } from './gpuTypes';
import { GLOBAL, GLOBAL_FLOATS, IMPULSES, type GlassRenderer } from './renderer';
import { DEFAULT_SCHEDULE, frameDue, loopNeeded } from './scheduler';
import { DEFAULT_TOKENS, flameTint, laneTint, readRootLight, readTokens, type GlassTokens, type Rgb } from './tint';
import { createWebGl2Glass } from './webgl2';
import { createWebGpuGlass } from './webgpu';

export type GlassBackend = 'webgpu' | 'webgl2' | null;

export interface GlassMood {
  light: boolean;
  direction: 'across' | 'down';
}

export interface GlassEngineOptions {
  /** The board the CSS draws; the layer's canvas goes in behind it. */
  grid: HTMLElement;
  flag: GlassFlag;
  /** Told which backend is drawing (null: none, the CSS board stays). */
  onBackend: (backend: GlassBackend) => void;
  debug?: HTMLElement | null;
  /** Hold the render scale (screenshots, comparisons); dynamic otherwise. */
  fixedScale?: number | null;
}

const RESTART_LIMIT = 3;
/** The lane light's cross-fade, as vision.css's --lane-fade (seconds). */
const LANE_FADE = 0.28;
const KEY_EASE = 0.9;

/** How long a change keeps the layer drawing, by what began (seconds). */
function animationFor(began: number, flags: number): number {
  let seconds = 0.6;
  if (began & FLAG.CURSOR) seconds = Math.max(seconds, 1.2);
  if (began & (FLAG.CORRECT | FLAG.WRONG)) seconds = Math.max(seconds, 2.2);
  if (began & FLAG.POP) seconds = Math.max(seconds, 2.6);
  if (flags & FLAG.FLARE) seconds = Math.max(seconds, 1.0);
  return seconds;
}

const ease = (k: number) => {
  const t = Math.min(1, Math.max(0, k));
  return t * t * (3 - 2 * t);
};

/** A value that eases from where it is toward a new target. */
class Eased {
  private from: number;
  private to: number;
  private at = -1000;
  constructor(
    value: number,
    private readonly duration: number,
  ) {
    this.from = value;
    this.to = value;
  }
  value(now: number): number {
    return this.from + (this.to - this.from) * ease((now - this.at) / this.duration);
  }
  set(target: number, now: number, instant = false): boolean {
    if (target === this.to) return false;
    this.from = instant ? target : this.value(now);
    this.to = target;
    this.at = now;
    return true;
  }
  settled(now: number): boolean {
    return now - this.at >= this.duration;
  }
}

export class GlassEngine {
  private renderer: GlassRenderer | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private readonly book = new CellBook(225);
  private elements: HTMLElement[] = [];
  private cues: CellCues[] = [];
  private readonly index = new Map<Element, number>();
  private readonly positions: Array<{ row: number; column: number }> = [];
  private readonly cellKeys = new Map<string, number>();
  private boxes = emptyBoxes();
  private boxesDirty = true;
  private trackBoxesUntil = 0;
  private readonly globals = new Float32Array(GLOBAL_FLOATS);
  private readonly epoch = performance.now();
  private readonly state = { animateUntil: 0, lastFrame: -1, lastInput: 0, ambient: true };
  private raf = 0;
  private destroyed = false;
  private restarts = 0;
  private mood: GlassMood = { light: false, direction: 'across' };
  private tokens: GlassTokens = DEFAULT_TOKENS;
  private root: HTMLElement | null = null;
  private cellSize = 32;
  private origin = { x: 0, y: 0 };
  private allSettled = false;
  private ceremony = -1000;
  private reducedMotion = false;
  private moreContrast = false;
  private readonly laneAcross = new Eased(1, LANE_FADE);
  private readonly laneDown = new Eased(DEFAULT_TOKENS.laneRest, LANE_FADE);
  private readonly warmth = new Eased(1, LANE_FADE);
  private readonly keyX = new Eased(0, KEY_EASE);
  private readonly keyY = new Eased(0, KEY_EASE);
  private keyPlaced = false;
  private pointer: { x: number; y: number } | null = null;
  private nextImpulse = 0;
  private cpuMs = 0;
  private framesDrawn = 0;
  private debugTimer = 0;
  private readonly dirty = new Set<number>();
  private readonly cleanups: Array<() => void> = [];

  constructor(private readonly options: GlassEngineOptions) {}

  /** Seconds since the layer started: the shaders' clock. */
  private now(): number {
    return (performance.now() - this.epoch) / 1000;
  }

  async start(): Promise<void> {
    this.root = this.options.grid.closest<HTMLElement>('#app') ?? document.querySelector<HTMLElement>('#app');
    this.watchPreferences();
    const backend = await this.connect(this.options.flag.backend === 'webgl2' ? 'webgl2' : 'webgpu');
    if (this.destroyed) return;
    this.options.onBackend(backend);
    if (!backend) return;
    this.observe();
    this.measure();
    this.state.lastInput = this.now();
    this.invalidate(0.8);
  }

  setMood(mood: GlassMood): void {
    const now = this.now();
    const changed = mood.light !== this.mood.light || mood.direction !== this.mood.direction;
    const turned = mood.direction !== this.mood.direction;
    const themed = mood.light !== this.mood.light;
    this.mood = mood;
    if (!changed) return;
    if (turned) this.aimLanes(now, false);
    // A turn re-tints the flame from the tokens already read; only a change
    // of theme reads the stylesheet again.
    this.readColours(true, themed);
    this.invalidate(0.6);
  }

  destroy(): void {
    this.destroyed = true;
    cancelAnimationFrame(this.raf);
    window.clearInterval(this.debugTimer);
    this.cleanups.splice(0).forEach((cleanup) => cleanup());
    this.renderer?.destroy();
    this.renderer = null;
    this.dropCanvas();
  }

  // ---- Backends -----------------------------------------------------------

  private async connect(first: 'webgpu' | 'webgl2'): Promise<GlassBackend> {
    const order: Array<'webgpu' | 'webgl2'> = first === 'webgpu' ? ['webgpu', 'webgl2'] : ['webgl2'];
    for (const kind of order) {
      if (this.destroyed) return null;
      try {
        if (kind === 'webgpu') {
          if (!gpuEntry()) continue;
          this.renderer = await createWebGpuGlass(this.freshCanvas(), this.lost, { fixedScale: this.options.fixedScale });
        } else {
          this.renderer = createWebGl2Glass(this.freshCanvas(), this.lost);
        }
        if (this.destroyed) {
          this.renderer.destroy();
          this.renderer = null;
          return null;
        }
        return kind;
      } catch (error) {
        if (this.options.flag.debug) console.warn(`[glass] ${kind} unavailable:`, error);
        this.renderer = null;
      }
    }
    this.dropCanvas();
    return null;
  }

  // Each backend draws on a canvas of its own (one that has handed out a
  // WebGPU context cannot give a WebGL one), made here rather than by React
  // so it can be swapped without React's knowledge. It covers the whole app,
  // so the clue lanes' answer boxes take the same light as the board.
  private freshCanvas(): HTMLCanvasElement {
    this.dropCanvas();
    const canvas = document.createElement('canvas');
    canvas.className = 'glass-canvas';
    canvas.setAttribute('aria-hidden', 'true');
    (this.root ?? document.body).appendChild(canvas);
    this.canvas = canvas;
    return canvas;
  }

  private dropCanvas(): void {
    this.canvas?.remove();
    this.canvas = null;
  }

  // A lost device is rebuilt without a reload, a few times; after that the
  // layer falls back to WebGL2, and then to the CSS board.
  private readonly lost = (reason: string, final: boolean) => {
    if (this.destroyed) return;
    if (this.options.flag.debug) console.warn('[glass] lost:', reason);
    const kind = this.renderer?.kind ?? 'webgpu';
    this.renderer?.destroy();
    this.renderer = null;
    this.restarts += 1;
    const next = final || this.restarts > RESTART_LIMIT ? (kind === 'webgpu' ? 'webgl2' : null) : kind;
    window.setTimeout(async () => {
      if (this.destroyed) return;
      const backend = next ? await this.connect(next) : null;
      this.options.onBackend(backend);
      if (!backend) return;
      this.measure();
      this.invalidate(0.8);
    }, 250);
  };

  // ---- Watching the board ---------------------------------------------------

  private watchPreferences(): void {
    const motion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const contrast = window.matchMedia?.('(prefers-contrast: more)');
    const read = () => {
      this.reducedMotion = Boolean(motion?.matches);
      this.moreContrast = Boolean(contrast?.matches);
      this.state.ambient = !this.reducedMotion && document.visibilityState !== 'hidden';
      this.pushGlobals();
      this.invalidate(0.3);
    };
    read();
    motion?.addEventListener?.('change', read);
    contrast?.addEventListener?.('change', read);
    const visibility = () => {
      read();
      if (document.visibilityState === 'hidden') {
        cancelAnimationFrame(this.raf);
        this.raf = 0;
      }
    };
    document.addEventListener('visibilitychange', visibility);
    this.cleanups.push(() => {
      motion?.removeEventListener?.('change', read);
      contrast?.removeEventListener?.('change', read);
      document.removeEventListener('visibilitychange', visibility);
    });
  }

  private observe(): void {
    const grid = this.options.grid;
    const container = grid.parentElement ?? grid;
    const resize = new ResizeObserver(() => this.measure());
    resize.observe(grid);
    const onWindowResize = () => this.measure();
    window.addEventListener('resize', onWindowResize);
    const mutations = new MutationObserver((records) => {
      let rebuilt = false;
      for (const record of records) {
        if (record.type === 'childList' && !rebuilt) {
          const count = grid.querySelectorAll('.grid-cell').length;
          if (count !== this.elements.length) {
            rebuilt = true;
            this.measure();
          }
        }
        const target = record.target instanceof Element ? record.target : record.target.parentElement;
        const cell = target?.closest('.grid-cell');
        const index = cell ? this.index.get(cell) : undefined;
        if (index !== undefined) this.dirty.add(index);
      }
      if (!rebuilt) this.flush();
    });
    mutations.observe(grid, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['class', 'style', 'data-entry-index', 'data-solved', 'data-solved-all', 'data-pop', 'data-flare'],
    });
    // The root carries the colour settings and the board's light (charge,
    // the active word's rank); the document root carries the theme.
    // Re-read once, in the next frame, never inside the event that changed
    // it: the root's inline light (charge, the active word) is cheap to read;
    // the computed tokens only when the theme or a colour setting changes.
    // The direction arrives through setMood.
    let pending = 0;
    let tokensToo = false;
    const later = (tokens: boolean) => {
      tokensToo = tokensToo || tokens;
      if (pending) return;
      pending = requestAnimationFrame(() => {
        pending = 0;
        this.readColours(true, tokensToo);
        tokensToo = false;
      });
    };
    const lightWatch = new MutationObserver(() => later(false));
    const rootWatch = new MutationObserver(() => later(true));
    if (this.root) {
      lightWatch.observe(this.root, { attributes: true, attributeFilter: ['style'] });
      rootWatch.observe(this.root, { attributes: true, attributeFilter: ['data-ramp', 'data-cues', 'data-vibrance', 'data-luma'] });
    }
    rootWatch.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class'] });
    this.cleanups.push(() => {
      cancelAnimationFrame(pending);
      lightWatch.disconnect();
    });
    // The answer boxes move when the lanes scroll, when clues come and go
    // (transitions), and change when the lit word or the cursor moves.
    const lanes = new MutationObserver(() => {
      this.boxesDirty = true;
      this.invalidate(0.3);
    });
    for (const lane of this.root?.querySelectorAll('.clue-column') ?? []) {
      lanes.observe(lane, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'data-entry-index'] });
    }
    const scrolled = () => {
      this.boxesDirty = true;
      this.invalidate(0.2);
    };
    const moving = () => {
      this.trackBoxesUntil = this.now() + 0.9;
      this.invalidate(0.9);
    };
    document.addEventListener('scroll', scrolled, { capture: true, passive: true });
    this.root?.addEventListener('transitionrun', moving);
    this.root?.addEventListener('animationstart', moving);
    this.cleanups.push(() => {
      lanes.disconnect();
      document.removeEventListener('scroll', scrolled, { capture: true });
      this.root?.removeEventListener('transitionrun', moving);
      this.root?.removeEventListener('animationstart', moving);
    });
    const cellOf = (event: Event) => {
      const cell = event.target instanceof Element ? event.target.closest('.grid-cell') : null;
      return cell ? this.index.get(cell) : undefined;
    };
    let lastCursor: number | undefined;
    const focus = (event: Event) => {
      if (lastCursor !== undefined) this.dirty.add(lastCursor);
      lastCursor = cellOf(event);
      if (lastCursor !== undefined) {
        this.dirty.add(lastCursor);
        this.aimKeyAt(lastCursor);
      }
      this.touch();
      this.flush();
    };
    const blur = () => {
      if (lastCursor !== undefined) this.dirty.add(lastCursor);
      // Read after the focus has moved on.
      requestAnimationFrame(() => this.flush());
    };
    const typed = (event: Event) => {
      const index = cellOf(event);
      if (index === undefined) return;
      const now = this.now();
      this.book.press(index, now);
      this.renderer?.setCellState(index, this.book.slice(index));
      this.impulseAt(index, 0.32, now);
      this.touch();
      this.invalidate(2.6);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Backspace' || event.key === 'Delete') typed(event);
    };
    const move = (event: PointerEvent) => {
      if (!this.canvas) return;
      const rect = this.canvas.getBoundingClientRect();
      this.pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      this.aimKey(this.pointer.x - this.cellSize * 0.8, this.pointer.y - this.cellSize * 1.4);
      this.touch();
    };
    const leave = () => {
      this.pointer = null;
      if (lastCursor !== undefined) this.aimKeyAt(lastCursor);
    };
    grid.addEventListener('focusin', focus);
    grid.addEventListener('focusout', blur);
    grid.addEventListener('input', typed);
    grid.addEventListener('keydown', key);
    container.addEventListener('pointermove', move, { passive: true });
    container.addEventListener('pointerleave', leave);
    this.cleanups.push(() => {
      resize.disconnect();
      mutations.disconnect();
      rootWatch.disconnect();
      window.removeEventListener('resize', onWindowResize);
      grid.removeEventListener('focusin', focus);
      grid.removeEventListener('focusout', blur);
      grid.removeEventListener('input', typed);
      grid.removeEventListener('keydown', key);
      container.removeEventListener('pointermove', move);
      container.removeEventListener('pointerleave', leave);
    });
    if (this.options.flag.debug && this.options.debug) {
      this.debugTimer = window.setInterval(() => this.showStats(), 300);
    }
  }

  /** Read the layout once: where the canvas sits and where every square is.
   *  Only on a change of layout, never per frame. */
  private measure(): void {
    const renderer = this.renderer;
    const grid = this.options.grid;
    if (!renderer) return;
    const elements = [...grid.querySelectorAll<HTMLElement>('.grid-cell')];
    const boxes = elements.map((element) => element.getBoundingClientRect());
    const gridBox = grid.getBoundingClientRect();
    this.cellSize = boxes[0]?.width || 32;
    // The canvas is the viewport; everything is in viewport CSS px.
    const width = window.innerWidth;
    const height = window.innerHeight;
    if (!this.canvas) return;
    this.origin = { x: 0, y: 0 };

    const rebuilt = elements.length !== this.elements.length || elements.some((element, i) => element !== this.elements[i]);
    if (rebuilt) {
      this.elements = elements;
      this.index.clear();
      this.positions.length = 0;
      elements.forEach((element, i) => {
        this.index.set(element, i);
        const row = element.parentElement;
        const position = { row: row ? [...grid.children].indexOf(row) : 0, column: row ? [...row.children].indexOf(element) : 0 };
        this.positions.push(position);
        this.cellKeys.set(`${position.row},${position.column}`, i);
      });
      this.book.reset(elements.length);
    }
    this.cues = elements.map(readCellCues);
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    boxes.forEach((box, i) => {
      const x = box.left - this.origin.x;
      const y = box.top - this.origin.y;
      this.book.place(i, x, y, box.width, box.height);
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x + box.width);
      maxY = Math.max(maxY, y + box.height);
    });
    const active = document.activeElement;
    elements.forEach((element, i) => this.book.update(i, readCellFacts(element, active), rebuilt ? -1000 : this.now()));
    this.allSettled = this.everySquareSettled();
    const board = Number.isFinite(minX) ? [minX, minY, maxX - minX, maxY - minY] : [gridBox.left, gridBox.top, gridBox.width, gridBox.height];
    this.globals.set(board, GLOBAL.board);
    // The grid as a lattice: origin, pitch and columns, so the shader finds a
    // square from a point without searching.
    const columns = Math.max(1, this.positions.filter((position) => position.row === 0).length);
    const rows = Math.max(1, Math.ceil(elements.length / columns));
    const pitchX = elements.length > 1 && columns > 1 ? this.book.data[CELL_FLOATS] - this.book.data[0] : this.cellSize;
    this.globals.set([board[0], board[1], pitchX || this.cellSize, columns], GLOBAL.grid);
    this.globals[GLOBAL.dims] = rows;
    this.globals[GLOBAL.dims + 1] = elements.length;
    if (!this.keyPlaced) {
      const now = this.now();
      this.keyX.set(board[0] + board[2] * 0.3, now, true);
      this.keyY.set(board[1] - this.cellSize * 2, now, true);
      this.keyPlaced = true;
    }
    renderer.resize(width, height, window.devicePixelRatio || 1);
    this.readColours(false);
    renderer.setScene({ cells: this.book.data, count: this.book.count });
    this.boxesDirty = true;
    this.readBoxesNow();
    this.pushGlobals();
    this.invalidate(0.4);
  }

  /** Read the answer boxes and the lanes' visible areas. */
  private readBoxesNow(): void {
    const root = this.root;
    if (!root || !this.renderer) return;
    this.boxesDirty = false;
    readBoxes(root, this.tokens, (key) => this.cellKeys.get(key) ?? -1, this.boxes);
    const clip = (selector: string, slot: number) => {
      const lane = root.querySelector(selector);
      const r = lane?.getBoundingClientRect();
      this.globals[slot] = r?.left ?? 0;
      this.globals[slot + 1] = r?.top ?? 0;
      this.globals[slot + 2] = r?.width ?? 0;
      this.globals[slot + 3] = r?.height ?? 0;
    };
    clip('#across', GLOBAL.clipAcross);
    clip('#down', GLOBAL.clipDown);
    this.renderer.setScene({ boxes: this.boxes.data, boxCount: this.boxes.count, globals: this.globals });
  }

  /** Re-read the root's colour tokens and light, and re-tint every square
   *  whose colour moved. */
  private readColours(upload = true, rereadTokens = true): void {
    const root = this.root;
    if (!root) return;
    if (rereadTokens) this.tokens = readTokens(root);
    const light = readRootLight(root);
    const tokens = this.tokens;
    const g = this.globals;
    const charge = light.charge;
    g[GLOBAL.lane + 3] = charge;
    g[GLOBAL.spill] = tokens.ramp && tokens.cues ? Math.min(0.3, tokens.spotAlpha * charge) : 0;
    g[GLOBAL.spill + 1] = tokens.cues ? Math.min(0.12, tokens.spotAlpha * 0.4 * charge) : 0;
    g[GLOBAL.spill + 2] = tokens.flameAlpha;
    g[GLOBAL.spill + 3] = tokens.cursorAlpha;
    const set = (slot: number, rgb: Rgb, w = 0) => {
      g[slot] = rgb[0];
      g[slot + 1] = rgb[1];
      g[slot + 2] = rgb[2];
      g[slot + 3] = w;
    };
    set(GLOBAL.orange, tokens.orange);
    set(GLOBAL.blue, tokens.blue);
    set(GLOBAL.black, tokens.black);
    set(GLOBAL.cell, tokens.cell);
    set(GLOBAL.shaded, tokens.shaded);
    set(GLOBAL.red, tokens.red);
    if (light.activeRank !== null && tokens.ramp) set(GLOBAL.flame, flameTint(tokens, this.mood.direction, light.activeRank), 1);
    else set(GLOBAL.flame, this.mood.direction === 'down' ? tokens.blue : tokens.orange, 1);
    this.aimLanes(this.now(), true);
    let changed = false;
    for (let i = 0; i < this.book.count; i += 1) {
      if (this.tintSquare(i)) changed = true;
    }
    if (changed && upload) this.renderer?.setScene({ cells: this.book.data, count: this.book.count });
    this.boxesDirty = true;
    this.pushGlobals();
    this.invalidate(0.4);
  }

  /** A square's word tints from its cues: on a black square, its gate ticks'
   *  tints (lit when its notch opens a word); on a white one, its words'. */
  private tintSquare(i: number): boolean {
    const cues = this.cues[i];
    if (!cues) return false;
    const tokens = this.tokens;
    const flags = this.book.flags(i);
    const rank = (value: number | null) => (tokens.ramp && value !== null ? value : null);
    let changed = false;
    if (flags & FLAG.BLACK) {
      const across = rank(cues.acrossRank);
      const down = rank(cues.downRank);
      changed = this.book.tint(i, SLOT.across, across === null ? tokens.orange : laneTint(tokens, 'across', across), across === null ? -1 : 0) || changed;
      changed = this.book.tint(i, SLOT.down, down === null ? tokens.blue : laneTint(tokens, 'down', down), down === null ? -1 : 0) || changed;
      return changed;
    }
    const across = rank(cues.acrossRank);
    const down = rank(cues.downRank);
    changed = this.book.tint(i, SLOT.across, across === null ? null : laneTint(tokens, 'across', across), cues.acrossDistance ?? -1) || changed;
    changed = this.book.tint(i, SLOT.down, down === null ? null : laneTint(tokens, 'down', down), cues.downDistance ?? -1) || changed;
    return changed;
  }

  /** Point the lanes' light at the direction being solved. */
  private aimLanes(now: number, quiet: boolean): void {
    const down = this.mood.direction === 'down';
    const rest = this.tokens.laneRest;
    const moved = [this.laneAcross.set(down ? rest : 1, now), this.laneDown.set(down ? 1 : rest, now), this.warmth.set(down ? 0 : 1, now)].some(Boolean);
    if (moved && !quiet) this.invalidate(LANE_FADE + 0.1);
  }

  private everySquareSettled(): boolean {
    let letters = 0;
    for (let i = 0; i < this.book.count; i += 1) {
      const flags = this.book.flags(i);
      if (flags & FLAG.BLACK) continue;
      letters += 1;
      if (!(flags & FLAG.SETTLED)) return false;
    }
    return letters > 0;
  }

  /** Re-read the squares that changed and upload just those. */
  private flush(): void {
    const renderer = this.renderer;
    if (!renderer || !this.dirty.size) return;
    const now = this.now();
    const active = document.activeElement;
    const pops: number[] = [];
    let seconds = 0;
    for (const i of this.dirty) {
      const element = this.elements[i];
      if (!element) continue;
      const facts = readCellFacts(element, active);
      if (facts.flags & ~this.book.flags(i) & FLAG.POP) pops.push(i);
    }
    const sweep = sweepPositions(pops.map((i) => this.positions[i]));
    const popAt = new Map(pops.map((i, rank) => [i, sweep[rank]]));
    for (const i of this.dirty) {
      const element = this.elements[i];
      if (!element) continue;
      const before = this.book.flags(i);
      const facts = readCellFacts(element, active);
      this.cues[i] = readCellCues(element);
      const moved = this.book.update(i, facts, now, popAt.get(i) ?? 0);
      const tinted = this.tintSquare(i);
      if (moved || tinted) {
        renderer.setCellState(i, this.book.slice(i));
        const began = facts.flags & ~before;
        seconds = Math.max(seconds, animationFor(began, facts.flags));
        if (began & FLAG.WRONG) this.impulseAt(i, 0.55, now);
        if (began & FLAG.POP && popAt.get(i) === 0) this.impulseAt(i, 0.4, now);
      }
    }
    this.dirty.clear();
    const settled = this.everySquareSettled();
    if (settled && !this.allSettled) {
      this.ceremony = now;
      this.pushGlobals();
      seconds = Math.max(seconds, 5);
    }
    this.allSettled = settled;
    if (seconds > 0) {
      this.touch();
      this.invalidate(seconds);
    }
  }

  // ---- The sheet and the light ------------------------------------------------

  /** Send a ripple through the gel from a square (strength in square heights). */
  private impulseAt(index: number, strength: number, now: number): void {
    if (this.reducedMotion) return;
    const base = index * CELL_FLOATS;
    const slot = GLOBAL.impulse + (this.nextImpulse % IMPULSES) * 4;
    this.nextImpulse += 1;
    this.globals[slot] = this.book.data[base] + this.book.data[base + 2] * 0.5;
    this.globals[slot + 1] = this.book.data[base + 1] + this.book.data[base + 3] * 0.5;
    this.globals[slot + 2] = now;
    this.globals[slot + 3] = strength;
  }

  private aimKeyAt(index: number): void {
    if (this.pointer) return;
    const base = index * CELL_FLOATS;
    const x = this.book.data[base] + this.book.data[base + 2] * 0.5;
    const y = this.book.data[base + 1] + this.book.data[base + 3] * 0.5;
    this.aimKey(x - this.cellSize * 1.5, y - this.cellSize * 2.5);
  }

  /** Send the key light somewhere, easing from wherever it is now. */
  private aimKey(x: number, y: number): void {
    const now = this.now();
    this.keyX.set(x, now);
    this.keyY.set(y, now);
    this.invalidate(KEY_EASE + 0.1);
  }

  // ---- Frames --------------------------------------------------------------

  private pushGlobals(): void {
    const g = this.globals;
    g[GLOBAL.dims + 2] = this.ceremony;
    g[GLOBAL.dims + 3] = this.state.ambient ? 1 : 0;
    g[GLOBAL.mode] = this.mood.direction === 'down' ? 1 : 0;
    g[GLOBAL.mode + 1] = this.mood.light ? 1 : 0;
    g[GLOBAL.mode + 2] = this.reducedMotion ? 1 : 0;
    g[GLOBAL.mode + 3] = this.moreContrast ? 1 : 0;
    this.renderer?.setScene({ globals: g });
  }

  /** The values that ease on the CPU, written in place before a frame. */
  private stepGlobals(now: number): void {
    const g = this.globals;
    g[GLOBAL.lane] = this.laneAcross.value(now);
    g[GLOBAL.lane + 1] = this.laneDown.value(now);
    g[GLOBAL.lane + 2] = this.warmth.value(now);
    g[GLOBAL.key] = this.keyX.value(now);
    g[GLOBAL.key + 1] = this.keyY.value(now);
    g[GLOBAL.key + 2] = this.cellSize * 4;
    g[GLOBAL.key + 3] = this.pointer ? 1 : 0;
    this.renderer?.setScene({ globals: g });
  }

  private touch(): void {
    this.state.lastInput = this.now();
  }

  private invalidate(seconds: number): void {
    const until = this.now() + (this.reducedMotion ? Math.min(seconds, 0.05) : seconds);
    this.state.animateUntil = Math.max(this.state.animateUntil, until);
    this.wake();
  }

  private wake(): void {
    if (this.raf || this.destroyed || document.visibilityState === 'hidden') return;
    this.raf = requestAnimationFrame(this.tick);
  }

  private readonly tick = () => {
    this.raf = 0;
    if (this.destroyed || !this.renderer) return;
    const now = this.now();
    if (frameDue(now, this.state, DEFAULT_SCHEDULE) || this.state.lastFrame < 0) {
      const started = performance.now();
      if (this.boxesDirty || now < this.trackBoxesUntil) this.readBoxesNow();
      this.stepGlobals(now);
      this.renderer.frame(now);
      this.cpuMs = this.cpuMs * 0.9 + (performance.now() - started) * 0.1;
      this.state.lastFrame = now;
      this.framesDrawn += 1;
    }
    if (loopNeeded(now, this.state, DEFAULT_SCHEDULE)) this.raf = requestAnimationFrame(this.tick);
  };

  private lastStats = { frames: 0, at: 0 };

  private showStats(): void {
    const element = this.options.debug;
    if (!element) return;
    const stats = this.renderer?.stats();
    const now = performance.now();
    const fps = this.lastStats.at ? ((this.framesDrawn - this.lastStats.frames) * 1000) / (now - this.lastStats.at) : 0;
    this.lastStats = { frames: this.framesDrawn, at: now };
    element.textContent = stats
      ? `${stats.backend} · gpu ${stats.gpuMs === null ? '–' : stats.gpuMs.toFixed(2)} ms · cpu ${this.cpuMs.toFixed(2)} ms · ${fps.toFixed(0)} fps · ${stats.scale.toFixed(2)}× · ${stats.width}×${stats.height}`
      : 'css (no GPU layer)';
  }
}
