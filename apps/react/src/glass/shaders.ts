// The glass, in WGSL. One module, several entry points, drawn as:
//   room      fs_background            the aurora and caustics behind the glass (half res)
//   frost     fs_down ×2, fs_up        dual-Kawase blur of the room (quarter res)
//   scene     fs_backdrop              the board's slab: the room through the gaps, its shadow
//             vs_shadow/fs_shadow      every square's soft contact shadow
//             vs_tile/fs_tile          every square: bevelled glass or obsidian, lit
//   bloom     fs_down_bright, fs_down ×2, fs_up ×2
//   output    fs_composite             bloom, AgX tone mapping, vignette, grain
// All motion is computed here from the time stamps in the cell buffer
// (cellState.ts), so the CPU writes nothing per frame but the globals.

export const GLASS_WGSL = /* wgsl */ `
struct Globals {
  view: vec4f,
  board: vec4f,
  light: vec4f,
  lightTiming: vec4f,
  mode: vec4f,
  events: vec4f,
  palette: array<vec4f, 12>,
};

@group(0) @binding(0) var<uniform> g: Globals;
@group(0) @binding(1) var<storage, read> cells: array<vec4f>;
@group(0) @binding(2) var texA: texture_2d<f32>;
@group(0) @binding(3) var texB: texture_2d<f32>;
@group(0) @binding(4) var samp: sampler;

const SKY_LOW = 0u;
const SKY_HIGH = 1u;
const CAUSTIC = 2u;
const GLASS = 3u;
const OBSIDIAN = 4u;
const SHADE = 5u;
const RING = 6u;
const ACROSS = 7u;
const DOWN = 8u;
const CORRECT = 9u;
const WRONG = 10u;
const KEY = 11u;

const F_BLACK = 1u;
const F_SHADED = 2u;
const F_CIRCLED = 4u;
const F_LETTER = 16u;
const F_CURSOR = 32u;
const F_WORD = 64u;
const F_CORRECT = 128u;
const F_WRONG = 256u;
const F_SOLVED = 512u;
const F_SETTLED = 1024u;
const F_NOTCH_E = 2048u;
const F_NOTCH_S = 4096u;
const F_FLARE = 8192u;

fn pal(i: u32) -> vec3f { return g.palette[i].rgb; }
fn now() -> f32 { return g.view.w; }
fn cellSize() -> f32 { return max(g.lightTiming.z, 8.0); }
fn paper() -> bool { return g.mode.y > 0.5; }
fn motion() -> f32 { return 1.0 - g.mode.z; }
fn contrast() -> f32 { return g.mode.w; }

fn hash21(p: vec2f) -> f32 {
  var q = fract(p * vec2f(123.34, 456.21));
  q = q + dot(q, q + 45.32);
  return fract(q.x * q.y);
}

fn noise(p: vec2f) -> f32 {
  let i = floor(p);
  let f = fract(p);
  let u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash21(i), hash21(i + vec2f(1.0, 0.0)), u.x), mix(hash21(i + vec2f(0.0, 1.0)), hash21(i + vec2f(1.0, 1.0)), u.x), u.y);
}

fn fbm(p0: vec2f) -> f32 {
  var p = p0;
  var a = 0.5;
  var s = 0.0;
  for (var k = 0; k < 4; k = k + 1) {
    s = s + a * noise(p);
    p = p * 2.03 + vec2f(17.1, 9.2);
    a = a * 0.5;
  }
  return s;
}

fn ease(x: f32) -> f32 {
  let t = clamp(x, 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

fn lightPos() -> vec2f {
  let k = ease((now() - g.lightTiming.x) / max(g.lightTiming.y, 0.001));
  return mix(g.light.xy, g.light.zw, k);
}

// The room drifts slowly; under reduced motion it holds still.
fn roomTime() -> f32 { return now() * 0.035 * motion(); }

fn sdRoundBox(p: vec2f, b: vec2f, r: f32) -> f32 {
  let q = abs(p) - b + vec2f(r);
  return length(max(q, vec2f(0.0))) + min(max(q.x, q.y), 0.0) - r;
}

fn sdGrad(p: vec2f, b: vec2f, r: f32) -> vec2f {
  let q = abs(p) - b + vec2f(r);
  let s = vec2f(select(-1.0, 1.0, p.x >= 0.0), select(-1.0, 1.0, p.y >= 0.0));
  if (max(q.x, q.y) > 0.0) {
    return s * normalize(max(q, vec2f(0.0)) + vec2f(1e-5));
  }
  return select(vec2f(0.0, s.y), vec2f(s.x, 0.0), q.x > q.y);
}

// A spring settling on 1, and a kick that rings back to 0.
fn spring(age: f32, k: f32, w: f32) -> f32 {
  if (age < 0.0) { return 0.0; }
  return 1.0 - exp(-age * k) * cos(age * w);
}
fn kick(age: f32, k: f32, w: f32) -> f32 {
  if (age < 0.0 || age > 2.0) { return 0.0; }
  return exp(-age * k) * sin(age * w);
}

struct FullOut {
  @builtin(position) pos: vec4f,
  @location(0) uv: vec2f,
};

@vertex
fn vs_full(@builtin(vertex_index) i: u32) -> FullOut {
  let p = vec2f(f32((i << 1u) & 2u), f32(i & 2u));
  var o: FullOut;
  o.pos = vec4f(p * 2.0 - 1.0, 0.0, 1.0);
  o.uv = vec2f(p.x, 1.0 - p.y);
  return o;
}

// ---- The room -----------------------------------------------------------
@fragment
fn fs_background(in: FullOut) -> @location(0) vec4f {
  let px = in.uv * g.view.xy;
  let cs = cellSize();
  let p = px / (cs * 4.5);
  let t = roomTime();
  let q = vec2f(fbm(p + vec2f(0.0, t)), fbm(p + vec2f(5.2, -t * 0.8)));
  let a = fbm(p * 0.8 + 2.2 * q + vec2f(t * 0.6, -t * 0.3));
  let lift = select(2.4, 1.0, paper());
  var col = mix(pal(SKY_LOW) * 0.7, pal(SKY_HIGH) * lift, smoothstep(0.35, 0.95, a));
  // Aurora curtains: tall soft folds of the day's light.
  let fold = fbm(vec2f(p.x * 1.7 + q.y * 2.0, p.y * 0.22 - t * 0.5));
  col = col + pal(CAUSTIC) * smoothstep(0.5, 0.95, fold) * select(0.42, 0.16, paper());
  // A caustic net swimming through it.
  let w = p * 3.1 + q * 2.4;
  let c1 = 0.5 + 0.5 * sin(w.x * 2.7 + sin(w.y * 1.9 + t * 3.0) * 1.6);
  let c2 = 0.5 + 0.5 * sin(w.y * 2.3 + sin(w.x * 2.2 - t * 2.4) * 1.6);
  col = col + pal(CAUSTIC) * pow(c1 * c2, 7.0) * select(1.4, 0.3, paper()) * (0.25 + 0.75 * a);
  // The key light pools in the room.
  let d = distance(px, lightPos()) / (cs * 7.0);
  col = col + pal(KEY) * select(0.12, 0.05, paper()) * exp(-d * d);
  return vec4f(col, 1.0);
}

// ---- Dual-Kawase blur (and the bloom's bright pass) ----------------------
fn kawaseDown(uv: vec2f) -> vec3f {
  let o = 1.0 / vec2f(textureDimensions(texA));
  var s = textureSampleLevel(texA, samp, uv, 0.0).rgb * 4.0;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(-o.x, -o.y), 0.0).rgb;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(o.x, o.y), 0.0).rgb;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(o.x, -o.y), 0.0).rgb;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(-o.x, o.y), 0.0).rgb;
  return s / 8.0;
}

@fragment
fn fs_down(in: FullOut) -> @location(0) vec4f {
  return vec4f(kawaseDown(in.uv), 1.0);
}

@fragment
fn fs_down_bright(in: FullOut) -> @location(0) vec4f {
  let c = kawaseDown(in.uv);
  let luma = dot(c, vec3f(0.2126, 0.7152, 0.0722));
  let threshold = select(0.45, 1.1, paper());
  let knee = 0.35;
  let soft = clamp(luma - threshold + knee, 0.0, 2.0 * knee);
  let weight = max(soft * soft / (4.0 * knee + 1e-4), luma - threshold) / max(luma, 1e-4);
  // Clamp so a single hot pixel cannot flare.
  return vec4f(min(c * max(weight, 0.0), vec3f(6.0)), 1.0);
}

@fragment
fn fs_up(in: FullOut) -> @location(0) vec4f {
  let o = 1.0 / vec2f(textureDimensions(texA));
  let uv = in.uv;
  var s = textureSampleLevel(texA, samp, uv + vec2f(-o.x * 2.0, 0.0), 0.0).rgb;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(-o.x, o.y), 0.0).rgb * 2.0;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(0.0, o.y * 2.0), 0.0).rgb;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(o.x, o.y), 0.0).rgb * 2.0;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(o.x * 2.0, 0.0), 0.0).rgb;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(o.x, -o.y), 0.0).rgb * 2.0;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(0.0, -o.y * 2.0), 0.0).rgb;
  s = s + textureSampleLevel(texA, samp, uv + vec2f(-o.x, -o.y), 0.0).rgb * 2.0;
  return vec4f(s / 12.0, 1.0);
}

// ---- The slab ------------------------------------------------------------
@fragment
fn fs_backdrop(in: FullOut) -> @location(0) vec4f {
  let px = in.uv * g.view.xy;
  let b = g.board;
  let cs = cellSize();
  let center = b.xy + b.zw * 0.5;
  let d = sdRoundBox(px - center, b.zw * 0.5 + vec2f(cs * 0.16), cs * 0.36);
  let aa = 1.0 / g.view.z;
  let inside = 1.0 - smoothstep(-aa, aa, d);
  // The room shows through the gaps, dimmed, so the glass carries the light.
  let room = textureSampleLevel(texA, samp, in.uv, 0.0).rgb;
  var col = room * select(0.8, 1.05, paper());
  // A thin rim of light along the slab's edge.
  col = col + pal(KEY) * exp(-abs(d + 1.5) * 0.35) * 0.08;
  // Outside the slab: in the dark the room's light spills past the edge as a
  // soft halo; on paper the slab casts a shadow instead.
  let outside = 1.0 - inside;
  let halo = exp(-max(d, 0.0) / (cs * 0.45)) * outside * select(0.6, 0.0, paper());
  let shadow = (1.0 - smoothstep(-cs * 0.1, cs * 1.3, d)) * select(0.25, 0.22, paper()) * outside;
  let glowCol = room * 1.3 * halo;
  return vec4f(col * inside + glowCol, inside + max(shadow, halo * 0.85));
}

// ---- The squares ---------------------------------------------------------
struct Cell {
  rect: vec4f,
  flags: u32,
  wordPos: f32,
  selectAt: f32,
  pressAt: f32,
  verdictAt: f32,
  popAt: f32,
  popPos: f32,
  stateAt: f32,
};

fn cellAt(i: u32) -> Cell {
  let a = cells[i * 3u];
  let b = cells[i * 3u + 1u];
  let c = cells[i * 3u + 2u];
  var cell: Cell;
  cell.rect = a;
  cell.flags = u32(b.x + 0.5);
  cell.wordPos = b.y;
  cell.selectAt = b.z;
  cell.pressAt = b.w;
  cell.verdictAt = c.x;
  cell.popAt = c.y;
  cell.popPos = c.z;
  cell.stateAt = c.w;
  return cell;
}

fn has(cell: Cell, f: u32) -> bool { return (cell.flags & f) != 0u; }

// How a square moves right now: lift toward the viewer (the cursor), the press
// of a typed key, a wrong letter's shudder, the sweep of a word popping, and
// the ceremony's wave.
struct Pose {
  lift: f32,
  scale: f32,
  offset: vec2f,
  pop: f32,
  wave: f32,
};

fn poseOf(cell: Cell) -> Pose {
  let t = now();
  let m = motion();
  let cs = cellSize();
  var pose: Pose;
  pose.lift = 0.0;
  if (has(cell, F_CURSOR)) {
    pose.lift = mix(1.0, spring(t - cell.selectAt, 9.0, 13.0), m);
  }
  let press = kick(t - cell.pressAt, 15.0, 28.0) * m;
  var shudder = 0.0;
  let wrongAge = t - cell.verdictAt;
  if (has(cell, F_WRONG) && wrongAge >= 0.0 && wrongAge < 1.5) {
    shudder = sin(wrongAge * 70.0) * exp(-wrongAge * 7.0) * cs * 0.05 * m;
  }
  let popAge = t - cell.popAt - cell.popPos * 0.32;
  pose.pop = 0.0;
  if (popAge > -0.3 && popAge < 1.4) {
    pose.pop = exp(-popAge * popAge * 26.0);
  }
  pose.wave = 0.0;
  let ceremony = t - g.events.x;
  if (ceremony > 0.0 && ceremony < 4.0) {
    let center = g.board.xy + g.board.zw * 0.5;
    let reach = length(g.board.zw) * 0.5;
    let dist = length(cell.rect.xy + cell.rect.zw * 0.5 - center) / max(reach, 1.0);
    let phase = ceremony * 0.8 - dist;
    pose.wave = exp(-phase * phase * 30.0) * (1.0 - ceremony / 4.0);
  }
  pose.scale = 1.0 + 0.05 * pose.lift - 0.05 * press + (0.035 * pose.pop + 0.05 * pose.wave) * m;
  pose.offset = vec2f(shudder, -cs * 0.03 * pose.lift);
  return pose;
}

struct TileOut {
  @builtin(position) pos: vec4f,
  @location(0) local: vec2f,
  @location(1) @interpolate(flat) index: u32,
  @location(2) screen: vec2f,
};

fn tileVertex(v: u32, i: u32, pad: f32) -> TileOut {
  let rect = cells[i * 3u];
  let corner = vec2f(f32(v & 1u), f32((v >> 1u) & 1u)) * 2.0 - 1.0;
  let half = rect.zw * 0.5 + vec2f(pad);
  let center = rect.xy + rect.zw * 0.5;
  let screen = center + corner * half;
  var o: TileOut;
  o.pos = vec4f(screen / g.view.xy * vec2f(2.0, -2.0) + vec2f(-1.0, 1.0), 0.0, 1.0);
  o.local = corner * half;
  o.index = i;
  o.screen = screen;
  return o;
}

// Only a square that is glowing or rippling needs room around it; the rest
// draw tight, which keeps the overdraw low.
@vertex
fn vs_tile(@builtin(vertex_index) v: u32, @builtin(instance_index) i: u32) -> TileOut {
  let cell = cellAt(i);
  let t = now();
  let cs = cellSize();
  var pad = cs * 0.04;
  let busy = has(cell, F_CURSOR) || (t - cell.verdictAt < 1.2) || (t - cell.popAt < 1.8) || has(cell, F_CIRCLED) || has(cell, F_NOTCH_E) || has(cell, F_NOTCH_S) || (t - g.events.x < 4.0);
  if (busy) { pad = cs * 0.55; }
  return tileVertex(v, i, pad);
}

@vertex
fn vs_shadow(@builtin(vertex_index) v: u32, @builtin(instance_index) i: u32) -> TileOut {
  return tileVertex(v, i, cellSize() * 0.36);
}

@fragment
fn fs_shadow(in: TileOut) -> @location(0) vec4f {
  let cell = cellAt(in.index);
  let cs = cellSize();
  let pose = poseOf(cell);
  let half = cell.rect.zw * 0.5 - vec2f(max(1.0, cs * 0.065));
  let radius = cs * 0.17;
  let away = normalize(in.screen - lightPos() + vec2f(0.0, 1e-3));
  let offset = away * cs * (0.035 + 0.11 * pose.lift + 0.05 * pose.pop) + pose.offset;
  let blur = cs * (0.06 + 0.13 * pose.lift);
  let d = sdRoundBox((in.local - offset) / pose.scale, half, radius);
  let black = has(cell, F_BLACK);
  var strength = select(0.55, 0.3, paper());
  if (black) { strength = strength * 0.35; }
  let a = (1.0 - smoothstep(-blur, blur, d)) * strength;
  return vec4f(0.0, 0.0, 0.0, a);
}

@fragment
fn fs_tile(in: TileOut) -> @location(0) vec4f {
  let cell = cellAt(in.index);
  let t = now();
  let cs = cellSize();
  let px = 1.0 / g.view.z;
  let m = motion();
  let pose = poseOf(cell);
  let local = (in.local - pose.offset) / pose.scale;
  let black = has(cell, F_BLACK);
  let half = cell.rect.zw * 0.5 - vec2f(max(1.0, cs * 0.065));
  let radius = cs * 0.17;
  let d = sdRoundBox(local, half, radius);
  let coverage = 1.0 - smoothstep(-px, px, d);
  let dirCol = select(pal(ACROSS), pal(DOWN), g.mode.x > 0.5);
  let verdictAge = t - cell.verdictAt;
  let rippling = has(cell, F_CORRECT) && verdictAge >= 0.0 && verdictAge < 1.2;
  if (d > cs * 0.55 && !rippling) {
    return vec4f(0.0);
  }

  // The surface: a pillow of glass (or a recessed obsidian block).
  let bevel = cs * select(0.17, 0.1, black);
  let s = clamp(-d / bevel, 0.0, 1.0);
  let slope = 2.0 * (1.0 - s) / bevel;
  let grad = sdGrad(local, half, radius);
  let height = cs * select(0.11, -0.05, black);
  var n = normalize(vec3f(grad * slope * height, 1.0));
  if (!black) {
    n = normalize(n + vec3f(local / (cs * 3.2), 0.0));
  }

  // What the glass shows: the frosted room behind it, bent at the edges and
  // split a little into its colours.
  let uv = in.screen / g.view.xy;
  let k = 1.0 / g.view.xy;
  let bend = (n.xy * cs * 0.4 + local * 0.08) * (1.0 - 0.6 * contrast());
  let frost = vec3f(
    textureSampleLevel(texB, samp, uv - bend * k, 0.0).r,
    textureSampleLevel(texB, samp, uv - bend * k * 1.09, 0.0).g,
    textureSampleLevel(texB, samp, uv - bend * k * 1.18, 0.0).b,
  );
  let room = textureSampleLevel(texA, samp, uv + n.xy * 0.04 + vec2f(0.0, 0.03), 0.0).rgb;
  // The rim bends the sharp room hard and splits it: the coloured edge light
  // real glass catches.
  let rimBend = n.xy * cs * 1.1 * (1.0 - 0.7 * contrast());
  let edgeLight = vec3f(
    textureSampleLevel(texA, samp, uv - rimBend * k, 0.0).r,
    textureSampleLevel(texA, samp, uv - rimBend * k * 1.15, 0.0).g,
    textureSampleLevel(texA, samp, uv - rimBend * k * 1.3, 0.0).b,
  );

  var body: vec3f;
  var emissive = vec3f(0.0);
  var glow = vec3f(0.0);
  var shine = 1.0;
  if (black) {
    // Polished obsidian: near black, with the room faintly mirrored in it.
    body = pal(OBSIDIAN) * 0.5 + room * select(0.03, 0.04, paper());
    shine = 1.9;
    let lane = select(1.0, 0.3, g.mode.x > 0.5) * select(1.0, 0.45, paper());
    let flare = select(1.0, 2.6, has(cell, F_FLARE));
    if (has(cell, F_NOTCH_E)) {
      let edge = exp(-max(half.x - local.x, 0.0) / (cs * 0.05)) * smoothstep(half.y * 0.9, half.y * 0.1, abs(local.y));
      let spill = exp(-max(half.x - local.x, 0.0) / (cs * 0.3)) * smoothstep(half.y * 1.1, 0.0, abs(local.y));
      emissive = emissive + pal(ACROSS) * (edge * 0.9 + spill * 0.12) * lane * flare;
      glow = glow + pal(ACROSS) * exp(-max(local.x - half.x, 0.0) / (cs * 0.08)) * step(half.x, local.x) * smoothstep(half.y, 0.0, abs(local.y)) * 0.25 * lane * flare;
    }
    if (has(cell, F_NOTCH_S)) {
      let lane2 = select(0.3, 1.0, g.mode.x > 0.5) * select(1.0, 0.45, paper());
      let edge = exp(-max(half.y - local.y, 0.0) / (cs * 0.05)) * smoothstep(half.x * 0.9, half.x * 0.1, abs(local.x));
      let spill = exp(-max(half.y - local.y, 0.0) / (cs * 0.3)) * smoothstep(half.x * 1.1, 0.0, abs(local.x));
      emissive = emissive + pal(DOWN) * (edge * 0.9 + spill * 0.12) * lane2 * flare;
      glow = glow + pal(DOWN) * exp(-max(local.y - half.y, 0.0) / (cs * 0.08)) * step(half.y, local.y) * smoothstep(half.x, 0.0, abs(local.x)) * 0.25 * lane2 * flare;
    }
  } else {
    // Smoky glass: most of what it shows is the room behind it, frosted;
    // the rest is its own tint. More contrast asks for more tint.
    let tint = select(0.42, 0.5, paper()) + 0.3 * contrast();
    // Half frosted: the room's veins still show through, softened and
    // bent by the glass, so the surface reads as liquid rather than milk.
    let seen = mix(edgeLight * 0.9, frost, select(0.55, 0.8, paper()));
    body = mix(seen * select(0.9, 1.0, paper()), pal(GLASS), tint);
    // Thickness: the glass darkens toward its lower edge, away from the light.
    body = body * (0.82 + 0.18 * (0.5 - local.y / (cs * 1.2)));
    // Thicker at the rim: the room's light gathers there, bent and split.
    let rim = (1.0 - s) * (1.0 - s);
    body = body + edgeLight * rim * select(1.5, 0.35, paper()) * (1.0 - contrast());
    // The key light pools on the glass around where it points, and falls
    // away across the board.
    let pool = distance(in.screen, lightPos()) / (cs * 6.5);
    let falloff = exp(-pool * pool);
    body = body * select(0.78 + 0.45 * falloff, 0.9 + 0.1 * falloff, paper()) + pal(KEY) * select(0.03, 0.0, paper()) * falloff;
    if (has(cell, F_SHADED)) {
      body = mix(body, pal(SHADE), 0.5) + frost * 0.12;
    }
    if (has(cell, F_SETTLED)) {
      body = body * 0.9;
      shine = 0.7;
    }
    if (has(cell, F_WORD)) {
      // The active word: a band of the direction's light flowing along it.
      body = mix(body, dirCol * select(0.16, 0.95, paper()) + frost * select(0.4, 0.05, paper()), select(0.4, 0.68, paper()));
      // A streak of light runs along the word, again and again.
      let phase = fract(t * 0.32 * m) * 1.8 - 0.4;
      let streak = exp(-pow((cell.wordPos - phase) * 4.0 + local.x / cs * 0.6, 2.0)) * s;
      emissive = emissive + dirCol * (0.03 + 0.3 * streak * m);
      // Its rim glows in the direction's colour.
      emissive = emissive + dirCol * rim * select(0.9, 0.5, paper());
    }
    if (has(cell, F_CURSOR)) {
      body = mix(body, dirCol * select(0.5, 1.0, paper()), select(0.3, 0.55, paper()));
      let ring = abs(d + px * 1.5);
      emissive = emissive + dirCol * exp(-ring * ring / (px * px * 2.2)) * (1.3 + 0.6 * pose.lift);
      glow = glow + dirCol * exp(-max(d, 0.0) / (cs * 0.13)) * step(0.0, d) * 0.35 * pose.lift;
    }
    if (has(cell, F_CORRECT)) {
      let a = smoothstep(0.0, 0.3, verdictAge);
      body = mix(body, pal(CORRECT) * select(0.32, 0.8, paper()), 0.4 * a);
      if (rippling) {
        let r = verdictAge * cs * 1.9;
        let ring = (length(local) - r) / (cs * 0.09);
        let ink = exp(-ring * ring) * exp(-verdictAge * 3.2) * m;
        emissive = emissive + pal(CORRECT) * ink * 1.1 * coverage;
        glow = glow + pal(CORRECT) * ink * 0.6 * (1.0 - coverage);
      }
    }
    if (has(cell, F_WRONG)) {
      body = mix(body, pal(WRONG) * select(0.32, 0.8, paper()), 0.5);
      emissive = emissive + pal(WRONG) * 0.9 * exp(-max(verdictAge, 0.0) * 4.0);
    }
    if (has(cell, F_CIRCLED)) {
      let r = length(local) - min(half.x, half.y) * 0.8;
      let line = exp(-r * r / (px * px * 2.0 + cs * cs * 0.0004));
      emissive = emissive + pal(RING) * line * 0.5;
      glow = glow + pal(RING) * exp(-abs(r) / (cs * 0.07)) * 0.08;
    }
  }
  // A word that popped: a light pulse sweeping along it.
  emissive = emissive + (pal(KEY) * 0.55 + pal(CORRECT) * 0.55) * pose.pop;
  // The ceremony's wave and its glints.
  emissive = emissive + (pal(KEY) * 0.6 + pal(CAUSTIC) * 0.5) * pose.wave;
  let glint = step(0.985, hash21(vec2f(f32(in.index), floor(t * 7.0)))) * select(0.0, 1.0, t - g.events.x < 3.5 && t > g.events.x);

  // Light: a soft key light above the board, Blinn-Phong with a broad sheen,
  // a Fresnel rim, a catch light on the top edge and a little occlusion at the
  // bottom one.
  let L = vec3f(lightPos(), cs * 5.5);
  let P = vec3f(in.screen, cs * 0.1 * s);
  let ldir = normalize(L - P);
  let hv = normalize(ldir + vec3f(0.0, 0.0, 1.0));
  let ndh = max(dot(n, hv), 0.0);
  let ndl = max(dot(n, ldir), 0.0);
  let lightNear = exp(-pow(distance(in.screen, lightPos()) / (cs * 9.0), 2.0));
  let spec = (pow(ndh, select(90.0, 320.0, black)) * select(1.4, 3.2, black) + pow(ndh, 12.0) * select(0.035, 0.02, black)) * shine * select(1.0, 0.45, paper()) * (0.45 + 0.55 * lightNear);
  let fres = pow(1.0 - max(n.z, 0.0), 2.6);
  var col = body * (0.62 + 0.38 * ndl);
  col = col + pal(KEY) * spec * (0.7 + 0.5 * pose.lift + glint * 3.0);
  col = col + (pal(KEY) * 0.22 + frost * 0.7) * fres * select(1.0, 0.5, paper());
  col = col + pal(KEY) * 0.1 * (1.0 - s) * max(-grad.y, 0.0);
  // A softbox above the board, reflected in every square: two long bands of
  // light running across the whole board, bent by each square's surface, so
  // the glass reads as one sheet of material catching one light. They drift.
  let center = g.board.xy + g.board.zw * 0.5;
  let span = max(max(g.board.z, g.board.w), 1.0);
  let landing = in.screen + n.xy * cs * 2.4;
  let axis = vec2f(0.8, -0.6);
  let f = dot(landing - center, axis) / span;
  let drift = sin(roomTime() * 2.2) * 0.1;
  let band = exp(-pow((f + 0.2 - drift) / 0.07, 2.0)) + 0.45 * exp(-pow((f - 0.24 - drift) / 0.025, 2.0));
  col = col + pal(KEY) * band * (0.07 + 0.55 * fres + 0.06 * s) * select(1.0, 0.3, paper()) * select(1.0, 1.6, black);
  col = col * (1.0 - 0.22 * (1.0 - s) * max(grad.y, 0.0));
  col = col + emissive;

  let alpha = coverage;
  return vec4f(col * alpha + glow * (1.0 - coverage), alpha);
}

// ---- Output --------------------------------------------------------------
fn agxContrast(x: vec3f) -> vec3f {
  let x2 = x * x;
  let x4 = x2 * x2;
  return 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + 0.4298 * x2 + 0.1191 * x - 0.00232;
}

fn agx(v0: vec3f) -> vec3f {
  let m = mat3x3f(0.842479062253094, 0.0423282422610123, 0.0423756549057051, 0.0784335999999992, 0.878468636469772, 0.0784336, 0.0792237451477643, 0.0791661274605434, 0.879142973793104);
  let minEv = -12.47393;
  let maxEv = 4.026069;
  var v = m * v0;
  v = clamp(log2(max(v, vec3f(1e-10))), vec3f(minEv), vec3f(maxEv));
  v = (v - minEv) / (maxEv - minEv);
  return agxContrast(v);
}

// A gentle punch: a touch more saturation than AgX's neutral base.
fn agxLook(v: vec3f) -> vec3f {
  let luma = dot(v, vec3f(0.2126, 0.7152, 0.0722));
  return luma + 1.12 * (v - luma);
}

fn agxEotf(v0: vec3f) -> vec3f {
  let m = mat3x3f(1.19687900512017, -0.0528968517574562, -0.0529716355144438, -0.0980208811401368, 1.15190312990417, -0.0980434501171241, -0.0990297440797205, -0.0989611768448433, 1.15107367264116);
  let v = m * v0;
  return pow(max(v, vec3f(0.0)), vec3f(2.2));
}

fn srgbEncode(c: vec3f) -> vec3f {
  let lo = c * 12.92;
  let hi = 1.055 * pow(max(c, vec3f(0.0)), vec3f(1.0 / 2.4)) - 0.055;
  return select(hi, lo, c <= vec3f(0.0031308));
}

@fragment
fn fs_composite(in: FullOut) -> @location(0) vec4f {
  let hdr = textureSampleLevel(texA, samp, in.uv, 0.0);
  let bloom = textureSampleLevel(texB, samp, in.uv, 0.0).rgb;
  var col = hdr.rgb + bloom * select(0.85, 0.18, paper()) * (1.0 - 0.6 * contrast());
  col = col * g.events.z;
  // Night: AgX, for highlights that roll off like film. Paper: a plain
  // exponential shoulder, which keeps white white.
  if (paper()) {
    col = 1.0 - exp(-col);
  } else {
    col = agxEotf(agxLook(agx(col)));
  }
  let px = in.uv * g.view.xy;
  let center = g.board.xy + g.board.zw * 0.5;
  let v = length((px - center) / (g.board.zw * 0.72));
  col = col * (1.0 - select(0.3, 0.07, paper()) * smoothstep(0.5, 1.3, v));
  let alpha = clamp(hdr.a + dot(bloom, vec3f(0.3, 0.6, 0.1)) * 0.45, 0.0, 1.0);
  let grain = (hash21(in.pos.xy + fract(now() * 13.1) * vec2f(97.0, 41.0) * motion()) - 0.5) * select(0.02, 0.012, paper()) * (1.0 - contrast());
  let encoded = srgbEncode(clamp(col, vec3f(0.0), vec3f(1.0))) + vec3f(grain * alpha);
  return vec4f(max(encoded, vec3f(0.0)), alpha);
}
`;
