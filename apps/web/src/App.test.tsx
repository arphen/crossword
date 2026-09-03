// @vitest-environment jsdom

import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it } from 'vitest';
import App from './App';

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe('legacy replica shell', () => {
  it('renders the legacy composition from domain state', async () => {
    const rootElement = document.createElement('div');
    document.body.append(rootElement);
    const root = createRoot(rootElement);

    await act(async () => {
      root.render(<App />);
    });

    expect(document.querySelectorAll('.clue-column')).toHaveLength(2);
    expect(document.querySelector('#across')).not.toBeNull();
    expect(document.querySelector('#down')).not.toBeNull();
    expect(document.querySelectorAll('#crossword-container .grid-cell').length).toBe(225);
    expect(document.querySelectorAll('#crossword-container input').length).toBe(187);
    expect(document.querySelectorAll('.stat-item').length).toBeGreaterThanOrEqual(5);
    expect(document.querySelector('.theme-switch input')).not.toBeNull();
    expect(document.querySelector('.action-bar')).not.toBeNull();

    await act(async () => {
      root.unmount();
    });
    rootElement.remove();
  });
});
