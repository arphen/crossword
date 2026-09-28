// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { assistanceLadder } from './assistanceLadder';

function app() {
  return {
    grid: [['A', '', ''], ['', null, null], ['', null, null]],
    crossword: [
      {
        direction: 'across',
        clue_number: 1,
        clue_text: 'Feline?',
        start_x: 0,
        start_y: 0,
        characters: [{ letters: 'C' }, { letters: 'A' }, { letters: 'T' }],
      },
      {
        direction: 'down',
        clue_number: 1,
        clue_text: 'Vehicle',
        start_x: 0,
        start_y: 0,
        characters: [{ letters: 'C' }, { letters: 'A' }, { letters: 'R' }],
      },
    ],
  };
}

describe('prepared assistance ladder', () => {
  it('offers an answer-free clue reading nudge and a crossing follow-up', () => {
    const ladder = assistanceLadder(app(), app().crossword[0]);
    expect(ladder.map((hint) => hint.assistanceTier)).toEqual([
      'clue-reading',
      'context',
      'crossing',
      'letter',
      'answer',
    ]);
    expect(ladder[0].hintId).toBe('prepared-clue-reading-v1');
    expect(ladder[0].text).toMatch(/question mark/i);
    expect(ladder[0].text).not.toMatch(/CAT/i);
    expect(ladder[1].affectedCellIds).toEqual(['r0c0']);
    expect(ladder[2].text).toMatch(/Across|Down/);
    expect(ladder[3].reveal).toBe('letter');
    expect(ladder[4].reveal).toBe('answer');
  });

  it('explains language, number, and fill conventions without exposing answers', () => {
    const conventions = [
      {
        ...app().crossword[0],
        clue_text: 'Yes, in German (pl.)',
      },
      {
        ...app().crossword[0],
        clue_text: 'Safe and ___',
      },
    ];

    const languageLadder = assistanceLadder(
      { ...app(), crossword: conventions },
      conventions[0],
    );
    expect(languageLadder[0].text).toMatch(/language of the answer/i);
    expect(languageLadder[0].text).toMatch(/plural marker/i);
    expect(languageLadder[0].text).not.toMatch(/\b(?:JA|OUI|SI)\b/i);

    const fillLadder = assistanceLadder(
      { ...app(), crossword: conventions },
      conventions[1],
    );
    expect(fillLadder[0].text).toMatch(/blank signals/i);
    expect(fillLadder[0].text).not.toMatch(/SAFE/i);
  });

  it('calls a multi-unit assistance reveal a token', () => {
    const tokenEntry = {
      ...app().crossword[0],
      characters: [
        { letters: 'C' },
        {
          letters: 'SS',
          tokenMetadata: { displayToken: 'ß', fillToken: 'SS', rebus: true },
        },
        { letters: 'T' },
      ],
    };
    const ladder = assistanceLadder(
      { ...app(), crossword: [tokenEntry, app().crossword[1]] },
      tokenEntry,
    );

    expect(ladder.find((hint) => hint.assistanceTier === 'letter')).toMatchObject({
      label: 'Reveal a token',
      text: expect.stringContaining('declared token'),
    });
  });
});
