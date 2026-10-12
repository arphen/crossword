import { describe, expect, it } from 'vitest';
import { chainAtRest, createChain, cubicBezier, pluck, stepChain } from './springMotion';

const lane = Array.from({ length: 21 }, (_, index) => index + 1);
const run = (chain, seconds, order = lane) => {
  for (let t = 0; t < seconds; t += 1 / 60) stepChain(chain, order, 1 / 60);
};

describe('the lane as one object', () => {
  it('carries a knock on one chip along to its neighbours', () => {
    const chain = createChain();
    pluck(chain, 11, 200);
    run(chain, 0.05);
    const near = Math.abs(chain.u.get(12));
    const far = Math.abs(chain.u.get(20));
    expect(near).toBeGreaterThan(0.2);
    expect(near).toBeGreaterThan(far);
    run(chain, 0.4);
    // By now the wave has reached the end of the lane.
    expect(Math.abs(chain.u.get(21)) + Math.abs(chain.v.get(21))).toBeGreaterThan(0.05);
  });

  it('dies away and comes to rest', () => {
    const chain = createChain();
    pluck(chain, 3, 300);
    run(chain, 0.2);
    expect(chainAtRest(chain)).toBe(false);
    run(chain, 6);
    expect(chainAtRest(chain)).toBe(true);
  });

  it('never swings a chip past its limit', () => {
    const chain = createChain();
    pluck(chain, 1, 100000);
    run(chain, 0.5);
    for (const value of chain.u.values()) expect(Math.abs(value)).toBeLessThanOrEqual(16);
  });

  it('keeps its state per clue number when the lane changes', () => {
    const chain = createChain();
    pluck(chain, 5, 150);
    run(chain, 0.05);
    const before = chain.u.get(5);
    // Clue 4 leaves the lane; 5 keeps its own displacement.
    stepChain(chain, lane.filter((number) => number !== 4), 0);
    expect(chain.u.get(5)).toBe(before);
    expect(chain.u.has(4)).toBe(false);
  });
});

describe('cubic-bezier', () => {
  it('matches the ends and the shape of an overshooting ease', () => {
    const ease = cubicBezier(0.3, 1.45, 0.5, 1);
    expect(ease(0)).toBe(0);
    expect(ease(1)).toBe(1);
    const peak = Math.max(...Array.from({ length: 50 }, (_, index) => ease(index / 50)));
    expect(peak).toBeGreaterThan(1);
    expect(cubicBezier(0, 0, 1, 1)(0.3)).toBeCloseTo(0.3, 3);
  });
});
