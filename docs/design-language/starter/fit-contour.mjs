// fit-contour.mjs — fit the lightness contour (l0, l1, l2) for one hue arc.
//
// Why: at a fixed lightness, sRGB holds very different chroma at different
// hues (yellow/green generous; pink/orange/violet/blue tight). One lightness
// per arc therefore clips the tight hues (paler, shifted off their rank) while
// the easy ones stay vivid, and the rainbow steps unevenly. The fix is a small
// per-rank lightness offset  l0 + l1*r + l2*r^2.
//
// Usage:  node fit-contour.mjs <hueStart> <hueEnd> <chroma> <baseL> [margin]
//   e.g.  node fit-contour.mjs 2 142 0.14 0.89        (warm arc, dark ground)
//         node fit-contour.mjs 183 323 0.14 0.75      (cool arc, dark ground)
// Paste the three printed numbers into --a-l0/--a-l1/--a-l2 (or --b-*).
// The crossword's own values were tuned by eye; this reproduces their shape
// (light mode matches closely) and is meant as a first draft to judge by eye.
// baseL is the lane's lightness INCLUDING its lift/drop: ramp-l + a-lift, or
// ramp-l - b-drop. Treat the result as a starting point and judge it by eye.

const [, , hs, he, cs, bl, mg = '0.02'] = process.argv;
const hueStart = Number(hs), hueEnd = Number(he), chroma = Number(cs), baseL = Number(bl), margin = Number(mg);
if ([hueStart, hueEnd, chroma, baseL].some(Number.isNaN)) {
  console.error('usage: node fit-contour.mjs <hueStart> <hueEnd> <chroma> <baseL> [margin]');
  process.exit(1);
}

// OKLCH -> linear sRGB (Björn Ottosson's matrices).
function inGamut(L, C, hDeg) {
  const h = (hDeg * Math.PI) / 180;
  const a = C * Math.cos(h), b = C * Math.sin(h);
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
  const r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  const g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  const bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;
  const eps = 1e-4;
  return [r, g, bb].every((v) => v >= -eps && v <= 1 + eps);
}

// For one rank: the lightness closest to baseL that keeps the colour in gamut
// with `margin` to spare. Scan outward from baseL in small steps.
function bestL(r) {
  const hue = hueStart + r * (hueEnd - hueStart);
  for (let d = 0; d <= 0.6; d += 0.005) {
    for (const L of d === 0 ? [baseL] : [baseL - d, baseL + d]) {
      if (L > 0.05 && L < 0.98 && inGamut(L - margin, chroma, hue) && inGamut(L + margin, chroma, hue)) return L;
    }
  }
  return baseL;
}

const samples = Array.from({ length: 41 }, (_, i) => i / 40);
const offsets = samples.map((r) => bestL(r) - baseL);

// Least-squares quadratic fit: offset ~ l0 + l1*r + l2*r^2 (normal equations).
const S = (f) => samples.reduce((acc, r, i) => acc + f(r, offsets[i]), 0);
const A = [
  [samples.length, S((r) => r), S((r) => r * r)],
  [S((r) => r), S((r) => r * r), S((r) => r ** 3)],
  [S((r) => r * r), S((r) => r ** 3), S((r) => r ** 4)],
];
const B = [S((r, y) => y), S((r, y) => r * y), S((r, y) => r * r * y)];
for (let i = 0; i < 3; i++) {
  const p = A[i][i];
  for (let j = i; j < 3; j++) A[i][j] /= p;
  B[i] /= p;
  for (let k = 0; k < 3; k++) {
    if (k === i) continue;
    const f = A[k][i];
    for (let j = i; j < 3; j++) A[k][j] -= f * A[i][j];
    B[k] -= f * B[i];
  }
}
const [l0, l1, l2] = B.map((v) => Math.round(v * 1000) / 1000);

// Report how well the fitted curve keeps the arc in gamut.
let clipped = 0;
for (const r of samples) {
  const hue = hueStart + r * (hueEnd - hueStart);
  if (!inGamut(baseL + l0 + l1 * r + l2 * r * r, chroma, hue)) clipped += 1;
}
console.log(`l0: ${l0}   l1: ${l1}   l2: ${l2}`);
console.log(`ranks still outside sRGB with this fit: ${clipped} of ${samples.length}`);
console.log('Browsers gamut-map the remainder by quietly lowering chroma, so a few is fine.');
console.log('If more than a quarter are outside, lower the chroma, shorten the arc, or move baseL.');
