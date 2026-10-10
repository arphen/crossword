// The WebGL2 fallback: the same light over the board and the answer boxes as
// the WebGPU layer (shaders.ts), in GLSL ES 3.00, for browsers without WebGPU.
// The cells and boxes travel as float textures read with texelFetch; the
// notches' glow is worked out where it falls instead of from a light field.

import { BOX_FLOATS } from './boxes';
import { CELL_FLOATS } from './cellState';
import { GLOBAL_FLOATS, type GlassRenderer, type GlassScene, type GlassStats, type LostHandler } from './renderer';

const CELL_TEXELS = CELL_FLOATS / 4;
const BOX_TEXELS = BOX_FLOATS / 4;

const COMMON = /* glsl */ `#version 300 es
precision highp float;
precision highp int;
uniform vec4 u_g[${GLOBAL_FLOATS / 4}];
uniform highp sampler2D u_cells;
uniform highp sampler2D u_boxes;

#define VIEW u_g[0]
#define BOARD u_g[1]
#define GRID u_g[2]
#define DIMS u_g[3]
#define MODE u_g[4]
#define LANE u_g[5]
#define SPILL u_g[6]
#define KEY u_g[7]
#define ORANGE u_g[8]
#define BLUE u_g[9]
#define FLAME u_g[10]
#define RED u_g[14]
#define CLIP_A u_g[15]
#define CLIP_D u_g[16]
#define IMPULSE(k) u_g[17 + (k)]

const uint BLACK = 1u;
const uint LETTER = 16u;
const uint CURSOR = 32u;
const uint WORD = 64u;
const uint CORRECT = 128u;
const uint WRONG = 256u;
const uint SETTLED = 1024u;
const uint NOTCH_E = 2048u;
const uint NOTCH_S = 4096u;
const uint POP = 32768u;
const uint SOLVED_A = 65536u;
const uint SOLVED_D = 131072u;
const float TAU = 6.2831853;
const float FLOOR = 0.24;

float now() { return VIEW.w; }
bool paper() { return MODE.y > 0.5; }
float motion() { return 1.0 - MODE.z; }
float pitch() { return GRID.z; }
int cols() { return int(GRID.w); }
int rows() { return int(DIMS.x); }
bool has(uint f, uint bit) { return (f & bit) != 0u; }
float since(float t) { return max(now() - t, 0.0); }
vec4 cellPart(int i, int part) { return texelFetch(u_cells, ivec2(part, i), 0); }
uint flagsOf(int i) { return uint(cellPart(i, 1).x); }
vec2 hash2(vec2 p) { return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
vec3 roomTint() { return mix(BLUE.rgb, ORANGE.rgb, LANE.z); }

int cellAt(ivec2 c) {
  if (c.x < 0 || c.y < 0 || c.x >= cols() || c.y >= rows()) return -1;
  int i = c.y * cols() + c.x;
  return i < int(DIMS.y) ? i : -1;
}

float spillLevel(float dist, float along) {
  float a0 = clamp(1.0 - dist * 0.42, 0.0, 1.0);
  float a1 = clamp(1.0 - (dist + 1.0) * 0.42, 0.0, 1.0);
  return mix(a0, a1, clamp(along, 0.0, 1.0));
}
float waterLevel(float dist, float along) {
  return max(spillLevel(dist, along), FLOOR * exp(-max(dist + along - 2.4, 0.0) * 0.12));
}

vec3 filamentGlow(vec2 u, vec2 at, bool vertical, vec3 tint, float level) {
  vec2 d = vertical ? vec2(u.x - at.x, max(abs(u.y - at.y) - 0.19, 0.0)) : vec2(max(abs(u.x - at.x) - 0.19, 0.0), u.y - at.y);
  float r = length(d) * pitch();
  float glow = exp(-r / (3.0 + 3.0 * min(LANE.w, 2.0))) * 0.55 + exp(-r / 14.0) * 0.12;
  return tint * glow * level;
}

vec3 notchGlow(vec2 u) {
  ivec2 base = ivec2(floor(u));
  float lit = min(1.0, LANE.w);
  vec3 light = vec3(0.0);
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      ivec2 c = base + ivec2(x, y);
      int i = cellAt(c);
      if (i < 0) continue;
      uint f = flagsOf(i);
      if (!has(f, BLACK)) continue;
      vec4 sa = cellPart(i, 3);
      vec4 sd = cellPart(i, 4);
      vec2 o = vec2(c);
      if (has(f, NOTCH_E)) light += filamentGlow(u, o + vec2(1.0, 0.5), true, sa.w >= 0.0 ? sa.rgb : ORANGE.rgb, lit * LANE.x);
      if (has(f, NOTCH_S)) light += filamentGlow(u, o + vec2(0.5, 1.0), false, sd.w >= 0.0 ? sd.rgb : BLUE.rgb, lit * LANE.y);
    }
  }
  return light;
}

vec3 ripples(vec2 p) {
  float h = 0.0;
  vec2 grad = vec2(0.0);
  for (int k = 0; k < 6; k++) {
    vec4 im = IMPULSE(k);
    float age = now() - im.z;
    if (age < 0.0 || age > 2.6 || im.w <= 0.0) continue;
    vec2 dv = (p - im.xy) / pitch();
    float r = length(dv) + 0.0001;
    float front = age * 5.0;
    float env = im.w * exp(-age * 1.9) * exp(-r * 0.3) * smoothstep(front + 0.9, front - 1.2, r);
    float phase = (r - front) * 2.3;
    h += sin(phase) * env;
    grad += cos(phase) * 2.3 * env * dv / r;
  }
  return vec3(h, grad) * motion();
}

float softness(uint f) {
  if (has(f, SETTLED)) return 0.15;
  if (has(f, SOLVED_A) || has(f, SOLVED_D)) return 0.4;
  if (has(f, LETTER)) return 0.7;
  return 1.0;
}

float fracture(vec2 f, float seed) {
  vec2 p = f * 2.4 + seed * 7.13;
  vec2 base = floor(p);
  float best = 9.0;
  float second = 9.0;
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      vec2 o = base + vec2(float(x), float(y));
      float d = length(p - (o + hash2(o + seed)));
      if (d < best) { second = best; best = d; } else if (d < second) { second = d; }
    }
  }
  return (second - best) / 2.4;
}

float caustic(vec2 u, vec2 bend) {
  float t = now() * 0.32 * DIMS.w * motion() + 23.0;
  vec2 p = (u + bend) * 1.45 - 250.0;
  vec2 q = p;
  float c = 1.0;
  for (int n = 0; n < 4; n++) {
    float tt = t * (1.0 - 3.5 / float(n + 1));
    q = p + vec2(cos(tt - q.x) + sin(tt + q.y), sin(tt - q.y) + cos(tt + q.x));
    c += 1.0 / length(vec2(p.x / (sin(q.x + tt) / 0.006), p.y / (cos(q.y + tt) / 0.006)));
  }
  c /= 4.0;
  c = 1.17 - pow(c, 1.4);
  float net = clamp(pow(abs(c), 8.0), 0.0, 1.5);
  return max(net - 0.12, 0.0) * 1.25;
}

vec3 encode(vec3 c) {
  return mix(1.055 * pow(max(c, 0.0), vec3(1.0 / 2.4)) - 0.055, c * 12.92, vec3(lessThanEqual(c, vec3(0.0031308))));
}

vec3 liquid(int cell, vec2 f, vec2 u, vec3 held, vec3 glow, vec3 wave, float along, bool cursor) {
  uint flags = cell >= 0 ? flagsOf(cell) : 0u;
  float soft = softness(flags);
  vec3 light = held * caustic(u, wave.yz * 0.6 * soft) * 2.6 + glow * 0.05;
  light += (held * 3.0 + glow + roomTint() * 0.04) * max(wave.x, 0.0) * soft * 0.5;
  if (along >= 0.0 && FLAME.w > 0.5) {
    float flow = pow(0.5 + 0.5 * sin((along * 1.6 - now() * 0.45 * DIMS.w) * TAU), 8.0);
    light += FLAME.rgb * (0.03 + 0.07 * flow * motion()) * (1.0 - along * 0.6);
  }
  if (cell < 0) return light;
  vec4 a = cellPart(cell, 1);
  vec4 b = cellPart(cell, 2);
  if (cursor) {
    float breathe = 0.5 + 0.5 * sin(now() * 2.2 * DIMS.w);
    light += FLAME.rgb * (0.04 + 0.03 * breathe * motion() + 0.18 * exp(-since(a.z) * 4.0));
  }
  float pressAge = since(a.w);
  if (pressAge < 1.2) {
    float r = max(abs(f.x - 0.5), abs(f.y - 0.5)) * 2.0;
    float ring = exp(-pow((r - (1.0 - pressAge * 2.2)) / 0.08, 2.0)) * exp(-pressAge * 3.0);
    light += (FLAME.rgb * 0.5 + held * 2.0) * ring * 0.5 * soft * motion();
  }
  if (has(flags, CORRECT)) {
    float t = since(b.x);
    light += vec3(0.55, 0.62, 0.58) * exp(-pow((f.x + f.y) * 0.5 - (t * 1.6 - 0.3), 2.0) * 90.0) * exp(-t * 1.1) * motion();
  }
  if (has(flags, WRONG)) {
    float t = since(b.x);
    float crack = 1.0 - smoothstep(0.0, 0.016, fracture(f, float(cell) * 0.618));
    light += mix(vec3(1.0), RED.rgb, 0.45) * crack * (0.1 + 0.6 * exp(-t * 1.3)) + RED.rgb * 0.12 * exp(-t * 2.0);
  }
  if (has(flags, POP)) {
    float t = since(b.y) - b.z * 0.38;
    if (t > 0.0) {
      vec4 sa = cellPart(cell, 3);
      vec3 tone = has(flags, SOLVED_A) && sa.w >= 0.0 ? sa.rgb : cellPart(cell, 4).rgb;
      light += tone * exp(-t * 3.0) * 0.45;
    }
  }
  return light;
}

vec3 ceremonyAt(vec2 p) {
  float t = now() - DIMS.z;
  if (t <= 0.0 || t >= 5.0) return vec3(0.0);
  float r = length(p - (BOARD.xy + BOARD.zw * 0.5)) / pitch();
  return mix(ORANGE.rgb, BLUE.rgb, 0.5 + 0.5 * sin(r * 0.5)) * exp(-pow(r - t * 4.5, 2.0) * 0.35) * exp(-t * 0.6) * 0.4;
}

vec4 emit(vec3 light) {
  vec3 l = light * (1.0 - 0.5 * MODE.w);
  if (paper()) {
    float peak = max(l.r, max(l.g, l.b));
    return vec4(mix(vec3(1.0), l / max(peak, 0.0001), clamp(peak * 2.2, 0.0, 0.42)), 1.0);
  }
  vec3 o = encode(min(l, vec3(1.0)));
  return vec4(o, max(o.r, max(o.g, o.b)));
}

vec2 viewPoint() { return vec2(gl_FragCoord.x, VIEW.y * VIEW.z - gl_FragCoord.y) / VIEW.z; }
`;

const QUAD_VS = /* glsl */ `#version 300 es
precision highp float;
uniform vec4 u_g[${GLOBAL_FLOATS / 4}];
uniform highp sampler2D u_boxes;
uniform int u_mode;
flat out int v_box;
void main() {
  vec2 corner = vec2(float(gl_VertexID & 1), float(gl_VertexID >> 1));
  vec4 rect = u_mode == 0 ? u_g[1] : texelFetch(u_boxes, ivec2(0, gl_InstanceID), 0);
  vec2 ndc = (rect.xy + corner * rect.zw) / u_g[0].xy * 2.0 - 1.0;
  gl_Position = vec4(ndc.x, -ndc.y, 0.0, 1.0);
  v_box = gl_InstanceID;
}
`;

const BOARD_FS =
  COMMON +
  /* glsl */ `
flat in int v_box;
out vec4 outColor;
void main() {
  vec2 p = viewPoint();
  vec2 u = (p - GRID.xy) / pitch();
  int i = cellAt(ivec2(floor(u)));
  if (i < 0) { outColor = emit(vec3(0.0)); return; }
  uint flags = flagsOf(i);
  vec2 f = u - floor(u);
  vec3 wave = ripples(p);
  if (has(flags, BLACK)) { outColor = emit(notchGlow(u) * 0.12 + ceremonyAt(p)); return; }
  vec4 a = cellPart(i, 1);
  vec4 sa = cellPart(i, 3);
  vec4 sd = cellPart(i, 4);
  vec3 held = vec3(0.0);
  if (sa.w >= 0.0 && !has(flags, SOLVED_A)) held += sa.rgb * waterLevel(sa.w, f.x) * SPILL.x * LANE.x;
  if (sd.w >= 0.0 && !has(flags, SOLVED_D)) held += sd.rgb * waterLevel(sd.w, f.y) * SPILL.x * LANE.y;
  float along = has(flags, WORD) ? max(a.y, 0.0) : -1.0;
  outColor = emit(liquid(i, f, u, held, vec3(0.0), wave, along, has(flags, CURSOR)) + ceremonyAt(p));
}
`;

const BOX_FS =
  COMMON +
  /* glsl */ `
flat in int v_box;
out vec4 outColor;
void main() {
  vec2 p = viewPoint();
  vec4 rect = texelFetch(u_boxes, ivec2(0, v_box), 0);
  vec4 tint = texelFetch(u_boxes, ivec2(1, v_box), 0);
  vec4 info = texelFetch(u_boxes, ivec2(2, v_box), 0);
  float lane = info.y;
  vec4 clip = lane > 0.5 ? CLIP_D : CLIP_A;
  if (any(lessThan(p, clip.xy)) || any(greaterThanEqual(p, clip.xy + clip.zw))) discard;
  uint flags = uint(info.z);
  vec2 f = (p - rect.xy) / rect.zw;
  int cell = int(info.x);
  float live = lane > 0.5 ? LANE.y : LANE.x;
  bool solved = cell >= 0 && has(flagsOf(cell), lane > 0.5 ? SOLVED_D : SOLVED_A);
  vec3 held = !solved && (flags & 64u) != 0u ? tint.rgb * waterLevel(tint.w, f.x) * SPILL.x * live : vec3(0.0);
  float along = (flags & 2u) != 0u ? tint.w / max(info.w - 1.0, 1.0) : -1.0;
  vec2 u = vec2(tint.w + f.x + lane * 7.3, f.y + floor(rect.y / rect.w) * 1.7);
  outColor = emit(liquid(cell, f, u, held, vec3(0.0), vec3(0.0), along, (flags & 1u) != 0u));
}
`;

function compile(gl: WebGL2RenderingContext, vertex: string, fragment: string): WebGLProgram {
  const shader = (type: number, source: string) => {
    const s = gl.createShader(type);
    if (!s) throw new Error('Could not create shader');
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(`Glass shader: ${gl.getShaderInfoLog(s)}`);
    return s;
  };
  const program = gl.createProgram();
  if (!program) throw new Error('Could not create program');
  gl.attachShader(program, shader(gl.VERTEX_SHADER, vertex));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, fragment));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(`Glass program: ${gl.getProgramInfoLog(program)}`);
  return program;
}

export function createWebGl2Glass(canvas: HTMLCanvasElement, onLost: LostHandler): WebGl2Glass {
  const gl = canvas.getContext('webgl2', { premultipliedAlpha: true, antialias: false });
  if (!gl) throw new Error('WebGL2 is not available');
  return new WebGl2Glass(canvas, gl, onLost);
}

interface Program {
  program: WebGLProgram;
  globals: WebGLUniformLocation | null;
  cells: WebGLUniformLocation | null;
  boxes: WebGLUniformLocation | null;
  mode: WebGLUniformLocation | null;
}

export class WebGl2Glass implements GlassRenderer {
  readonly kind = 'webgl2' as const;
  private readonly board: Program;
  private readonly box: Program;
  private readonly vao: WebGLVertexArrayObject;
  private readonly cellTexture: WebGLTexture;
  private readonly boxTexture: WebGLTexture;
  private readonly globals = new Float32Array(GLOBAL_FLOATS);
  private cellCount = 0;
  private boxCount = 0;
  private cssWidth = 1;
  private cssHeight = 1;
  private pixelRatio = 1;
  private destroyed = false;
  private readonly lostListener: (event: Event) => void;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly gl: WebGL2RenderingContext,
    onLost: LostHandler,
  ) {
    const locate = (program: WebGLProgram): Program => ({
      program,
      globals: gl.getUniformLocation(program, 'u_g'),
      cells: gl.getUniformLocation(program, 'u_cells'),
      boxes: gl.getUniformLocation(program, 'u_boxes'),
      mode: gl.getUniformLocation(program, 'u_mode'),
    });
    this.board = locate(compile(gl, QUAD_VS, BOARD_FS));
    this.box = locate(compile(gl, QUAD_VS, BOX_FS));
    const vao = gl.createVertexArray();
    const cells = gl.createTexture();
    const boxes = gl.createTexture();
    if (!vao || !cells || !boxes) throw new Error('Could not create resources');
    this.vao = vao;
    this.cellTexture = cells;
    this.boxTexture = boxes;
    for (const texture of [cells, boxes]) {
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    }
    this.lostListener = (event: Event) => {
      event.preventDefault();
      if (!this.destroyed) onLost('WebGL context lost', false);
    };
    canvas.addEventListener('webglcontextlost', this.lostListener);
  }

  resize(width: number, height: number, pixelRatio: number): void {
    this.cssWidth = Math.max(1, width);
    this.cssHeight = Math.max(1, height);
    this.pixelRatio = Math.min(2, Math.max(1, pixelRatio || 1));
    this.canvas.width = Math.round(this.cssWidth * this.pixelRatio);
    this.canvas.height = Math.round(this.cssHeight * this.pixelRatio);
  }

  private upload(texture: WebGLTexture, texels: number, rows: number, data: Float32Array): void {
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, texels, Math.max(1, rows), 0, gl.RGBA, gl.FLOAT, data, 0);
  }

  setScene(scene: GlassScene): void {
    if (scene.globals) this.globals.set(scene.globals.subarray(0, GLOBAL_FLOATS));
    if (scene.cells) {
      this.cellCount = scene.count ?? Math.floor(scene.cells.length / CELL_FLOATS);
      if (this.cellCount > 0) this.upload(this.cellTexture, CELL_TEXELS, this.cellCount, scene.cells.subarray(0, this.cellCount * CELL_FLOATS));
    }
    if (scene.boxes) {
      this.boxCount = scene.boxCount ?? Math.floor(scene.boxes.length / BOX_FLOATS);
      if (this.boxCount > 0) this.upload(this.boxTexture, BOX_TEXELS, this.boxCount, scene.boxes.subarray(0, this.boxCount * BOX_FLOATS));
    }
  }

  setCellState(index: number, floats: Float32Array): void {
    if (index < 0 || index >= this.cellCount) return;
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, this.cellTexture);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, index, CELL_TEXELS, 1, gl.RGBA, gl.FLOAT, floats, 0);
  }

  frame(time: number): void {
    const gl = this.gl;
    if (this.destroyed || gl.isContextLost() || this.cellCount === 0) return;
    this.globals[0] = this.cssWidth;
    this.globals[1] = this.cssHeight;
    this.globals[2] = this.pixelRatio;
    this.globals[3] = time;
    const paper = this.globals[17] > 0.5;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    // Light over the page is nothing; dye over the page is white.
    gl.clearColor(paper ? 1 : 0, paper ? 1 : 0, paper ? 1 : 0, paper ? 1 : 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.disable(gl.BLEND);
    gl.bindVertexArray(this.vao);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.cellTexture);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, this.boxTexture);
    const use = (p: Program, mode: number) => {
      gl.useProgram(p.program);
      gl.uniform4fv(p.globals, this.globals);
      gl.uniform1i(p.cells, 0);
      gl.uniform1i(p.boxes, 1);
      gl.uniform1i(p.mode, mode);
    };
    use(this.board, 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    if (this.boxCount > 0) {
      use(this.box, 1);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.boxCount);
    }
    gl.bindVertexArray(null);
  }

  stats(): GlassStats {
    return { backend: 'webgl2', gpuMs: null, scale: 1, width: this.canvas.width, height: this.canvas.height };
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.canvas.removeEventListener('webglcontextlost', this.lostListener);
    const gl = this.gl;
    gl.deleteProgram(this.board.program);
    gl.deleteProgram(this.box.program);
    gl.deleteTexture(this.cellTexture);
    gl.deleteTexture(this.boxTexture);
    gl.deleteVertexArray(this.vao);
  }
}
