import { describe, expect, it } from 'vitest';
import { glassPalette, PALETTE_SLOTS, paletteFloats, weekdayIndex } from './palette';

describe('glass palette', () => {
  it('reads a weekday from its name, Monday when unknown', () => {
    expect(weekdayIndex('Sunday')).toBe(0);
    expect(weekdayIndex(' saturday ')).toBe(6);
    expect(weekdayIndex('')).toBe(1);
    expect(weekdayIndex(undefined)).toBe(1);
  });

  it('gives every day its own room and keeps the shared voice', () => {
    const rooms = new Set([0, 1, 2, 3, 4, 5, 6].map((day) => glassPalette(day).skyHigh.join(',')));
    expect(rooms.size).toBe(7);
    // Across stays orange and Down blue, whatever the day.
    const monday = glassPalette(1);
    const friday = glassPalette(5);
    expect(monday.across).toEqual(friday.across);
    expect(monday.across[0]).toBeGreaterThan(monday.across[2]);
    expect(monday.down[2]).toBeGreaterThan(monday.down[0]);
  });

  it('lights paper and night differently', () => {
    const night = glassPalette(3, false);
    const paper = glassPalette(3, true);
    const luma = (rgb: number[]) => rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
    expect(luma(paper.glass)).toBeGreaterThan(luma(night.glass));
    expect(luma(paper.skyLow)).toBeGreaterThan(0.5);
    expect(luma(night.obsidian)).toBeLessThan(0.01);
  });

  it('packs the palette into the order the shaders read', () => {
    const floats = paletteFloats(glassPalette(2));
    expect(floats).toHaveLength(PALETTE_SLOTS * 4);
    const f32 = (rgb: number[]) => [...Float32Array.from(rgb)];
    expect([...floats.slice(0, 3)]).toEqual(f32(glassPalette(2).skyLow));
    expect(floats[3]).toBe(1);
    expect([...floats.slice(11 * 4, 11 * 4 + 3)]).toEqual(f32(glassPalette(2).key));
  });
});
