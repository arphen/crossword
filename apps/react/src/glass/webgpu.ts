// The WebGPU backend: the passes described in shaders.ts, drawn into a
// premultiplied canvas behind the board. Everything a frame needs is built
// ahead (pipelines once, render targets and bind groups per size), so a frame
// writes one small uniform block and records the same passes again.

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
  type GpuRenderPass,
  type GpuRenderPipeline,
  type GpuTexture,
} from './gpuTypes';
import { GLOBAL, GLOBAL_FLOATS, type GlassRenderer, type GlassScene, type GlassStats, type LostHandler } from './renderer';
import { nextRenderScale } from './scheduler';
import { GLASS_WGSL } from './shaders';

const HDR = 'rgba16float';
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
  room: GpuRenderPipeline;
  down: GpuRenderPipeline;
  downBright: GpuRenderPipeline;
  up: GpuRenderPipeline;
  backdrop: GpuRenderPipeline;
  shadow: GpuRenderPipeline;
  tile: GpuRenderPipeline;
  composite: GpuRenderPipeline;
}

const TRANSPARENT = { r: 0, g: 0, b: 0, a: 0 };
const OVER = {
  color: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha', operation: 'add' },
  alpha: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha', operation: 'add' },
};

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
  private readonly sampler: object;
  private pipes: Pipelines | null = null;
  private targets: Record<string, Target> = {};
  private groups: Record<string, object> = {};
  private readonly composite: Descriptor;
  private readonly compositeAttachment: Descriptor;
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
    const full = { module, entryPoint: 'vs_full' };
    const make = (fragment: string, format: string, blend: object | null = null, vertex: string | null = null) =>
      this.device.createRenderPipelineAsync({
        label: `glass ${fragment}`,
        layout: 'auto',
        vertex: vertex ? { module, entryPoint: vertex } : full,
        fragment: { module, entryPoint: fragment, targets: [blend ? { format, blend } : { format }] },
        primitive: { topology: vertex ? 'triangle-strip' : 'triangle-list' },
      });
    const [room, down, downBright, up, backdrop, shadow, tile, composite] = await Promise.all([
      make('fs_background', HDR),
      make('fs_down', HDR),
      make('fs_down_bright', HDR),
      make('fs_up', HDR),
      make('fs_backdrop', HDR),
      make('fs_shadow', HDR, OVER, 'vs_shadow'),
      make('fs_tile', HDR, OVER, 'vs_tile'),
      make('fs_composite', this.format),
    ]);
    this.pipes = { room, down, downBright, up, backdrop, shadow, tile, composite };
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
    if (scene.globals) this.globals.set(scene.globals.subarray(0, GLOBAL_FLOATS));
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
  }

  setCellState(index: number, floats: Float32Array): void {
    if (index < 0 || index >= this.cellCount) return;
    this.device.queue.writeBuffer(this.cellBuffer, index * CELL_FLOATS * 4, floats, 0, CELL_FLOATS);
  }

  frame(time: number): void {
    const pipes = this.pipes;
    const t = this.targets;
    if (!pipes || this.destroyed || !t.hdr) return;
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
    const run = (target: Target, pipeline: GpuRenderPipeline, group: object, draw: (pass: GpuRenderPass) => void = (p) => p.draw(3)) => {
      const pass = encoder.beginRenderPass(target.pass);
      pass.setPipeline(pipeline);
      pass.setBindGroup(0, group);
      draw(pass);
      return pass;
    };
    const timing = sample && this.query;
    if (timing) t.room.pass.timestampWrites = { querySet: this.query.set, beginningOfPassWriteIndex: 0 };
    run(t.room, pipes.room, this.groups.room).end();
    if (timing) delete t.room.pass.timestampWrites;
    run(t.frostHalf, pipes.down, this.groups.frostHalf).end();
    run(t.frostQuarter, pipes.down, this.groups.frostQuarter).end();
    run(t.frost, pipes.up, this.groups.frost).end();
    const scene = run(t.hdr, pipes.backdrop, this.groups.backdrop);
    if (this.cellCount > 0) {
      scene.setPipeline(pipes.shadow);
      scene.setBindGroup(0, this.groups.shadow);
      scene.draw(4, this.cellCount);
      scene.setPipeline(pipes.tile);
      scene.setBindGroup(0, this.groups.tile);
      scene.draw(4, this.cellCount);
    }
    scene.end();
    run(t.bloomA, pipes.downBright, this.groups.bloomA).end();
    run(t.bloomB, pipes.down, this.groups.bloomB).end();
    run(t.bloomC, pipes.down, this.groups.bloomC).end();
    run(t.bloomD, pipes.up, this.groups.bloomD).end();
    run(t.bloomE, pipes.up, this.groups.bloomE).end();
    this.compositeAttachment.view = this.context.getCurrentTexture().createView();
    if (timing) this.composite.timestampWrites = { querySet: this.query.set, endOfPassWriteIndex: 1 };
    const out = encoder.beginRenderPass(this.composite);
    if (timing) delete this.composite.timestampWrites;
    out.setPipeline(pipes.composite);
    out.setBindGroup(0, this.groups.composite);
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

  private target(name: string, divisor: number, format = HDR): Target {
    const width = Math.max(1, Math.round((this.cssWidth * this.pixelRatio * this.scale) / divisor));
    const height = Math.max(1, Math.round((this.cssHeight * this.pixelRatio * this.scale) / divisor));
    const texture = this.device.createTexture({ size: [width, height], format, usage: TEXTURE.RENDER_ATTACHMENT | TEXTURE.TEXTURE_BINDING, label: `glass ${name}` });
    const view = texture.createView();
    return { texture, view, pass: { colorAttachments: [{ view, loadOp: 'clear', storeOp: 'store', clearValue: TRANSPARENT }] } };
  }

  private dropTargets(): void {
    Object.values(this.targets).forEach((target) => target.texture.destroy());
    this.targets = {};
    this.groups = {};
  }

  private rebuild(): void {
    if (!this.pipes || this.destroyed) return;
    this.dropTargets();
    this.targets = {
      room: this.target('room', 2),
      frostHalf: this.target('frost/4', 4),
      frostQuarter: this.target('frost/8', 8),
      frost: this.target('frost', 4),
      hdr: this.target('hdr', 1),
      bloomA: this.target('bloom/2', 2),
      bloomB: this.target('bloom/4', 4),
      bloomC: this.target('bloom/8', 8),
      bloomD: this.target('bloom up/4', 4),
      bloomE: this.target('bloom up/2', 2),
    };
    this.rebuildGroups();
  }

  private rebuildGroups(): void {
    const pipes = this.pipes;
    const t = this.targets;
    if (!pipes || !t.hdr) return;
    const group = (pipeline: GpuRenderPipeline, entries: Array<[number, object]>) =>
      this.device.createBindGroup({ layout: pipeline.getBindGroupLayout(0), entries: entries.map(([binding, resource]) => ({ binding, resource })) });
    const globals = { buffer: this.globalBuffer };
    const cells = { buffer: this.cellBuffer };
    const sample = (view: object): Array<[number, object]> => [
      [2, view],
      [4, this.sampler],
    ];
    this.groups = {
      room: group(pipes.room, [[0, globals]]),
      frostHalf: group(pipes.down, sample(t.room.view)),
      frostQuarter: group(pipes.down, sample(t.frostHalf.view)),
      frost: group(pipes.up, sample(t.frostQuarter.view)),
      backdrop: group(pipes.backdrop, [[0, globals], ...sample(t.room.view)]),
      shadow: group(pipes.shadow, [
        [0, globals],
        [1, cells],
      ]),
      tile: group(pipes.tile, [
        [0, globals],
        [1, cells],
        [2, t.room.view],
        [3, t.frost.view],
        [4, this.sampler],
      ]),
      bloomA: group(pipes.downBright, [[0, globals], ...sample(t.hdr.view)]),
      bloomB: group(pipes.down, sample(t.bloomA.view)),
      bloomC: group(pipes.down, sample(t.bloomB.view)),
      bloomD: group(pipes.up, sample(t.bloomC.view)),
      bloomE: group(pipes.up, sample(t.bloomD.view)),
      composite: group(pipes.composite, [
        [0, globals],
        [2, t.hdr.view],
        [3, t.bloomE.view],
        [4, this.sampler],
      ]),
    };
  }
}
