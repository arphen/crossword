import { describe, expect, it } from 'vitest';
import {
  VIEW_DEFAULTS,
  VIEW_SETTINGS_KEY,
  normalizeViewSettings,
  prefersLowBloom,
  readViewSettings,
  viewAttributes,
  writeViewSettings,
} from './viewSettings';

const memory = (initial = {}) => {
  const stored = new Map(Object.entries(initial));
  return {
    getItem: (key) => (stored.has(key) ? stored.get(key) : null),
    setItem: (key, value) => stored.set(key, String(value)),
    read: () => (stored.has(VIEW_SETTINGS_KEY) ? stored.get(VIEW_SETTINGS_KEY) : null),
  };
};

const lowBloom = (query) => ({ matches: query.includes('prefers-contrast') });

describe('view settings', () => {
  it('starts from the defaults when nothing was saved', () => {
    expect(readViewSettings({ storage: memory() })).toEqual(VIEW_DEFAULTS);
    expect(normalizeViewSettings(undefined)).toEqual(VIEW_DEFAULTS);
  });

  it('lets a saved choice outrank the display hint', () => {
    const storage = memory({
      [VIEW_SETTINGS_KEY]: JSON.stringify({ ...VIEW_DEFAULTS, luma: 'veil' }),
    });
    expect(readViewSettings({ storage, media: lowBloom }).luma).toBe('veil');
  });

  it('opens a low-bloom display on the dim tier', () => {
    expect(readViewSettings({ storage: memory(), media: lowBloom }).luma).toBe('dim');
    expect(readViewSettings({ storage: memory(), media: () => null }).luma).toBe(
      'standard',
    );
    expect(prefersLowBloom(undefined)).toBe(false);
  });

  it('ignores a stored value that names no real option', () => {
    const storage = memory({
      [VIEW_SETTINGS_KEY]: JSON.stringify({
        luma: 'brightest',
        grouping: 'threes',
        rail: 'yes',
      }),
    });
    expect(readViewSettings({ storage })).toEqual(VIEW_DEFAULTS);
  });

  it('survives storage that is broken or refuses to be written', () => {
    expect(readViewSettings({ storage: memory({ [VIEW_SETTINGS_KEY]: '{oops' }) })).toEqual(
      VIEW_DEFAULTS,
    );
    expect(readViewSettings()).toEqual(VIEW_DEFAULTS);
    expect(() =>
      writeViewSettings(VIEW_DEFAULTS, {
        storage: {
          setItem: () => {
            throw new Error('quota');
          },
        },
      }),
    ).not.toThrow();
  });

  it('saves exactly the settings it is given', () => {
    const storage = memory();
    writeViewSettings({ ...VIEW_DEFAULTS, grouping: 'none' }, { storage });
    expect(JSON.parse(storage.read())).toEqual({ ...VIEW_DEFAULTS, grouping: 'none' });
  });
});

describe('board attributes', () => {
  it('publishes every setting the stylesheets key off', () => {
    expect(viewAttributes(VIEW_DEFAULTS)).toEqual({
      'data-luma': 'standard',
      'data-scale': 'normal',
      'data-rail': 'on',
      'data-ramp': 'on',
      'data-grouping': 'auto',
      'data-cues': 'on',
      'data-glyph': 'regular',
    });
  });

  it('writes a switch as on or off rather than as a boolean', () => {
    const attributes = viewAttributes({ ...VIEW_DEFAULTS, cues: false, rail: false });
    expect(attributes['data-cues']).toBe('off');
    expect(attributes['data-rail']).toBe('off');
    expect(attributes['data-grouping']).toBe('auto');
  });
});
