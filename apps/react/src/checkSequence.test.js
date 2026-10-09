import { describe, expect, it } from 'vitest';
import { ASCEND_MS, planSequence, wordStep } from './checkSequence';

const word = (key, ...cells) => ({ key, cells });

describe('the check sequence', () => {
  it('takes its time over a few words and hurries a sweep', () => {
    expect(wordStep(1)).toBe(0);
    expect(wordStep(3)).toBe(165);
    expect(wordStep(20)).toBe(85);
    expect(wordStep(76)).toBe(34);
    // Even a whole board's worth of words pops in under two and a half seconds.
    expect(75 * wordStep(76)).toBeLessThan(2600);
  });

  it('pops the solved words one after another, in the order given', () => {
    const plan = planSequence({
      words: [word('across-1', '0,0', '0,1'), word('down-1', '0,0', '1,0'), word('across-3', '2,0', '2,1')],
      verdicts: [['0,0', 'green'], ['0,1', 'green'], ['1,0', 'green'], ['2,0', 'green'], ['2,1', 'green']],
    });
    const words = plan.events.filter((event) => event.type === 'word');
    expect(words.map((event) => event.key)).toEqual(['across-1', 'down-1', 'across-3']);
    expect(words[1].at - words[0].at).toBe(165);
    // A shared square lights with the first word through it, once.
    expect(words.map((event) => event.cells.map(([cell]) => cell))).toEqual([['0,0', '0,1'], ['1,0'], ['2,0', '2,1']]);
    expect(plan.wordAt.get('across-3')).toBe(words[2].at);
    expect(plan.releaseAt).toBe(words[2].at + ASCEND_MS + 60);
  });

  it('settles the other right letters after the words, then lands the mistakes last', () => {
    const plan = planSequence({
      words: [word('across-1', '0,0', '0,1')],
      verdicts: [['0,0', 'green'], ['0,1', 'green'], ['3,3', 'green'], ['3,4', 'red'], ['5,9', 'red'], ['4,4', 'blank']],
      breakBeat: { kind: 'break' },
    });
    const types = plan.events.map((event) => event.type);
    expect(types).toEqual(['word', 'cells', 'break']);
    const settled = plan.events.find((event) => event.type === 'cells');
    expect(settled.cells).toEqual([['3,3', 'green']]);
    const blow = plan.events.find((event) => event.type === 'break');
    expect(blow.at).toBeGreaterThan(settled.at);
    // The crack spreads from the first wrong letter: the far one lands later.
    expect(blow.cells).toEqual([['3,4', 'red', 0], ['5,9', 'red', 190]]);
    // Blank squares are never painted.
    expect(plan.events.flatMap((event) => event.cells || []).some(([cell]) => cell === '4,4')).toBe(false);
    expect(plan.end).toBeGreaterThanOrEqual(blow.at);
  });

  it('plays a check with only mistakes straight away', () => {
    const plan = planSequence({ verdicts: [['1,1', 'red']], breakBeat: { kind: 'break' } });
    expect(plan.events).toEqual([{ at: 70, type: 'break', cells: [['1,1', 'red', 0]] }]);
    expect(plan.releaseAt).toBe(0);
  });

  it('keeps a long ripple to a handful of events', () => {
    const verdicts = Array.from({ length: 120 }, (_, index) => [`${Math.floor(index / 15)},${index % 15}`, 'green']);
    const plan = planSequence({ verdicts });
    const cells = plan.events.filter((event) => event.type === 'cells');
    expect(cells.length).toBeLessThan(30);
    expect(cells.reduce((sum, event) => sum + event.cells.length, 0)).toBe(120);
    expect(plan.end).toBeLessThan(800);
  });
});
