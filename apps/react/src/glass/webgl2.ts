// The WebGL2 fallback: the same squares, the same lights and states, drawn in
// one pass without the frosted room, the bloom or the dispersion. Each draw
// tone maps and encodes its own colour, so it blends straight onto the page.

import { CELL_FLOATS } from './cellState';
import { GLOBAL_FLOATS, type GlassRenderer, type GlassScene, type GlassStats, type LostHandler } from './renderer';

const HEADER = /* glsl */ `#version 300 es
precision highp float;
uniform vec4 u_g[${GLOBAL_FLOATS / 4}];
#define VIEW u_g[0]
#define BOARD u_g[1]
#define LIGHT u_g[2]
#define LIGHT_T u_g[3]
#define MODE u_g[4]
#define EVENTS u_g[5]
#define PAL(i) u_g[6 + (i)].rgb
const int SKY_LOW = 0; const int SKY_HIGH = 1; const int CAUSTIC = 2; const int GLASS = 3; const int OBSIDIAN = 4;
const int SHADE = 5; const int RING = 6; const int ACROSS = 7; const int DOWN = 8; const int CORRECT = 9; const int WRONG = 10; const int KEY = 11;
float cellSize() { return max(LIGHT_T.z, 8.0); }
bool paper() { return MODE.y > 0.5; }
float motion() { return 1.0 - MODE.z; }
float hash21(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float noise(vec2 p) { vec2 i = floor(p); vec2 f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash21(i), hash21(i + vec2(1, 0)), u.x), mix(hash21(i + vec2(0, 1)), hash21(i + vec2(1, 1)), u.x), u.y); }
float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int k = 0; k < 3; k++) { s += a * noise(p); p = p * 2.03 + vec2(17.1, 9.2); a *= 0.5; } return s; }
vec2 lightPos() { float k = clamp((VIEW.w - LIGHT_T.x) / max(LIGHT_T.y, 0.001), 0.0, 1.0); k = k * k * (3.0 - 2.0 * k); return mix(LIGHT.xy, LIGHT.zw, k); }
vec3 room(vec2 px) {
  vec2 p = px / (cellSize() * 4.5); float t = VIEW.w * 0.035 * motion();
  float a = fbm(p * 0.8 + vec2(fbm(p + t), fbm(p - t)) * 2.0);
  vec3 c = mix(PAL(SKY_LOW), PAL(SKY_HIGH), smoothstep(0.28, 0.88, a));
  vec2 w = p * 3.1; float caustic = pow((0.5 + 0.5 * sin(w.x * 2.7 + sin(w.y * 1.9 + t * 3.0) * 1.6)) * (0.5 + 0.5 * sin(w.y * 2.3 + sin(w.x * 2.2 - t * 2.4) * 1.6)), 5.0);
  return c + PAL(CAUSTIC) * caustic * 0.3 * (0.35 + 0.65 * a);
}
float sdRoundBox(vec2 p, vec2 b, float r) { vec2 q = abs(p) - b + vec2(r); return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r; }
vec2 sdGrad(vec2 p, vec2 b, float r) { vec2 q = abs(p) - b + vec2(r); vec2 s = vec2(p.x >= 0.0 ? 1.0 : -1.0, p.y >= 0.0 ? 1.0 : -1.0);
  if (max(q.x, q.y) > 0.0) return s * normalize(max(q, 0.0) + 1e-5); return q.x > q.y ? vec2(s.x, 0.0) : vec2(0.0, s.y); }
vec3 tonemap(vec3 c) { c *= EVENTS.z; c = clamp((c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14), 0.0, 1.0);
  return mix(1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, c * 12.92, vec3(lessThanEqual(c, vec3(0.0031308)))); }
`;

const FULL_VS = /* glsl */ `#version 300 es
out vec2 v_uv;
void main() { vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2)); v_uv = vec2(p.x, 1.0 - p.y); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }
`;

const BACKDROP_FS = `${HEADER}
in vec2 v_uv; out vec4 o;
void main() {
  vec2 px = v_uv * VIEW.xy; float cs = cellSize();
  vec2 center = BOARD.xy + BOARD.zw * 0.5;
  float d = sdRoundBox(px - center, BOARD.zw * 0.5 + vec2(cs * 0.16), cs * 0.36);
  float inside = 1.0 - smoothstep(-1.0, 1.0, d);
  vec3 col = room(px) * (paper() ? 0.9 : 0.42) + PAL(KEY) * exp(-abs(d + 1.0) * 0.5) * 0.12;
  float shadow = (1.0 - smoothstep(-cs * 0.1, cs * 1.3, d)) * (paper() ? 0.22 : 0.6) * (1.0 - inside);
  o = vec4(tonemap(col) * inside, inside + shadow);
}
`;

const TILE_VS = /* glsl */ `#version 300 es
precision highp float;
layout(location = 0) in vec4 a_rect;
layout(location = 1) in vec4 a_b;
layout(location = 2) in vec4 a_c;
uniform vec4 u_g[${GLOBAL_FLOATS / 4}];
uniform float u_pad;
out vec2 v_local; out vec2 v_screen; flat out vec4 v_rect; flat out vec4 v_b; flat out vec4 v_c;
void main() {
  vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
  float cs = max(u_g[3].z, 8.0);
  vec2 hb = a_rect.zw * 0.5 + vec2(cs * u_pad);
  vec2 screen = a_rect.xy + a_rect.zw * 0.5 + corner * hb;
  v_local = corner * hb; v_screen = screen; v_rect = a_rect; v_b = a_b; v_c = a_c;
  gl_Position = vec4(screen / u_g[0].xy * vec2(2.0, -2.0) + vec2(-1.0, 1.0), 0.0, 1.0);
}
`;

const SHADOW_FS = `${HEADER}
in vec2 v_local; in vec2 v_screen; flat in vec4 v_rect; flat in vec4 v_b; flat in vec4 v_c; out vec4 o;
void main() {
  float cs = cellSize(); int flags = int(v_b.x + 0.5);
  float lift = (flags & 32) != 0 ? 1.0 : 0.0;
  vec2 away = normalize(v_screen - lightPos() + vec2(0.0, 1e-3));
  vec2 hb = v_rect.zw * 0.5 - vec2(max(1.0, cs * 0.05));
  float blur = cs * (0.06 + 0.13 * lift);
  float d = sdRoundBox(v_local - away * cs * (0.035 + 0.11 * lift), hb, cs * 0.17);
  float strength = (paper() ? 0.3 : 0.55) * ((flags & 1) != 0 ? 0.35 : 1.0);
  o = vec4(0.0, 0.0, 0.0, (1.0 - smoothstep(-blur, blur, d)) * strength);
}
`;

const TILE_FS = `${HEADER}
in vec2 v_local; in vec2 v_screen; flat in vec4 v_rect; flat in vec4 v_b; flat in vec4 v_c; out vec4 o;
void main() {
  float cs = cellSize(); float t = VIEW.w; float m = motion(); float px = 1.0 / VIEW.z;
  int flags = int(v_b.x + 0.5);
  bool black = (flags & 1) != 0; bool cursor = (flags & 32) != 0;
  float lift = cursor ? mix(1.0, 1.0 - exp(-(t - v_b.z) * 9.0) * cos((t - v_b.z) * 13.0), m) : 0.0;
  float pressAge = t - v_b.w; float press = (pressAge > 0.0 && pressAge < 2.0) ? exp(-pressAge * 15.0) * sin(pressAge * 28.0) * m : 0.0;
  float popAge = t - v_c.y - v_c.z * 0.32; float pop = (popAge > -0.3 && popAge < 1.4) ? exp(-popAge * popAge * 26.0) : 0.0;
  float scale = 1.0 + 0.05 * lift - 0.05 * press + 0.035 * pop * m;
  vec2 local = (v_local - vec2(0.0, -cs * 0.03 * lift)) / scale;
  vec2 hb = v_rect.zw * 0.5 - vec2(max(1.0, cs * 0.05));
  float radius = cs * 0.17;
  float d = sdRoundBox(local, hb, radius);
  float coverage = 1.0 - smoothstep(-px, px, d);
  if (d > cs * 0.55) discard;
  float bevel = cs * (black ? 0.1 : 0.17);
  float s = clamp(-d / bevel, 0.0, 1.0);
  vec2 grad = sdGrad(local, hb, radius);
  vec3 n = normalize(vec3(grad * (2.0 * (1.0 - s) / bevel) * cs * (black ? -0.05 : 0.11), 1.0));
  if (!black) n = normalize(n + vec3(local / (cs * 3.2), 0.0));
  vec3 dirCol = MODE.x > 0.5 ? PAL(DOWN) : PAL(ACROSS);
  vec3 seen = room(v_screen - n.xy * cs * 0.4);
  vec3 body; vec3 emissive = vec3(0.0); vec3 glow = vec3(0.0);
  float verdictAge = t - v_c.x;
  if (black) {
    body = PAL(OBSIDIAN) + seen * (paper() ? 0.06 : 0.16);
    float laneE = MODE.x > 0.5 ? 0.3 : 1.0; float laneS = MODE.x > 0.5 ? 1.0 : 0.3;
    if ((flags & 2048) != 0) emissive += PAL(ACROSS) * exp(-max(hb.x - local.x, 0.0) / (cs * 0.14)) * smoothstep(hb.y * 1.05, hb.y * 0.15, abs(local.y)) * 0.55 * laneE;
    if ((flags & 4096) != 0) emissive += PAL(DOWN) * exp(-max(hb.y - local.y, 0.0) / (cs * 0.14)) * smoothstep(hb.x * 1.05, hb.x * 0.15, abs(local.x)) * 0.55 * laneS;
  } else {
    body = mix(seen * (paper() ? 1.0 : 0.9), PAL(GLASS), paper() ? 0.5 : 0.45);
    float pool = distance(v_screen, lightPos()) / (cs * 6.5);
    body *= paper() ? 0.9 + 0.1 * exp(-pool * pool) : 0.78 + 0.45 * exp(-pool * pool);
    if ((flags & 2) != 0) body = mix(body, PAL(SHADE), 0.5);
    if ((flags & 64) != 0) { float flow = 0.5 + 0.5 * sin(6.2832 * (v_b.y * 1.2 - t * 0.42 * m)); body = mix(body, dirCol * (paper() ? 0.75 : 0.42), 0.26 + 0.2 * flow); }
    if (cursor) { body = mix(body, dirCol * (paper() ? 0.85 : 0.5), 0.3); float ring = abs(d + px * 1.5); emissive += dirCol * exp(-ring * ring / (px * px * 2.2)) * 1.4;
      glow += dirCol * exp(-max(d, 0.0) / (cs * 0.13)) * step(0.0, d) * 0.35 * lift; }
    if ((flags & 128) != 0) { body = mix(body, PAL(CORRECT) * (paper() ? 0.8 : 0.32), 0.4 * smoothstep(0.0, 0.3, verdictAge));
      if (verdictAge >= 0.0 && verdictAge < 1.2) { float ring = (length(local) - verdictAge * cs * 1.9) / (cs * 0.09); emissive += PAL(CORRECT) * exp(-ring * ring) * exp(-verdictAge * 3.2) * m * 1.1 * coverage; } }
    if ((flags & 256) != 0) { body = mix(body, PAL(WRONG) * (paper() ? 0.8 : 0.32), 0.5); emissive += PAL(WRONG) * 0.9 * exp(-max(verdictAge, 0.0) * 4.0); }
    if ((flags & 4) != 0) { float r = length(local) - min(hb.x, hb.y) * 0.8; emissive += PAL(RING) * exp(-r * r / (px * px * 2.0 + cs * cs * 0.0004)) * 0.5; }
  }
  emissive += (PAL(KEY) * 0.55 + PAL(CORRECT) * 0.55) * pop;
  vec3 ldir = normalize(vec3(lightPos(), cs * 5.5) - vec3(v_screen, cs * 0.1 * s));
  vec3 hv = normalize(ldir + vec3(0.0, 0.0, 1.0));
  float ndh = max(dot(n, hv), 0.0);
  float lightNear = exp(-pow(distance(v_screen, lightPos()) / (cs * 9.0), 2.0));
  float spec = (pow(ndh, black ? 320.0 : 90.0) * (black ? 3.2 : 1.4) + pow(ndh, 12.0) * 0.03) * (paper() ? 0.45 : 1.0) * (0.45 + 0.55 * lightNear) * 0.55; // ACES clips harder than AgX
  float fres = pow(1.0 - max(n.z, 0.0), 2.6);
  vec3 col = body * (0.62 + 0.38 * max(dot(n, ldir), 0.0)) + PAL(KEY) * spec * (0.7 + 0.5 * lift) + (PAL(KEY) * 0.22 + seen * 0.7) * fres * (paper() ? 0.5 : 1.0);
  col += PAL(KEY) * 0.1 * (1.0 - s) * max(-grad.y, 0.0);
  col *= 1.0 - 0.22 * (1.0 - s) * max(grad.y, 0.0);
  col += emissive;
  o = vec4(tonemap(col) * coverage + tonemap(glow) * (1.0 - coverage), coverage);
}
`;

function compile(gl: WebGL2RenderingContext, vertex: string, fragment: string): WebGLProgram {
  const shader = (type: number, source: string) => {
    const s = gl.createShader(type);
    if (!s) throw new Error('Could not create a shader');
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || 'Shader did not compile');
    return s;
  };
  const program = gl.createProgram();
  if (!program) throw new Error('Could not create a program');
  gl.attachShader(program, shader(gl.VERTEX_SHADER, vertex));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, fragment));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) || 'Program did not link');
  return program;
}

export function createWebGl2Glass(canvas: HTMLCanvasElement, onLost: LostHandler): WebGl2Glass {
  const gl = canvas.getContext('webgl2', { premultipliedAlpha: true, alpha: true, antialias: false, powerPreference: 'high-performance' });
  if (!gl) throw new Error('WebGL2 is not available');
  return new WebGl2Glass(canvas, gl, onLost);
}

export class WebGl2Glass implements GlassRenderer {
  readonly kind = 'webgl2' as const;
  private readonly backdrop: WebGLProgram;
  private readonly shadow: WebGLProgram;
  private readonly tile: WebGLProgram;
  private readonly vao: WebGLVertexArrayObject;
  private readonly cells: WebGLBuffer;
  private readonly globals = new Float32Array(GLOBAL_FLOATS);
  private count = 0;
  private capacity = 0;
  private cssWidth = 1;
  private cssHeight = 1;
  private pixelRatio = 1;
  private destroyed = false;
  private readonly lostListener: (event: Event) => void;
  private readonly locations: Map<WebGLProgram, { globals: WebGLUniformLocation | null; pad: WebGLUniformLocation | null }>;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly gl: WebGL2RenderingContext,
    onLost: LostHandler,
  ) {
    this.backdrop = compile(gl, FULL_VS, BACKDROP_FS);
    this.shadow = compile(gl, TILE_VS, SHADOW_FS);
    this.tile = compile(gl, TILE_VS, TILE_FS);
    this.locations = new Map(
      [this.backdrop, this.shadow, this.tile].map((program) => [program, { globals: gl.getUniformLocation(program, 'u_g'), pad: gl.getUniformLocation(program, 'u_pad') }]),
    );
    const vao = gl.createVertexArray();
    const cells = gl.createBuffer();
    if (!vao || !cells) throw new Error('Could not create buffers');
    this.vao = vao;
    this.cells = cells;
    gl.bindVertexArray(vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, cells);
    for (let location = 0; location < 3; location += 1) {
      gl.enableVertexAttribArray(location);
      gl.vertexAttribPointer(location, 4, gl.FLOAT, false, CELL_FLOATS * 4, location * 16);
      gl.vertexAttribDivisor(location, 1);
    }
    gl.bindVertexArray(null);
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

  setScene(scene: GlassScene): void {
    const gl = this.gl;
    if (scene.globals) this.globals.set(scene.globals.subarray(0, GLOBAL_FLOATS));
    if (scene.cells) {
      const count = scene.count ?? Math.floor(scene.cells.length / CELL_FLOATS);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.cells);
      if (count > this.capacity) {
        this.capacity = count;
        gl.bufferData(gl.ARRAY_BUFFER, scene.cells.subarray(0, count * CELL_FLOATS), gl.DYNAMIC_DRAW);
      } else {
        gl.bufferSubData(gl.ARRAY_BUFFER, 0, scene.cells, 0, count * CELL_FLOATS);
      }
      this.count = count;
    }
  }

  setCellState(index: number, floats: Float32Array): void {
    if (index < 0 || index >= this.count) return;
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.cells);
    gl.bufferSubData(gl.ARRAY_BUFFER, index * CELL_FLOATS * 4, floats, 0, CELL_FLOATS);
  }

  frame(time: number): void {
    const gl = this.gl;
    if (this.destroyed || gl.isContextLost()) return;
    this.globals[0] = this.cssWidth;
    this.globals[1] = this.cssHeight;
    this.globals[2] = this.pixelRatio;
    this.globals[3] = time;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.bindVertexArray(this.vao);
    const use = (program: WebGLProgram, pad: number | null) => {
      const location = this.locations.get(program);
      gl.useProgram(program);
      gl.uniform4fv(location?.globals ?? null, this.globals);
      if (pad !== null) gl.uniform1f(location?.pad ?? null, pad);
    };
    use(this.backdrop, null);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    if (this.count > 0) {
      use(this.shadow, 0.36);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.count);
      use(this.tile, 0.55);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.count);
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
    gl.deleteProgram(this.backdrop);
    gl.deleteProgram(this.shadow);
    gl.deleteProgram(this.tile);
    gl.deleteBuffer(this.cells);
    gl.deleteVertexArray(this.vao);
  }
}
