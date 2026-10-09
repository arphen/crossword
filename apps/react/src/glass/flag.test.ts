import { describe, expect, it } from 'vitest';
import { GLASS_STORAGE_KEY, readGlassFlag } from './flag';

const store = (value: string | null) => ({ getItem: (key: string) => (key === GLASS_STORAGE_KEY ? value : null) });

describe('glass flag', () => {
  it('is off by default', () => {
    expect(readGlassFlag('', null)).toEqual({ enabled: false, debug: false, backend: 'auto' });
    expect(readGlassFlag('?other=1', store(null)).enabled).toBe(false);
  });

  it('turns on for a visit with ?gpu=1 and off with ?gpu=0', () => {
    expect(readGlassFlag('?gpu=1', null).enabled).toBe(true);
    expect(readGlassFlag('?gpu', null).enabled).toBe(true);
    expect(readGlassFlag('?gpu=0', store('1')).enabled).toBe(false);
  });

  it('remembers a stored override until the address bar says otherwise', () => {
    expect(readGlassFlag('', store('1')).enabled).toBe(true);
    expect(readGlassFlag('', store('0')).enabled).toBe(false);
    expect(readGlassFlag('?gpu=1', store('0')).enabled).toBe(true);
  });

  it('asks for the debug readout (which implies the layer) and can force WebGL2', () => {
    expect(readGlassFlag('?gpu-debug', null)).toEqual({ enabled: true, debug: true, backend: 'auto' });
    expect(readGlassFlag('?gpu=webgl2', null)).toMatchObject({ enabled: true, backend: 'webgl2' });
  });

  it('survives storage that throws', () => {
    const broken = { getItem: () => { throw new Error('blocked'); } };
    expect(readGlassFlag('', broken).enabled).toBe(false);
  });
});
