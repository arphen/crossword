// @vitest-environment jsdom
import React from 'react';
import { expect, it, vi } from 'vitest';
import { displayedPuzzleWeekday, renderClueSurface } from './CrosswordView';

it('uses the personal recipe label when the future route supplies one', () => {
  const app = { getCurrentDayName: vi.fn(() => 'Monday') };
  expect(displayedPuzzleWeekday(app, 'Wednesday')).toBe('Wednesday');
  expect(app.getCurrentDayName).not.toHaveBeenCalled();
});

it('keeps the daily solver weekday derived from its puzzle date', () => {
  const app = { getCurrentDayName: vi.fn(() => 'Monday') };
  expect(displayedPuzzleWeekday(app)).toBe('Monday');
  expect(app.getCurrentDayName).toHaveBeenCalledOnce();
});

it('annotates clue grammar signals without rewriting the source surface', () => {
  const parts = renderClueSurface('Say "hello"? [sound] ___, briefly (pl.) past tense', true);
  const signals = parts.filter(part => React.isValidElement(part));

  expect(signals.map(part => part.props['data-clue-signal'])).toEqual([
    'quote',
    'question',
    'bracket',
    'blank',
    'abbreviation',
    'plural',
    'tense',
  ]);
  expect(signals[0].props.children).toBe('"hello"');
  expect(signals[0].props.tabIndex).toBe(0);
  expect(signals[0].props['aria-label']).toContain('Quotation');
  expect(signals[0].props.title).toContain('Quotation');
});

it('annotates straight and curly single-quote clue surfaces', () => {
  const parts = renderClueSurface("'___ the knot' (Spoken equivalent) · ‘A sugary ___’", true);
  const signals = parts.filter(part => React.isValidElement(part));

  expect(signals.map(part => part.props['data-clue-signal'])).toEqual(['quote', 'quote']);
  expect(signals[0].props.children).toBe("'___ the knot'");
  expect(signals[1].props.children).toBe('‘A sugary ___’');
});

it('leaves daily clue text untouched when annotation is disabled', () => {
  const text = 'Capital of Ghana?';
  expect(renderClueSurface(text)).toBe(text);
});
