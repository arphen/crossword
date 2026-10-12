// The lane as one object: every chip is a mass, every spring between two
// chips couples them, and each chip is tied loosely to its resting place. A
// knock on one chip (a word solved, a mistake, a clue picked) travels up and
// down the lane through the springs and dies away. A discrete wave equation
// with damping, stepped at a fixed rate; the displacement is sideways (along
// the lane's width), so the coils visibly stretch and slacken as it passes.
// Pure arithmetic, so the motion is testable without a browser; ClueSpring
// draws it, without reading the DOM per frame.

export const CHAIN = {
  coupling: 820, // neighbour pull, 1/s²: how fast a knock travels along
  anchor: 46, // pull back to rest, 1/s²
  damping: 3.4, // 1/s
  limit: 16, // px: a chip never swings further than this
};
const STEP = 1 / 240;

/** A chain keyed by clue number, so it survives chips joining and leaving. */
export function createChain() {
  return { u: new Map(), v: new Map() };
}

/** Give one chip a knock: `impulse` is a velocity in px/s, signed. */
export function pluck(chain, number, impulse) {
  chain.v.set(number, (chain.v.get(number) || 0) + impulse);
  if (!chain.u.has(number)) chain.u.set(number, 0);
}

/** Advance the chain by `dt` seconds along the chips in lane order. */
export function stepChain(chain, order, dt, params = CHAIN) {
  const count = order.length;
  if (!count) return;
  let remaining = Math.min(dt, 1 / 20);
  const u = order.map((number) => chain.u.get(number) || 0);
  const v = order.map((number) => chain.v.get(number) || 0);
  const a = new Array(count).fill(0);
  while (remaining > 1e-6) {
    const h = Math.min(STEP, remaining);
    for (let i = 0; i < count; i += 1) {
      const left = i > 0 ? u[i - 1] - u[i] : 0;
      const right = i + 1 < count ? u[i + 1] - u[i] : 0;
      a[i] = params.coupling * (left + right) - params.anchor * u[i] - params.damping * v[i];
    }
    for (let i = 0; i < count; i += 1) {
      v[i] += a[i] * h;
      u[i] = Math.max(-params.limit, Math.min(params.limit, u[i] + v[i] * h));
    }
    remaining -= h;
  }
  chain.u.clear();
  chain.v.clear();
  order.forEach((number, i) => {
    chain.u.set(number, u[i]);
    chain.v.set(number, v[i]);
  });
}

/** Whether anything is still visibly moving. */
export function chainAtRest(chain, epsilon = 0.04) {
  for (const value of chain.u.values()) if (Math.abs(value) > epsilon) return false;
  for (const value of chain.v.values()) if (Math.abs(value) > epsilon * 20) return false;
  return true;
}

/** A CSS cubic-bezier timing function as a function of progress, so motion
 *  drawn in JS can follow an animation the browser is running. */
export function cubicBezier(x1, y1, x2, y2) {
  const sample = (a1, a2, t) => ((1 - 3 * a2 + 3 * a1) * t + (3 * a2 - 6 * a1)) * t * t + 3 * a1 * t;
  const slope = (a1, a2, t) => 3 * (1 - 3 * a2 + 3 * a1) * t * t + 2 * (3 * a2 - 6 * a1) * t + 3 * a1;
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i += 1) {
      const error = sample(x1, x2, t) - x;
      const d = slope(x1, x2, t);
      if (Math.abs(error) < 1e-5 || Math.abs(d) < 1e-6) break;
      t -= error / d;
    }
    return sample(y1, y2, Math.min(1, Math.max(0, t)));
  };
}
