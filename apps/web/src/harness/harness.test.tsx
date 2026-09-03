// @vitest-environment jsdom

import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it } from 'vitest';
import { HarnessPage } from './HarnessPage';
import { resolveHarnessFixture, resolveHarnessMode } from './fixtures';

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function renderHarness(fixtureId: string | null, mode: 'light' | 'dark' | 'forced' | 'zoom' = 'light') {
  const rootElement = document.createElement('div');
  document.body.append(rootElement);
  const root = createRoot(rootElement);
  act(() => {
    root.render(<HarnessPage fixtureId={fixtureId} mode={mode} />);
  });
  const unmount = () => {
    act(() => root.unmount());
    rootElement.remove();
  };
  return { rootElement, unmount };
}

describe('visual harness', () => {
  it('falls back to the first fixture for unknown ids', () => {
    expect(resolveHarnessFixture('does-not-exist').id).toBe('empty-15');
    expect(resolveHarnessMode('sepia')).toBe('light');
  });

  it('renders every fixture deterministically across two mounts', () => {
    for (const fixture of ['empty-15', 'active-across', 'active-down-typed', 'check-error', 'half-collapsed', 'long-clue', 'special-cells']) {
      const first = renderHarness(fixture);
      const markup = first.rootElement.innerHTML;
      first.unmount();

      const second = renderHarness(fixture);
      expect(second.rootElement.innerHTML).toBe(markup);
      expect(markup).not.toContain('NaN');
      second.unmount();
    }
  });

  it('exposes the fixture index and documents placeholders instead of faking states', () => {
    const { rootElement, unmount } = renderHarness('special-cells');
    expect(rootElement.querySelectorAll('.harness-index a').length).toBeGreaterThanOrEqual(7);
    expect(rootElement.querySelector('.harness-notes')?.textContent).toContain('rebus');
    unmount();

    const long = renderHarness('long-clue');
    expect(long.rootElement.querySelector('.harness-notes')?.textContent).toContain('15-letter');
    long.unmount();
  });

  it('marks the night wrapper with the legacy color scheme', () => {
    const { rootElement, unmount } = renderHarness('active-across', 'dark');
    expect(rootElement.querySelector('.harness-root')?.classList.contains('harness-night')).toBe(true);
    const wrapper = rootElement.querySelector<HTMLElement>('.harness-root');
    expect(wrapper?.style.colorScheme).toBe('dark');
    unmount();
  });
});
