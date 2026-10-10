// The glass layer's shader: the board as a sheet of living gel.
//
// One analytic pass draws the whole board, no render-target chain and no
// bloom: every light is computed where it falls, so it stays crisp.
//
// The colour is the board's own (vision.css, via tint.ts): each word's hue on
// its lane's arc, entering at the word's notch and fading along it (0.42 a
// square, like the CSS spill), the room tint warm while Across is solved and
// cool while Down is, the active word burning in its flame, the charge
// gathering as words are solved. What the gel adds is the physics of it:
//
//   - The floor. A dark well under everything, lit by pools of the light the
//     gel holds and by the notch filaments, which are true line emitters in
//     the seams. On paper the floor is the page.
//   - The gel. Each square is a soft cube with a meniscus edge. Through it you
//     see the floor refracted, absorbed by its thickness (Beer-Lambert), and the
//     word's light scattered inside it, strongest at the edge it enters from.
//     On paper the hue is a dye the clear gel absorbs through instead.
//   - The surface: a thin Fresnel rim in the colours around it, a wet
//     highlight riding the meniscus, never a plastic blob in the middle.
//   - The sheet. Every keystroke sends a ripple through the whole board, and
//     each square answers in its own way: an empty one wobbles, a filled one is
//     firmer, a solved one has set. A wrong answer fractures and clouds; a
//     right one crystallises; a solved word pulses along; the finished board
//     sends one wave through everything.

const GEL = /* wgsl */ `
struct Globals {
  view: vec4f,
  board: vec4f,
  grid: vec4f,
  dims: vec4f,
  mode: vec4f,
  lane: vec4f,
  spill: vec4f,
  key: vec4f,
  orange: vec4f,
  blue: vec4f,
  flame: vec4f,
  black: vec4f,
  cell: vec4f,
  shaded: vec4f,
  red: vec4f,
  clipAcross: vec4f,
  clipDown: vec4f,
  impulse: array<vec4f, 6>,
};

struct Cell {
  rect: vec4f,
  a: vec4f,   // flags, wordPos, selectAt, pressAt
  b: vec4f,   // verdictAt, popAt, popPos, stateAt
  sa: vec4f,  // Across tint, distance along it (-1 none) | east tick
  sd: vec4f,  // Down tint, distance along it (-1 none) | south tick
};

@group(0) @binding(0) var<uniform> g: Globals;
@group(0) @binding(1) var<storage, read> cells: array<Cell>;
@group(0) @binding(3) var lightField: texture_2d<f32>;
@group(0) @binding(4) var linearSampler: sampler;

struct Box {
  rect: vec4f,
  tint: vec4f, // clue tint, place in the answer
  info: vec4f, // board cell (-1 none), lane, flags, answer length
};
@group(0) @binding(5) var<storage, read> boxes: array<Box>;

const BOX_CURSOR = 1u;
const BOX_LIT = 2u;
const BOX_RANKED = 64u;

// Every open square and box keeps at least this share of its words' light,
// so the water never stops dead between one notch's reach and the next.
const FLOOR = 0.24;

// The light field holds this many texels per square, over the grid and one
// square of margin all round.
const FIELD = 8.0;

const BLACK = 1u;
const SHADED = 2u;
const CIRCLED = 4u;
const LETTER = 16u;
const CURSOR = 32u;
const WORD = 64u;
const CORRECT = 128u;
const WRONG = 256u;
const SETTLED = 1024u;
const NOTCH_E = 2048u;
const NOTCH_S = 4096u;
const POP = 32768u;
const SOLVED_A = 65536u;
const SOLVED_D = 131072u;

const TAU = 6.2831853;

fn now() -> f32 { return g.view.w; }
fn paper() -> bool { return g.mode.y > 0.5; }
fn motion() -> f32 { return 1.0 - g.mode.z; }
fn contrast() -> f32 { return g.mode.w; }
fn pitch() -> f32 { return g.grid.z; }
fn cols() -> i32 { return i32(g.grid.w); }
fn rows() -> i32 { return i32(g.dims.x); }
fn has(f: u32, bit: u32) -> bool { return (f & bit) != 0u; }
fn since(t: f32) -> f32 { return max(now() - t, 0.0); }
fn flagsOf(i: i32) -> u32 { return u32(cells[i].a.x); }
fn luma(c: vec3f) -> f32 { return dot(c, vec3f(0.2126, 0.7152, 0.0722)); }

fn cellAt(c: vec2i) -> i32 {
  if (c.x < 0 || c.y < 0 || c.x >= cols() || c.y >= rows()) { return -1; }
  let i = c.y * cols() + c.x;
  if (i >= i32(g.dims.y)) { return -1; }
  return i;
}

fn hash(p: vec2f) -> f32 {
  return fract(sin(dot(p, vec2f(127.1, 311.7))) * 43758.5453);
}
fn hash2(p: vec2f) -> vec2f {
  return fract(sin(vec2f(dot(p, vec2f(127.1, 311.7)), dot(p, vec2f(269.5, 183.3)))) * 43758.5453);
}

// The room's light: warm while Across is solved, cool while Down is.
fn roomTint() -> vec3f { return mix(g.blue.rgb, g.orange.rgb, g.lane.z); }
fn haloTint() -> vec3f { return select(g.orange.rgb, g.blue.rgb, g.mode.x > 0.5); }

// A word's light at a point of one of its squares: entering at full strength
// on the word's first square and stepping down 0.42 a square, interpolated
// across the square the way the CSS spill gradient is.
fn spillLevel(dist: f32, along: f32) -> f32 {
  let a0 = clamp(1.0 - dist * 0.42, 0.0, 1.0);
  let a1 = clamp(1.0 - (dist + 1.0) * 0.42, 0.0, 1.0);
  return mix(a0, a1, clamp(along, 0.0, 1.0));
}

// The same, with the floor the overlay keeps (the CSS spill itself stops).
fn waterLevel(dist: f32, along: f32) -> f32 {
  return max(spillLevel(dist, along), FLOOR * exp(-max(dist + along - 2.4, 0.0) * 0.12));
}

// The light a gel square holds at local point f (0..1): its words' spills,
// the room tint, and the flame while its word is lit.
fn heldLight(i: i32, f: vec2f) -> vec3f {
  let c = cells[i];
  let flags = u32(c.a.x);
  var light = vec3f(0.0);
  if (c.sa.w >= 0.0 && !has(flags, SOLVED_A)) {
    light += c.sa.rgb * spillLevel(c.sa.w, f.x) * g.spill.x * g.lane.x;
  }
  if (c.sd.w >= 0.0 && !has(flags, SOLVED_D)) {
    light += c.sd.rgb * spillLevel(c.sd.w, f.y) * g.spill.x * g.lane.y;
  }
  if (!has(flags, SETTLED)) { light += roomTint() * g.spill.y; }
  if (has(flags, WORD) && g.flame.w > 0.5) {
    let fade = 1.0 - max(c.a.y, 0.0) * 0.7;
    light += g.flame.rgb * g.spill.z * fade;
  }
  if (has(flags, CURSOR) && g.flame.w > 0.5) { light += g.flame.rgb * g.spill.w * 0.7; }
  return light;
}

// What a square gives off into the floor around it (its mean light).
fn emission(c: vec2i) -> vec3f {
  let i = cellAt(c);
  if (i < 0) { return vec3f(0.0); }
  if (has(flagsOf(i), BLACK)) { return vec3f(0.0); }
  // The words' light only: the room tint is everywhere already.
  let flags = flagsOf(i);
  var light = heldLight(i, vec2f(0.5));
  if (!has(flags, SETTLED)) { light -= roomTint() * g.spill.y; }
  return max(light, vec3f(0.0));
}

// A notch filament: a short line on a seam, bright-cored, its light falling
// off around it. u is in square units; the segment runs along one axis.
fn filament(u: vec2f, at: vec2f, vertical: bool, tint: vec3f, level: f32, part: i32) -> vec3f {
  let reach = 0.19;
  var d: vec2f;
  if (vertical) { d = vec2f(u.x - at.x, max(abs(u.y - at.y) - reach, 0.0)); }
  else { d = vec2f(max(abs(u.x - at.x) - reach, 0.0), u.y - at.y); }
  let r = length(d) * pitch();
  let charge = g.lane.w;
  let core = exp(-r * r / 1.1);
  let glow = exp(-r / (3.0 + 3.0 * min(charge, 2.0))) * 0.55 + exp(-r / 14.0) * 0.12;
  let white = min(0.78, 0.44 * charge);
  // part 0: the soft light only (the light field); 1: the core only.
  if (part == 0) { return tint * glow * level; }
  return mix(tint, vec3f(1.0), white) * core * 1.6 * level;
}

fn tickTint(rank: vec4f, lane: vec3f) -> vec3f {
  return select(lane, rank.rgb, rank.w >= 0.0 && dot(rank.rgb, vec3f(1.0)) > 0.0);
}

// Every filament near u: east ticks of black squares (an Across word opens
// to the right), south ticks (a Down word opens below), and the edge ticks of
// words that open on the grid's own border.
fn notches(u: vec2f, part: i32, reach: i32) -> vec3f {
  let base = vec2i(floor(u));
  let lit = min(1.0, g.lane.w);
  var light = vec3f(0.0);
  // reach 1: the 3x3 around u; reach 0: u's square and its west and north
  // neighbours, the only ones whose ticks sit on its edges.
  let hi = select(0, 1, reach == 1);
  for (var y = -1; y <= hi; y++) {
    for (var x = -1; x <= hi; x++) {
      if (reach == 0 && x == -1 && y == -1) { continue; }
      let c = base + vec2i(x, y);
      let i = cellAt(c);
      if (i < 0) { continue; }
      let cell = cells[i];
      let flags = u32(cell.a.x);
      let o = vec2f(c);
      if (has(flags, BLACK)) {
        if (has(flags, NOTCH_E)) {
          light += filament(u, o + vec2f(1.0, 0.5), true, tickTint(cell.sa, g.orange.rgb), lit * g.lane.x, part);
        }
        if (has(flags, NOTCH_S)) {
          light += filament(u, o + vec2f(0.5, 1.0), false, tickTint(cell.sd, g.blue.rgb), lit * g.lane.y, part);
        }
      } else {
        if (c.x == 0 && cell.sa.w == 0.0 && !has(flags, SOLVED_A)) {
          light += filament(u, o + vec2f(0.0, 0.5), true, cell.sa.rgb, lit * g.lane.x, part);
        }
        if (c.y == 0 && cell.sd.w == 0.0 && !has(flags, SOLVED_D)) {
          light += filament(u, o + vec2f(0.5, 0.0), false, cell.sd.rgb, lit * g.lane.y, part);
        }
      }
    }
  }
  return light;
}

// The light pooling on the floor around u (square units): each square's held
// light, spread smoothly between square centres.
fn pool(u: vec2f) -> vec3f {
  let gp = u - 0.5;
  let i0 = vec2i(floor(gp));
  let t = fract(gp);
  let w = t * t * (3.0 - 2.0 * t);
  return mix(
    mix(emission(i0), emission(i0 + vec2i(1, 0)), w.x),
    mix(emission(i0 + vec2i(0, 1)), emission(i0 + vec2i(1, 1)), w.x),
    w.y);
}

// The light field pass: pools and the filaments' soft light, at FIELD texels a
// square. Everything soft on the floor is read back from here with one
// filtered sample, so the gel pass never walks its neighbours for it.
@fragment fn fs_field(@builtin(position) pos: vec4f) -> @location(0) vec4f {
  let u = pos.xy / FIELD - 1.0;
  return vec4f(pool(u) + notches(u, 0, 1), 1.0);
}

fn fieldAt(q: vec2f) -> vec3f {
  let u = (q - g.grid.xy) / pitch();
  let span = vec2f(f32(cols()) + 2.0, f32(rows()) + 2.0);
  return textureSampleLevel(lightField, linearSampler, (u + 1.0) / span, 0.0).rgb;
}

// ---- The sheet: ripples every square shares -------------------------------

// Height (square units) and its gradient of the travelling ripples at p.
fn ripples(p: vec2f) -> vec3f {
  var h = 0.0;
  var grad = vec2f(0.0);
  for (var k = 0; k < 6; k++) {
    let im = g.impulse[k];
    let age = now() - im.z;
    if (age < 0.0 || age > 2.6 || im.w <= 0.0) { continue; }
    let dv = (p - im.xy) / pitch();
    let r = length(dv) + 0.0001;
    let front = age * 5.0;
    let env = im.w * exp(-age * 1.9) * exp(-r * 0.3) * smoothstep(front + 0.9, front - 1.2, r);
    let phase = (r - front) * 2.3;
    h += sin(phase) * env;
    grad += cos(phase) * 2.3 * env * dv / r;
  }
  // The finished board: one slow wave out from the middle.
  let ceremony = now() - g.dims.z;
  if (ceremony > 0.0 && ceremony < 5.0) {
    let centre = g.board.xy + g.board.zw * 0.5;
    let dv = (p - centre) / pitch();
    let r = length(dv) + 0.0001;
    let front = ceremony * 4.5;
    let env = 1.6 * exp(-ceremony * 0.7) * smoothstep(front + 1.5, front - 3.0, r);
    let phase = (r - front) * 1.6;
    h += sin(phase) * env;
    grad += cos(phase) * 1.6 * env * dv / r;
  }
  return vec3f(h, grad) * motion();
}

// How a square answers the sheet: an empty one is soft, a filled one firmer,
// a solved one has set.
fn softness(flags: u32) -> f32 {
  if (has(flags, SETTLED)) { return 0.15; }
  if (has(flags, SOLVED_A) || has(flags, SOLVED_D)) { return 0.4; }
  if (has(flags, LETTER)) { return 0.7; }
  return 1.0;
}

// ---- What the light does on a square --------------------------------------

// A crack: distance to the nearest edge between a few jittered cells, so a
// wrong square shows a fracture through it.
fn fracture(f: vec2f, seed: f32) -> f32 {
  let p = f * 2.4 + seed * 7.13;
  let base = floor(p);
  var best = 9.0;
  var second = 9.0;
  for (var y = -1; y <= 1; y++) {
    for (var x = -1; x <= 1; x++) {
      let o = base + vec2f(f32(x), f32(y));
      let site = o + hash2(o + seed);
      let d = length(p - site);
      if (d < best) { second = best; best = d; } else if (d < second) { second = d; }
    }
  }
  return (second - best) / 2.4;
}

// Caustics: the bright net light makes through moving water (the classic
// iterated-warp construction: each pass bends the plane by the last, and the
// light gathers where the bends converge). u is in square units, so the net
// keeps its scale on any board; still when ambient motion is off.
fn caustic(u: vec2f, bend: vec2f) -> f32 {
  let t = now() * 0.32 * g.dims.w * motion() + 23.0;
  let p = (u + bend) * 1.45 - 250.0;
  var q = p;
  var c = 1.0;
  let strength = 0.006;
  for (var n = 0; n < 4; n++) {
    let tt = t * (1.0 - 3.5 / f32(n + 1));
    q = p + vec2f(cos(tt - q.x) + sin(tt + q.y), sin(tt - q.y) + cos(tt + q.x));
    c += 1.0 / length(vec2f(p.x / (sin(q.x + tt) / strength), p.y / (cos(q.y + tt) / strength)));
  }
  c /= 4.0;
  c = 1.17 - pow(c, 1.4);
  let net = clamp(pow(abs(c), 8.0), 0.0, 1.5);
  return max(net - 0.12, 0.0) * 1.25;
}

fn encode(c: vec3f) -> vec3f {
  let lo = c * 12.92;
  let hi = 1.055 * pow(max(c, vec3f(0.0)), vec3f(1.0 / 2.4)) - 0.055;
  return select(hi, lo, c <= vec3f(0.0031308));
}

struct Out { @builtin(position) pos: vec4f };

@vertex fn vs_full(@builtin(vertex_index) i: u32) -> Out {
  var o: Out;
  let xy = vec2f(f32((i << 1u) & 2u), f32(i & 2u));
  o.pos = vec4f(xy * 2.0 - 1.0, 0.0, 1.0);
  return o;
}

// The light on one square or answer box. 'cell' is the board square it is or
// mirrors (its events: typing, verdicts, solving), 'f' the point within it,
// 'u' the caustic coordinates (square units, continuous across neighbours),
// 'held' the words' light it holds, 'along' its place along the lit word
// (0..1, or -1 when not lit).
fn liquid(cell: i32, f: vec2f, u: vec2f, held: vec3f, glow: vec3f, wave: vec3f, along: f32, cursor: bool) -> vec3f {
  var flags = 0u;
  if (cell >= 0) { flags = flagsOf(cell); }
  let soft = softness(flags);
  var light = vec3f(0.0);

  // Light under water: the words' light broken into a moving net the
  // ripples bend, and a soft glow from the notches nearby.
  let net = caustic(u, wave.yz * 0.6 * soft);
  light += held * net * 2.6 + glow * 0.05;
  let crest = max(wave.x, 0.0) * soft;
  light += (held * 3.0 + glow + roomTint() * 0.04) * crest * 0.5;

  // The lit word: light flows along it, first square to last; the cursor's
  // square breathes.
  if (along >= 0.0 && g.flame.w > 0.5) {
    let flow = pow(0.5 + 0.5 * sin((along * 1.6 - now() * 0.45 * g.dims.w) * TAU), 8.0);
    light += g.flame.rgb * (0.03 + 0.07 * flow * motion()) * (1.0 - along * 0.6);
  }
  if (cell < 0) { return light; }
  let c = cells[cell];
  if (cursor) {
    let a = since(c.a.z);
    let breathe = 0.5 + 0.5 * sin(now() * 2.2 * g.dims.w);
    light += g.flame.rgb * (0.04 + 0.03 * breathe * motion() + 0.18 * exp(-a * 4.0));
  }

  // A typed letter: light gathers inward, a drop landing.
  let pressAge = since(c.a.w);
  if (pressAge < 1.2) {
    let r = max(abs(f.x - 0.5), abs(f.y - 0.5)) * 2.0;
    let ring = exp(-pow((r - (1.0 - pressAge * 2.2)) / 0.08, 2.0)) * exp(-pressAge * 3.0);
    light += (g.flame.rgb * 0.5 + held * 2.0) * ring * 0.5 * soft * motion();
  }
  if (has(flags, CORRECT)) {
    // Crystallises: one clean glint across.
    let a = since(c.b.x);
    let band = exp(-pow((f.x + f.y) * 0.5 - (a * 1.6 - 0.3), 2.0) * 90.0) * exp(-a * 1.1);
    light += vec3f(0.55, 0.62, 0.58) * band * motion();
  }
  if (has(flags, WRONG)) {
    // Fractures: hairline cracks, bright as they open, then a faint scar.
    let a = since(c.b.x);
    let crack = 1.0 - smoothstep(0.0, 0.016, fracture(f, f32(cell) * 0.618));
    light += mix(vec3f(1.0), g.red.rgb, 0.45) * crack * (0.1 + 0.6 * exp(-a * 1.3));
    light += g.red.rgb * 0.12 * exp(-a * 2.0);
  }
  if (has(flags, POP)) {
    let a = since(c.b.y) - c.b.z * 0.38;
    if (a > 0.0) {
      let tone = select(c.sd.rgb, c.sa.rgb, has(flags, SOLVED_A) && c.sa.w >= 0.0);
      light += tone * exp(-a * 3.0) * 0.45;
    }
  }
  return light;
}

fn ceremonyAt(p: vec2f) -> vec3f {
  let ceremony = now() - g.dims.z;
  if (ceremony <= 0.0 || ceremony >= 5.0) { return vec3f(0.0); }
  let r = length(p - (g.board.xy + g.board.zw * 0.5)) / pitch();
  let ring = exp(-pow(r - ceremony * 4.5, 2.0) * 0.35) * exp(-ceremony * 0.6);
  return mix(g.orange.rgb, g.blue.rgb, 0.5 + 0.5 * sin(r * 0.5)) * ring * 0.4;
}

// The overlay's output: light added over the CSS (premultiplied), or on
// paper a dye the page is multiplied by.
fn emit(light: vec3f) -> vec4f {
  let l = light * (1.0 - 0.5 * contrast());
  if (paper()) {
    // A dye passes its own hue: the page is multiplied toward it, as far as
    // the light was strong.
    let peak = max(l.r, max(l.g, l.b));
    let hue = l / max(peak, 0.0001);
    return vec4f(mix(vec3f(1.0), hue, clamp(peak * 2.2, 0.0, 0.42)), 1.0);
  }
  let out = encode(min(l, vec3f(1.0)));
  return vec4f(out, max(out.r, max(out.g, out.b)));
}

fn quad(i: u32, rect: vec4f) -> vec4f {
  let corner = vec2f(f32(i & 1u), f32(i >> 1u));
  let px = rect.xy + corner * rect.zw;
  let ndc = px / g.view.xy * 2.0 - 1.0;
  return vec4f(ndc.x, -ndc.y, 0.0, 1.0);
}

@vertex fn vs_board(@builtin(vertex_index) i: u32) -> Out {
  var o: Out;
  o.pos = quad(i, g.board);
  return o;
}

// The board: the CSS draws the squares; this lights them.
@fragment fn fs_gel(@builtin(position) pos: vec4f) -> @location(0) vec4f {
  let p = pos.xy / g.view.z;
  let P = pitch();
  let u = (p - g.grid.xy) / P;
  let i = cellAt(vec2i(floor(u)));
  if (i < 0) { return emit(vec3f(0.0)); }
  let cell = cells[i];
  let flags = u32(cell.a.x);
  let f = u - floor(u);
  let wave = ripples(p);
  let glow = fieldAt(p - wave.yz * P * 0.05);
  if (has(flags, BLACK)) { return emit(glow * 0.12 + ceremonyAt(p)); }

  var held = vec3f(0.0);
  if (cell.sa.w >= 0.0 && !has(flags, SOLVED_A)) { held += cell.sa.rgb * waterLevel(cell.sa.w, f.x) * g.spill.x * g.lane.x; }
  if (cell.sd.w >= 0.0 && !has(flags, SOLVED_D)) { held += cell.sd.rgb * waterLevel(cell.sd.w, f.y) * g.spill.x * g.lane.y; }
  let along = select(-1.0, max(cell.a.y, 0.0), has(flags, WORD));
  return emit(liquid(i, f, u, held, glow, wave, along, has(flags, CURSOR)) + ceremonyAt(p));
}

struct BoxOut {
  @builtin(position) pos: vec4f,
  @location(0) @interpolate(flat) index: u32,
};

@vertex fn vs_box(@builtin(vertex_index) v: u32, @builtin(instance_index) b: u32) -> BoxOut {
  var o: BoxOut;
  o.pos = quad(v, boxes[b].rect);
  o.index = b;
  return o;
}

fn inside(p: vec2f, r: vec4f) -> bool {
  return all(p >= r.xy) && all(p < r.xy + r.zw);
}

// An answer box: the light its square has, in the clue's own hue, stepping
// down the answer from the first box.
@fragment fn fs_box(in: BoxOut) -> @location(0) vec4f {
  let p = in.pos.xy / g.view.z;
  let box = boxes[in.index];
  let lane = box.info.y;
  let clip = select(g.clipAcross, g.clipDown, lane > 0.5);
  if (!inside(p, clip)) { discard; }
  let flags = u32(box.info.z);
  let f = (p - box.rect.xy) / box.rect.zw;
  let place = box.tint.w;
  let cell = i32(box.info.x);
  let live = select(g.lane.x, g.lane.y, lane > 0.5);
  var solved = false;
  if (cell >= 0) { solved = has(flagsOf(cell), select(SOLVED_A, SOLVED_D, lane > 0.5)); }
  var held = vec3f(0.0);
  if (!solved && has(flags, BOX_RANKED)) { held = box.tint.rgb * waterLevel(place, f.x) * g.spill.x * live; }
  let along = select(-1.0, place / max(box.info.w - 1.0, 1.0), has(flags, BOX_LIT));
  // The net runs on along the row, box to box.
  let u = vec2f(place + f.x + lane * 7.3, f.y + floor(box.rect.y / box.rect.w) * 1.7);
  return emit(liquid(cell, f, u, held, vec3f(0.0), vec3f(0.0), along, has(flags, BOX_CURSOR)));
}
`;

const BLIT = /* wgsl */ `
@group(0) @binding(2) var source: texture_2d<f32>;

struct Copy { @builtin(position) pos: vec4f, @location(0) uv: vec2f };

@vertex fn vs_copy(@builtin(vertex_index) i: u32) -> Copy {
  var o: Copy;
  let xy = vec2f(f32((i << 1u) & 2u), f32(i & 2u));
  o.pos = vec4f(xy * 2.0 - 1.0, 0.0, 1.0);
  o.uv = vec2f(xy.x, 1.0 - xy.y);
  return o;
}

@fragment fn fs_copy(in: Copy) -> @location(0) vec4f {
  let c = textureSampleLevel(source, linearSampler, in.uv, 0.0);
  // Already premultiplied light (or, on paper, a multiply factor).
  return c;
}
`;

export const GLASS_WGSL = GEL + BLIT;
