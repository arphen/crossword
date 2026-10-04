import { describe, expect, it } from 'vitest';
import { createSelectionPresentation } from './selectionPresentation';

const entry = (direction, letters = ['A', 'QU', 'C', 'D', 'E']) => ({
    direction, start_x: 4, start_y: 2, clue_number: 17,
    characters: letters.map(letters => ({ letters }))
});

describe('active-word position cues', () => {
    it('gives a crossing the active ordinal, independent of its own clue index', () => {
        const across = createSelectionPresentation(entry('across'));
        // The third Across cell can be the first letter of a crossing Down clue.
        expect(across.get('2,6')).toMatchObject({ index: 2, length: 5,
            style: { '--entry-position': '50%' } });
        expect(across.has('3,6')).toBe(false);
        expect(across.get('2,4').style['--entry-position']).toBe('0%');
        expect(across.get('2,8').style['--entry-position']).toBe('100%');
    });

    it('changes axis with direction and counts a rebus as one box', () => {
        const down = createSelectionPresentation(entry('down'));
        expect(down.size).toBe(5);
        expect(down.get('3,4')).toMatchObject({ index: 1,
            style: { '--entry-position': '25%' } });
        expect(down.get('6,4').title).toBe('Letter 5 of 5 · 17 down');
        expect(down.has('2,5')).toBe(false);
    });

    it('handles no selection and single-cell entries without invalid colors', () => {
        expect(createSelectionPresentation(null).size).toBe(0);
        expect(createSelectionPresentation(entry('across', ['A'])).get('2,4').style)
            .toEqual({ '--entry-position': '0%' });
    });
});
