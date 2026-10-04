// Geometry for the clue springs: arithmetic from measured chip rectangles to SVG
// path data. No DOM and no React, so the shape of a spring is testable on its own.

const RELAXED_COILS = 5.5;
const TAUT_COILS = 2.5;
const RELAXED_RADIUS = 4.6;
const TAUT_RADIUS = 2.4;
// A gap of this many ramp steps is as taut as a spring gets.
const TAUT_AT = 12;

/**
 * How tight a spring is wound, from how many ramp steps it has to span. Adjacent
 * numbers are a relaxed spring; every solved clue between two chips pulls the
 * pair further apart, and the same length has to carry more colour change, so the
 * coil opens out and flattens: the slack has been taken up.
 */
export function springTension(steps) {
  const gap = Math.max(1, Number.isFinite(steps) ? steps : 1);
  const taut = Math.min(1, Math.log(gap) / Math.log(TAUT_AT));
  return {
    taut,
    coils: RELAXED_COILS + (TAUT_COILS - RELAXED_COILS) * taut,
    radius: RELAXED_RADIUS + (TAUT_RADIUS - RELAXED_RADIUS) * taut,
    // Loops close up on a relaxed coil and open into a plain wave when pulled.
    loop: 1.9 - 1.2 * taut,
  };
}

/** Where the line between two chip centres leaves each chip's rectangle, pulled in
 *  a pixel so the coil tucks under the chip rather than stopping short of it. */
export function springEnds(a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy);
  if (length === 0) return { from: { x: a.x, y: a.y }, to: { x: b.x, y: b.y } };
  const tx = dx / length;
  const ty = dy / length;
  const reach = (chip) =>
    Math.min(
      tx === 0 ? Infinity : chip.hw / Math.abs(tx),
      ty === 0 ? Infinity : chip.hh / Math.abs(ty),
    ) - 1;
  const out = reach(a);
  const inward = reach(b);
  return {
    from: { x: a.x + tx * out, y: a.y + ty * out },
    to: { x: b.x - tx * inward, y: b.y - ty * inward },
  };
}

const smooth = (value) => value * value * (3 - 2 * value);
const round = (value) => Math.round(value * 10) / 10;

/**
 * A coil from `from` to `to`: a prolate trochoid, the curve a helix makes when it
 * is drawn at a slant, which is what a spring looks like in a diagram. The radius
 * is eased in over the first and last tenth so both ends meet their chip on the
 * axis instead of mid-swing.
 */
export function coilPath(from, to, { coils, radius, loop }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy);
  if (!(length >= 4)) return '';
  const tx = dx / length;
  const ty = dy / length;
  const nx = -ty;
  const ny = tx;
  const turn = Math.PI * 2 * coils;
  const loopRadius = (loop * length) / turn;
  const steps = Math.max(12, Math.ceil(coils * 18));
  const points = [];
  for (let step = 0; step <= steps; step += 1) {
    const s = step / steps;
    const theta = turn * s;
    const ease = smooth(Math.min(1, s / 0.1, (1 - s) / 0.1));
    const along = length * s - ease * loopRadius * Math.sin(theta);
    const across = ease * radius * Math.cos(theta);
    points.push(
      `${round(from.x + tx * along + nx * across)} ${round(from.y + ty * along + ny * across)}`,
    );
  }
  return `M${points.join('L')}`;
}

/**
 * One spring between each pair of neighbouring chips in a lane. `chips` are the
 * measured centres and half-sizes in list order, `numbers` the clue numbers in the
 * same order, `ramp` the number → 0..1 map from createClueRamp, and `states` a
 * parallel list of 'active' | 'affected' | '' so the springs at the selected rung
 * can answer to it.
 */
export function springSegments({ chips, numbers, ramp, states = [], lane = 'lane' }) {
  const span = Math.max(1, (ramp?.size || 1) - 1);
  const count = Math.min(chips.length, numbers.length);
  const segments = [];
  for (let index = 0; index + 1 < count; index += 1) {
    const fromRamp = ramp?.get(numbers[index]) ?? 0;
    const toRamp = ramp?.get(numbers[index + 1]) ?? 0;
    const steps = Math.round(Math.abs(toRamp - fromRamp) * span);
    const tension = springTension(steps);
    const ends = springEnds(chips[index], chips[index + 1]);
    const d = coilPath(ends.from, ends.to, tension);
    if (!d) continue;
    const pair = [states[index], states[index + 1]];
    segments.push({
      key: `${lane}-${numbers[index]}-${numbers[index + 1]}`,
      d,
      from: ends.from,
      to: ends.to,
      fromRamp,
      toRamp,
      steps,
      taut: round(tension.taut * 100) / 100,
      state: pair.includes('rapture')
        ? 'rapture'
        : pair.includes('active')
          ? 'active'
          : pair.includes('affected')
            ? 'affected'
            : '',
    });
  }
  return segments;
}
