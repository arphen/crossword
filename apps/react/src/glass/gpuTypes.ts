// The slice of WebGPU the glass layer uses, declared locally and structurally
// so the code compiles against any TypeScript DOM library (with or without
// WebGPU in it) and never declares globals. Descriptors stay loose objects:
// the browser validates them, and the layer checks shader compilation itself.

export type Descriptor = Record<string, unknown>;

export interface GpuLike {
  requestAdapter(options?: Descriptor): Promise<GpuAdapter | null>;
  getPreferredCanvasFormat(): string;
}

export interface GpuAdapter {
  readonly features: { has(name: string): boolean };
  requestDevice(options?: Descriptor): Promise<GpuDevice>;
}

export interface GpuDevice {
  readonly features: { has(name: string): boolean };
  readonly queue: GpuQueue;
  readonly lost: Promise<{ reason: string; message: string }>;
  createBuffer(descriptor: Descriptor): GpuBuffer;
  createTexture(descriptor: Descriptor): GpuTexture;
  createSampler(descriptor?: Descriptor): object;
  createShaderModule(descriptor: Descriptor): GpuShaderModule;
  createRenderPipelineAsync(descriptor: Descriptor): Promise<GpuRenderPipeline>;
  createBindGroup(descriptor: Descriptor): object;
  createCommandEncoder(descriptor?: Descriptor): GpuCommandEncoder;
  createQuerySet(descriptor: Descriptor): { destroy(): void };
  addEventListener(type: 'uncapturederror', listener: (event: { error: { message: string } }) => void): void;
  pushErrorScope(filter: string): void;
  popErrorScope(): Promise<{ message: string } | null>;
  destroy(): void;
}

export interface GpuQueue {
  writeBuffer(buffer: GpuBuffer, offset: number, data: ArrayBufferView | ArrayBuffer, dataOffset?: number, size?: number): void;
  submit(buffers: object[]): void;
  onSubmittedWorkDone(): Promise<void>;
}

export interface GpuBuffer {
  mapAsync(mode: number): Promise<void>;
  getMappedRange(): ArrayBuffer;
  unmap(): void;
  destroy(): void;
}

export interface GpuTexture {
  createView(descriptor?: Descriptor): object;
  destroy(): void;
}

export interface GpuShaderModule {
  getCompilationInfo(): Promise<{ messages: ReadonlyArray<{ type: string; message: string; lineNum: number; linePos: number }> }>;
}

export interface GpuRenderPipeline {
  getBindGroupLayout(index: number): object;
}

export interface GpuCommandEncoder {
  beginRenderPass(descriptor: Descriptor): GpuRenderPass;
  resolveQuerySet(querySet: object, first: number, count: number, destination: GpuBuffer, offset: number): void;
  copyBufferToBuffer(source: GpuBuffer, sourceOffset: number, destination: GpuBuffer, destinationOffset: number, size: number): void;
  finish(): object;
}

export interface GpuRenderPass {
  setPipeline(pipeline: GpuRenderPipeline): void;
  setBindGroup(index: number, group: object): void;
  draw(vertexCount: number, instanceCount?: number, firstVertex?: number, firstInstance?: number): void;
  end(): void;
}

export interface GpuCanvasContext {
  configure(configuration: Descriptor): void;
  unconfigure(): void;
  getCurrentTexture(): GpuTexture;
}

/** Spec constants, so no global WebGPU names are needed. */
export const BUFFER = { MAP_READ: 1, COPY_SRC: 4, COPY_DST: 8, UNIFORM: 64, STORAGE: 128, QUERY_RESOLVE: 512 } as const;
export const TEXTURE = { TEXTURE_BINDING: 4, RENDER_ATTACHMENT: 16 } as const;
export const MAP_READ = 1;

/** The browser's WebGPU entry point, when there is one. */
export function gpuEntry(): GpuLike | null {
  if (typeof navigator === 'undefined') return null;
  const gpu = (navigator as unknown as { gpu?: GpuLike }).gpu;
  return gpu && typeof gpu.requestAdapter === 'function' ? gpu : null;
}
