// The glass layer's engine, free of React: it watches the board the CSS draws
// (layout, classes, marks, focus, typing), keeps the cell buffer in step,
// picks a backend (WebGPU, then WebGL2, then none, which leaves the CSS board
// as it is), recovers from a lost device, and decides when a frame is worth
// drawing. The DOM is the source of truth; this only ever reads it.

import { CellBook, FLAG, readCellFacts, sweepPositions } from './cellState';
import type { GlassFlag } from './flag';
import { gpuEntry } from './gpuTypes';
import { glassPalette, paletteFloats } from './palette';
import { GLOBAL, GLOBAL_FLOATS, type GlassRenderer } from './renderer';
import { DEFAULT_SCHEDULE, frameDue, loopNeeded } from './scheduler';
import { createWebGl2Glass } from './webgl2';
import { createWebGpuGlass } from './webgpu';

export type GlassBackend = 'webgpu' | 'webgl2' | null;

export interface GlassMood {
  /** 0 Sunday … 6 Saturday. */
  weekday: number;
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

const MARGIN_CELLS = 1.1;
const LIGHT_EASE = 0.9;
const RESTART_LIMIT = 3;

/** How long a change keeps the layer drawing, by what began (seconds). */
function animationFor(began: number, flags: number): number {
  let seconds = 0.45;
  if (began & FLAG.CURSOR) seconds = Math.max(seconds, 1.0);
  if (began & (FLAG.CORRECT | FLAG.WRONG)) seconds = Math.max(seconds, 1.6);
  if (began & FLAG.POP) seconds = Math.max(seconds, 2.2);
  if (flags & FLAG.FLARE) seconds = Math.max(seconds, 1.0);
  return seconds;
}

export class GlassEngine {
  private renderer: GlassRenderer | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private readonly book = new CellBook(225);
  private elements: HTMLElement[] = [];
  private readonly index = new Map<Element, number>();
  private readonly positions: Array<{ row: number; column: number }> = [];
  private readonly globals = new Float32Array(GLOBAL_FLOATS);
  private readonly palette = new Float32Array(12 * 4);
  private readonly epoch = performance.now();
  private readonly state = { animateUntil: 0, lastFrame: -1, lastInput: 0, ambient: true };
  private raf = 0;
  private destroyed = false;
  private restarts = 0;
  private mood: GlassMood = { weekday: 1, light: false, direction: 'across' };
  private cellSize = 32;
  private origin = { x: 0, y: 0 };
  private allSettled = false;
  private ceremony = -1000;
  private reducedMotion = false;
  private moreContrast = false;
  private lightTo = { x: 0, y: 0 };
  private pointer: { x: number; y: number } | null = null;
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
    const changed = mood.weekday !== this.mood.weekday || mood.light !== this.mood.light || mood.direction !== this.mood.direction;
    this.mood = mood;
    if (!changed) return;
    paletteFloats(glassPalette(mood.weekday, mood.light), this.palette);
    this.pushGlobals();
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
        paletteFloats(glassPalette(this.mood.weekday, this.mood.light), this.palette);
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
  // so it can be swapped without React's knowledge.
  private freshCanvas(): HTMLCanvasElement {
    this.dropCanvas();
    const canvas = document.createElement('canvas');
    canvas.className = 'glass-canvas';
    canvas.setAttribute('aria-hidden', 'true');
    this.options.grid.parentElement?.insertBefore(canvas, this.options.grid);
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
        this.aimLightAt(lastCursor);
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
      this.book.press(index, this.now());
      this.renderer?.setCellState(index, this.book.slice(index));
      this.touch();
      this.invalidate(0.6);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Backspace' || event.key === 'Delete') typed(event);
    };
    const move = (event: PointerEvent) => {
      if (!this.canvas) return;
      const rect = this.canvas.getBoundingClientRect();
      this.pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      this.aimLight(this.pointer.x - this.cellSize * 0.6, this.pointer.y - this.cellSize * 1.2);
      this.touch();
    };
    const leave = () => {
      this.pointer = null;
      if (lastCursor !== undefined) this.aimLightAt(lastCursor);
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
    const container = grid.parentElement;
    if (!renderer || !container) return;
    const elements = [...grid.querySelectorAll<HTMLElement>('.grid-cell')];
    const boxes = elements.map((element) => element.getBoundingClientRect());
    const gridBox = grid.getBoundingClientRect();
    const containerBox = container.getBoundingClientRect();
    this.cellSize = boxes[0]?.width || 32;
    const margin = Math.round(this.cellSize * MARGIN_CELLS);
    const left = gridBox.left - containerBox.left - margin;
    const top = gridBox.top - containerBox.top - margin;
    const width = gridBox.width + margin * 2;
    const height = gridBox.height + margin * 2;
    const canvas = this.canvas;
    if (!canvas) return;
    canvas.style.left = `${left}px`;
    canvas.style.top = `${top}px`;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    this.origin = { x: gridBox.left - margin, y: gridBox.top - margin };

    const rebuilt = elements.length !== this.elements.length || elements.some((element, i) => element !== this.elements[i]);
    if (rebuilt) {
      this.elements = elements;
      this.index.clear();
      this.positions.length = 0;
      elements.forEach((element, i) => {
        this.index.set(element, i);
        const row = element.parentElement;
        this.positions.push({ row: row ? [...grid.children].indexOf(row) : 0, column: row ? [...row.children].indexOf(element) : 0 });
      });
      this.book.reset(elements.length);
    }
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
    const board = Number.isFinite(minX) ? [minX, minY, maxX - minX, maxY - minY] : [margin, margin, gridBox.width, gridBox.height];
    this.globals.set(board, GLOBAL.board);
    renderer.resize(width, height, window.devicePixelRatio || 1);
    renderer.setScene({ cells: this.book.data, count: this.book.count });
    if (!this.lightTo.x && !this.lightTo.y) {
      this.lightTo = { x: board[0] + board[2] * 0.3, y: board[1] - this.cellSize * 2 };
      this.globals.set([this.lightTo.x, this.lightTo.y, this.lightTo.x, this.lightTo.y], GLOBAL.light);
    }
    this.pushGlobals();
    this.invalidate(0.4);
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
      if (this.book.update(i, facts, now, popAt.get(i) ?? 0)) {
        renderer.setCellState(i, this.book.slice(i));
        seconds = Math.max(seconds, animationFor(facts.flags & ~before, facts.flags));
      }
    }
    this.dirty.clear();
    const settled = this.everySquareSettled();
    if (settled && !this.allSettled) {
      this.ceremony = now;
      this.pushGlobals();
      seconds = Math.max(seconds, 4.5);
    }
    this.allSettled = settled;
    if (seconds > 0) {
      this.touch();
      this.invalidate(seconds);
    }
  }

  // ---- Light ---------------------------------------------------------------

  private aimLightAt(index: number): void {
    if (this.pointer) return;
    const base = index * 12;
    const x = this.book.data[base] + this.book.data[base + 2] * 0.5;
    const y = this.book.data[base + 1] + this.book.data[base + 3] * 0.5;
    this.aimLight(x - this.cellSize * 1.2, y - this.cellSize * 2.4);
  }

  /** Send the key light somewhere, easing from wherever it is now. */
  private aimLight(x: number, y: number): void {
    const g = this.globals;
    const now = this.now();
    const k = Math.min(1, Math.max(0, (now - g[GLOBAL.lightTiming]) / LIGHT_EASE));
    const e = k * k * (3 - 2 * k);
    const fromX = g[GLOBAL.light] + (g[GLOBAL.light + 2] - g[GLOBAL.light]) * e;
    const fromY = g[GLOBAL.light + 1] + (g[GLOBAL.light + 3] - g[GLOBAL.light + 1]) * e;
    g[GLOBAL.light] = fromX;
    g[GLOBAL.light + 1] = fromY;
    g[GLOBAL.light + 2] = x;
    g[GLOBAL.light + 3] = y;
    g[GLOBAL.lightTiming] = now;
    this.lightTo = { x, y };
    this.pushGlobals();
    this.invalidate(LIGHT_EASE + 0.1);
  }

  // ---- Frames --------------------------------------------------------------

  private pushGlobals(): void {
    const g = this.globals;
    g[GLOBAL.lightTiming + 1] = LIGHT_EASE;
    g[GLOBAL.lightTiming + 2] = this.cellSize;
    g[GLOBAL.lightTiming + 3] = this.book.count;
    g[GLOBAL.mode] = this.mood.direction === 'down' ? 1 : 0;
    g[GLOBAL.mode + 1] = this.mood.light ? 1 : 0;
    g[GLOBAL.mode + 2] = this.reducedMotion ? 1 : 0;
    g[GLOBAL.mode + 3] = this.moreContrast ? 1 : 0;
    g[GLOBAL.events] = this.ceremony;
    g[GLOBAL.events + 1] = this.state.ambient ? 1 : 0;
    g[GLOBAL.events + 2] = this.mood.light ? 2.3 : 1.05;
    g.set(this.palette, GLOBAL.palette);
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
