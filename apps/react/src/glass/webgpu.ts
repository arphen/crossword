// The WebGPU backend: the gel pass described in shaders.ts, drawn at the
// render scale and copied into a premultiplied canvas behind the board.
// Everything a frame needs is built ahead (pipelines once, the target and
// bind groups per size), so a frame writes one small uniform block and
// records the same two passes again.

import { BOX_FLOATS } from './boxes';
import { CELL_FLOATS } from './cellState';
import {
  BUFFER,
  MAP_READ,
  TEXTURE,
  gpuEntry,
  type Descriptor,
  type GpuBuffer,
  type GpuCanvasContext,
  type GpuDevice,
  type GpuRenderPipeline,
  type GpuTexture,
} from './gpuTypes';
import { GLOBAL, GLOBAL_FLOATS, type GlassRenderer, type GlassScene, type GlassStats, type LostHandler } from './renderer';
import { nextRenderScale } from './scheduler';
import { GLASS_WGSL } from './shaders';

const SCENE = 'rgba8unorm';
const FIELD = 'rgba16float';
/** Light-field texels per square (FIELD in shaders.ts). */
const FIELD_TEXELS = 8;
/** GPU budget per frame the render scale is held to (ms). */
const BUDGET_MS = 4;
/** How often the GPU time is sampled (frames). */
const SAMPLE_EVERY = 20;

interface Target {
  texture: GpuTexture;
  view: object;
  pass: Descriptor;
}

interface Pipelines {
  field: GpuRenderPipeline;
  gel: GpuRenderPipeline;
  box: GpuRenderPipeline;
  copy: GpuRenderPipeline;
}

const TRANSPARENT = { r: 0, g: 0, b: 0, a: 0 };
const WHITE = { r: 1, g: 1, b: 1, a: 1 };

export interface WebGpuOptions {
  /** Hold the render scale here instead of following the frame budget. */
  fixedScale?: number | null;
}

export async function createWebGpuGlass(canvas: HTMLCanvasElement, onLost: LostHandler, options: WebGpuOptions = {}): Promise<WebGpuGlass> {
  const gpu = gpuEntry();
  if (!gpu) throw new Error('WebGPU is not available');
  const adapter = await gpu.requestAdapter({ powerPreference: 'high-performance' });
  if (!adapter) throw new Error('No WebGPU adapter');
  const timestamps = adapter.features.has('timestamp-query');
  const device = await adapter.requestDevice({ requiredFeatures: timestamps ? ['timestamp-query'] : [] });
  const context = canvas.getContext('webgpu') as unknown as GpuCanvasContext | null;
  if (!context) {
    device.destroy();
    throw new Error('No WebGPU canvas context');
  }
  const format = gpu.getPreferredCanvasFormat();
  context.configure({ device, format, alphaMode: 'premultiplied' });
  const module = device.createShaderModule({ code: GLASS_WGSL, label: 'glass' });
  const info = await module.getCompilationInfo();
  const errors = info.messages.filter((message) => message.type === 'error');
  if (errors.length) {
    device.destroy();
    throw new Error(`Glass shaders failed: ${errors.map((e) => `${e.lineNum}:${e.linePos} ${e.message}`).join('; ')}`);
  }
  const glass = new WebGpuGlass(canvas, device, context, format, timestamps, onLost, options);
  await glass.build(module);
  return glass;
}

export class WebGpuGlass implements GlassRenderer {
  readonly kind = 'webgpu' as const;
  private readonly globals = new Float32Array(GLOBAL_FLOATS);
  private readonly globalBuffer: GpuBuffer;
  private cellBuffer: GpuBuffer;
  private cellCapacity = 1;
  private cellCount = 0;
  private boxBuffer: GpuBuffer;
  private boxCapacity = 1;
  private boxCount = 0;
  private paper = false;
  private readonly sampler: object;
  private pipes: Pipelines | null = null;
  private targets: Record<string, Target> = {};
  private groups: Record<string, object> = {};
  private readonly composite: Descriptor;
  private readonly compositeAttachment: Descriptor;
  private fieldSize: [number, number] = [0, 0];
  private cssWidth = 1;
  private cssHeight = 1;
  private pixelRatio = 1;
  private scale = 1;
  private calm = 0;
  private frames = 0;
  private gpuMs: number | null = null;
  private destroyed = false;
  private sampling = false;
  /** Frames submitted and not yet finished on the GPU. */
  private inFlight = 0;
  private readonly finished = () => {
    this.inFlight -= 1;
  };
  private readonly query: { set: { destroy(): void }; resolve: GpuBuffer; read: GpuBuffer } | null = null;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly device: GpuDevice,
    private readonly context: GpuCanvasContext,
    private readonly format: string,
    timestamps: boolean,
    private readonly onLost: LostHandler,
    private readonly options: WebGpuOptions,
  ) {
    this.scale = options.fixedScale ?? 1;
    this.globalBuffer = device.createBuffer({ size: GLOBAL_FLOATS * 4, usage: BUFFER.UNIFORM | BUFFER.COPY_DST, label: 'glass globals' });
    this.cellBuffer = device.createBuffer({ size: CELL_FLOATS * 4, usage: BUFFER.STORAGE | BUFFER.COPY_DST, label: 'glass cells' });
    this.boxBuffer = device.createBuffer({ size: BOX_FLOATS * 4, usage: BUFFER.STORAGE | BUFFER.COPY_DST, label: 'glass boxes' });
    this.sampler = device.createSampler({ magFilter: 'linear', minFilter: 'linear', addressModeU: 'clamp-to-edge', addressModeV: 'clamp-to-edge' });
    this.compositeAttachment = { view: null, loadOp: 'clear', storeOp: 'store', clearValue: TRANSPARENT };
    this.composite = { colorAttachments: [this.compositeAttachment] };
    if (timestamps) {
      this.query = {
        set: device.createQuerySet({ type: 'timestamp', count: 2 }),
        resolve: device.createBuffer({ size: 16, usage: BUFFER.QUERY_RESOLVE | BUFFER.COPY_SRC }),
        read: device.createBuffer({ size: 16, usage: BUFFER.MAP_READ | BUFFER.COPY_DST }),
      };
    }
    // Validation errors are a bug in the layer: say so once, in the console.
    let reported = 0;
    device.addEventListener('uncapturederror', (event) => {
      if (reported++ < 3) console.warn('[glass] WebGPU error:', event.error.message);
    });
    device.lost.then((info) => {
      if (this.destroyed) return;
      this.pipes = null;
      this.onLost(info.message || info.reason || 'device lost', false);
    });
  }

  async build(module: object): Promise<void> {
    const make = (vertex: string, fragment: string, format: string, topology = 'triangle-list') =>
      this.device.createRenderPipelineAsync({
        label: `glass ${fragment}`,
        layout: 'auto',
        vertex: { module, entryPoint: vertex },
        fragment: { module, entryPoint: fragment, targets: [{ format }] },
        primitive: { topology },
      });
    const [field, gel, box, copy] = await Promise.all([
      make('vs_full', 'fs_field', FIELD),
      make('vs_board', 'fs_gel', SCENE, 'triangle-strip'),
      make('vs_box', 'fs_box', SCENE, 'triangle-strip'),
      make('vs_copy', 'fs_copy', this.format),
    ]);
    this.pipes = { field, gel, box, copy };
    this.rebuild();
  }

  resize(width: number, height: number, pixelRatio: number): void {
    this.cssWidth = Math.max(1, width);
    this.cssHeight = Math.max(1, height);
    this.pixelRatio = Math.min(2, Math.max(1, pixelRatio || 1));
    this.canvas.width = Math.max(1, Math.round(this.cssWidth * this.pixelRatio));
    this.canvas.height = Math.max(1, Math.round(this.cssHeight * this.pixelRatio));
    this.rebuild();
  }

  setScene(scene: GlassScene): void {
    if (scene.globals) {
      this.globals.set(scene.globals.subarray(0, GLOBAL_FLOATS));
      const columns = Math.max(1, Math.round(this.globals[GLOBAL.grid + 3]));
      const rows = Math.max(1, Math.round(this.globals[GLOBAL.dims]));
      const paper = this.globals[GLOBAL.mode + 1] > 0.5;
      if (paper !== this.paper) {
        this.paper = paper;
        this.rebuild();
      }
      if (columns !== this.fieldSize[0] || rows !== this.fieldSize[1]) {
        this.fieldSize = [columns, rows];
        this.rebuild();
      }
    }
    if (scene.cells) {
      const count = scene.count ?? Math.floor(scene.cells.length / CELL_FLOATS);
      if (count > this.cellCapacity) {
        this.cellBuffer.destroy();
        this.cellCapacity = Math.max(count, Math.ceil(this.cellCapacity * 1.5));
        this.cellBuffer = this.device.createBuffer({ size: this.cellCapacity * CELL_FLOATS * 4, usage: BUFFER.STORAGE | BUFFER.COPY_DST, label: 'glass cells' });
        this.rebuildGroups();
      }
      this.cellCount = count;
      if (count > 0) this.device.queue.writeBuffer(this.cellBuffer, 0, scene.cells, 0, count * CELL_FLOATS);
    }
    if (scene.boxes) {
      const count = scene.boxCount ?? Math.floor(scene.boxes.length / BOX_FLOATS);
      if (count > this.boxCapacity) {
        this.boxBuffer.destroy();
        this.boxCapacity = Math.max(count, Math.ceil(this.boxCapacity * 1.5));
        this.boxBuffer = this.device.createBuffer({ size: this.boxCapacity * BOX_FLOATS * 4, usage: BUFFER.STORAGE | BUFFER.COPY_DST, label: 'glass boxes' });
        this.rebuildGroups();
      }
      this.boxCount = count;
      if (count > 0) this.device.queue.writeBuffer(this.boxBuffer, 0, scene.boxes, 0, count * BOX_FLOATS);
    }
  }

  setCellState(index: number, floats: Float32Array): void {
    if (index < 0 || index >= this.cellCount) return;
    this.device.queue.writeBuffer(this.cellBuffer, index * CELL_FLOATS * 4, floats, 0, CELL_FLOATS);
  }

  frame(time: number): void {
    const pipes = this.pipes;
    const t = this.targets;
    if (!pipes || this.destroyed || !t.scene || this.cellCount === 0) return;
    // Never queue work faster than the GPU finishes it: with two frames in
    // flight, this one is skipped (the next due frame draws the latest state).
    if (this.inFlight >= 2) return;
    this.globals[GLOBAL.view] = this.cssWidth;
    this.globals[GLOBAL.view + 1] = this.cssHeight;
    this.globals[GLOBAL.view + 2] = this.pixelRatio * this.scale;
    this.globals[GLOBAL.view + 3] = time;
    this.device.queue.writeBuffer(this.globalBuffer, 0, this.globals);
    const sample = this.frames % SAMPLE_EVERY === 0 && !this.sampling;
    this.frames += 1;
    const encoder = this.device.createCommandEncoder();
    const timing = sample && this.query;
    const lit = t.field.pass;
    if (timing) lit.timestampWrites = { querySet: this.query.set, beginningOfPassWriteIndex: 0 };
    const field = encoder.beginRenderPass(lit);
    if (timing) delete lit.timestampWrites;
    field.setPipeline(pipes.field);
    field.setBindGroup(0, this.groups.field);
    field.draw(3);
    field.end();
    const gel = encoder.beginRenderPass(t.scene.pass);
    gel.setPipeline(pipes.gel);
    gel.setBindGroup(0, this.groups.gel);
    gel.draw(4);
    if (this.boxCount > 0) {
      gel.setPipeline(pipes.box);
      gel.setBindGroup(0, this.groups.box);
      gel.draw(4, this.boxCount);
    }
    gel.end();
    this.compositeAttachment.view = this.context.getCurrentTexture().createView();
    if (timing) this.composite.timestampWrites = { querySet: this.query.set, endOfPassWriteIndex: 1 };
    const out = encoder.beginRenderPass(this.composite);
    if (timing) delete this.composite.timestampWrites;
    out.setPipeline(pipes.copy);
    out.setBindGroup(0, this.groups.copy);
    out.draw(3);
    out.end();
    if (timing) {
      encoder.resolveQuerySet(this.query.set, 0, 2, this.query.resolve, 0);
      encoder.copyBufferToBuffer(this.query.resolve, 0, this.query.read, 0, 16);
    }
    this.device.queue.submit([encoder.finish()]);
    this.inFlight += 1;
    this.device.queue.onSubmittedWorkDone().then(this.finished, this.finished);
    if (sample) this.measure(Boolean(timing));
  }

  stats(): GlassStats {
    return {
      backend: 'webgpu',
      gpuMs: this.gpuMs,
      scale: this.scale,
      width: Math.round(this.cssWidth * this.pixelRatio * this.scale),
      height: Math.round(this.cssHeight * this.pixelRatio * this.scale),
    };
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.dropTargets();
    this.cellBuffer.destroy();
    this.boxBuffer.destroy();
    this.globalBuffer.destroy();
    this.query?.set.destroy();
    this.query?.resolve.destroy();
    this.query?.read.destroy();
    try {
      this.context.unconfigure();
    } catch {
      // A lost context has nothing left to unconfigure.
    }
    this.device.destroy();
  }

  // GPU time, sampled every few frames: from timestamp queries when the
  // device has them, otherwise from submission to completion (an upper bound).
  private measure(timestamps: boolean): void {
    this.sampling = true;
    const started = performance.now();
    const settle = (ms: number | null) => {
      this.sampling = false;
      if (ms === null || this.destroyed) return;
      this.gpuMs = ms;
      if (this.options.fixedScale) return;
      // Samples come every SAMPLE_EVERY frames: six calm ones is two seconds.
      const next = nextRenderScale(this.scale, ms, BUDGET_MS, this.calm, { min: 0.5, max: 1, calmNeeded: 6 });
      this.calm = next.calmFrames;
      if (Math.abs(next.scale - this.scale) > 0.001) {
        this.scale = next.scale;
        this.rebuild();
      }
    };
    if (timestamps && this.query) {
      const read = this.query.read;
      read
        .mapAsync(MAP_READ)
        .then(() => {
          const times = new BigInt64Array(read.getMappedRange());
          const ms = Number(times[1] - times[0]) / 1e6;
          read.unmap();
          settle(ms > 0 && ms < 1000 ? ms : null);
        })
        .catch(() => settle(null));
      return;
    }
    this.device.queue
      .onSubmittedWorkDone()
      .then(() => settle(performance.now() - started))
      .catch(() => settle(null));
  }

  private target(name: string, divisor: number, format = SCENE, size: [number, number] | null = null, clear = TRANSPARENT): Target {
    const width = size ? size[0] : Math.max(1, Math.round((this.cssWidth * this.pixelRatio * this.scale) / divisor));
    const height = size ? size[1] : Math.max(1, Math.round((this.cssHeight * this.pixelRatio * this.scale) / divisor));
    const texture = this.device.createTexture({ size: [width, height], format, usage: TEXTURE.RENDER_ATTACHMENT | TEXTURE.TEXTURE_BINDING, label: `glass ${name}` });
    const view = texture.createView();
    return { texture, view, pass: { colorAttachments: [{ view, loadOp: 'clear', storeOp: 'store', clearValue: clear }] } };
  }

  private dropTargets(): void {
    Object.values(this.targets).forEach((target) => target.texture.destroy());
    this.targets = {};
    this.groups = {};
  }

  private rebuild(): void {
    if (!this.pipes || this.destroyed) return;
    this.dropTargets();
    const [columns, rows] = this.fieldSize;
    this.targets = {
      // Light over the page is nothing; dye over the page is white.
      scene: this.target('scene', 1, SCENE, null, this.paper ? WHITE : TRANSPARENT),
      field: this.target('field', 1, FIELD, [Math.max(1, (columns + 2) * FIELD_TEXELS), Math.max(1, (rows + 2) * FIELD_TEXELS)]),
    };
    this.rebuildGroups();
  }

  private rebuildGroups(): void {
    const pipes = this.pipes;
    const t = this.targets;
    if (!pipes || !t.scene) return;
    const group = (pipeline: GpuRenderPipeline, entries: Array<[number, object]>) =>
      this.device.createBindGroup({ layout: pipeline.getBindGroupLayout(0), entries: entries.map(([binding, resource]) => ({ binding, resource })) });
    const globals = { buffer: this.globalBuffer };
    const cells = { buffer: this.cellBuffer };
    this.groups = {
      field: group(pipes.field, [
        [0, globals],
        [1, cells],
      ]),
      gel: group(pipes.gel, [
        [0, globals],
        [1, cells],
        [3, t.field.view],
        [4, this.sampler],
      ]),
      box: group(pipes.box, [
        [0, globals],
        [1, cells],
        [5, { buffer: this.boxBuffer }],
      ]),
      copy: group(pipes.copy, [
        [2, t.scene.view],
        [4, this.sampler],
      ]),
    };
  }
}
