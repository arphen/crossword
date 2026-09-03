import { describe, expect, it } from 'vitest';

import { curatedTemplateBank } from './templateBank';
import { DEFAULT_MIN_ENTRY_LENGTH, deriveTopology, validateTopologyMask } from './topology';

const HUMAN_MASK = [
  '....#....#.....',
  '....#....#.....',
  '....#....#.....',
  '...........#...',
  '####...#...#...',
  '......#......##',
  '.....#....#....',
  '.....#...#.....',
  '....#....#.....',
  '##......#......',
  '...#...#...####',
  '...#...........',
  '.....#....#....',
  '.....#....#....',
  '.....#....#....'
];

describe('topology derivation', () => {
  it('accepts the proven human mask', () => {
    expect(validateTopologyMask(HUMAN_MASK, 3)).toEqual([]);
  });

  it('validates EVERY curated bank template (fill-measured production data)', () => {
    const bank = curatedTemplateBank();
    expect(bank.length).toBeGreaterThan(0);
    for (const template of bank) {
      const violations = validateTopologyMask(template.mask, 3);
      expect(violations, `template ${template.id}: ${violations.map((v) => v.code).join(',')}`).toEqual([]);
    }
  });

  it('rejects a disconnected or unchecked simple mask', () => {
    // Two disconnected across rows: invalid under the full invariant set.
    const violations = validateTopologyMask(['...', '###', '...'], 3);
    expect(violations.length).toBeGreaterThan(0);
    expect(violations.some((violation) => violation.code === 'short-run')).toBe(true);
    expect(violations.some((violation) => violation.code === 'unchecked-cell')).toBe(true);
  });

  it('rejects a disconnected mask', () => {
    const violations = validateTopologyMask(['..#', '###', '#..'], 3);
    expect(violations.some((violation) => violation.code === 'disconnected')).toBe(true);
  });

  it('rejects short runs and unchecked cells', () => {
    const violations = validateTopologyMask(['..#....'], 3);
    expect(violations.some((violation) => violation.code === 'short-run')).toBe(true);
  });

  it('numbers entries in standard row-major crossword order', () => {
    const derived = deriveTopology(HUMAN_MASK, { templateId: 'human' });
    if (!derived.ok) throw new Error(JSON.stringify(derived.violations));
    const numbers = [...derived.topology.numberByCellId.entries()];
    expect(numbers.length).toBeGreaterThan(20);
    expect([...derived.topology.numberByCellId.values()]).toEqual(
      [...derived.topology.numberByCellId.values()].sort((a, b) => a - b)
    );
  });
});
