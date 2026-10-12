import { describe, expect, it } from 'vitest';
import { DEFAULT_TOKENS, boardCharge, flameTint, laneTint, oklchToLinear, parseColor } from './tint';

const close = (actual: readonly number[], expected: readonly number[], digits = 3) =>
  actual.forEach((value, i) => expect(value).toBeCloseTo(expected[i], digits));

describe('the glass layer speaks the board’s colours', () => {
  it('reads hex and rgb() colours into linear RGB', () => {
    close(parseColor('#ffffff') ?? [], [1, 1, 1]);
    close(parseColor('#000') ?? [], [0, 0, 0]);
    close(parseColor('rgb(255, 0, 0)') ?? [], [1, 0, 0]);
    // sRGB mid-grey is about a fifth of the light in linear terms.
    close(parseColor('#808080') ?? [], [0.2158, 0.2158, 0.2158]);
    expect(parseColor('oklch(0.8 0.1 40)')).toBeNull();
  });

  it('converts OKLCH to linear sRGB the way CSS does', () => {
    close(oklchToLinear(1, 0, 0), [1, 1, 1]);
    close(oklchToLinear(0, 0, 0), [0, 0, 0]);
    // oklch(0.628 0.2577 29.23) is sRGB red.
    close(oklchToLinear(0.62796, 0.25768, 29.2339), [1, 0, 0], 2);
  });

  it('puts Across on the warm arc a step brighter and Down on the cool arc a step quieter', () => {
    const across = laneTint(DEFAULT_TOKENS, 'across', 0.5);
    const down = laneTint(DEFAULT_TOKENS, 'down', 0.5);
    // Across 40 in a 1-80 puzzle reads orange: red over green over blue.
    expect(across[0]).toBeGreaterThan(across[1]);
    expect(across[1]).toBeGreaterThan(across[2]);
    // Down's middle reads blue.
    expect(down[2]).toBeGreaterThan(down[0]);
    const lum = (c: readonly number[]) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    expect(lum(laneTint(DEFAULT_TOKENS, 'across', 0.2))).toBeGreaterThan(lum(laneTint(DEFAULT_TOKENS, 'down', 0.2)) * 0.9);
  });

  it('spends more chroma on the flame than on the resting tint', () => {
    const rest = laneTint(DEFAULT_TOKENS, 'across', 0.3);
    const flame = flameTint(DEFAULT_TOKENS, 'across', 0.3);
    const spread = (c: readonly number[]) => Math.max(...c) - Math.min(...c);
    expect(spread(flame)).toBeGreaterThan(spread(rest));
  });

  it('gathers the charge as words are solved, dims it with the score, warms it with a combo', () => {
    expect(boardCharge(1, 1, 0)).toBeCloseTo(1);
    expect(boardCharge(0.25, 1, 0)).toBeCloseTo(2);
    expect(boardCharge(1, 0.5, 0)).toBeCloseTo(0.5);
    expect(boardCharge(1, 1, 1)).toBeCloseTo(1.45);
    expect(boardCharge(0, 1, 1)).toBe(2.6);
    expect(boardCharge(1, 0, 0)).toBe(0.18);
  });
});
