// Whether the glass layer is asked for, and whether its debug overlay is.
// Default off: `?gpu=1` turns it on for a visit, `?gpu=0` turns it off, and a
// stored override (`localStorage['crossword.gpu']` = '1' or '0') wins over the
// default for every visit until it is removed. Pure apart from the inputs it is
// handed, so the rules are testable without a browser.

export const GLASS_STORAGE_KEY = 'crossword.gpu';

export interface GlassFlag {
  /** The layer should be attempted. */
  enabled: boolean;
  /** Show frame time, GPU time and the active backend. */
  debug: boolean;
  /** Force a backend: 'webgl2' skips WebGPU (testing the fallback). */
  backend: 'auto' | 'webgl2';
}

interface StorageLike {
  getItem(key: string): string | null;
}

const truthy = (value: string | null) => value !== null && value !== '0' && value.toLowerCase() !== 'off' && value.toLowerCase() !== 'false';

export function readGlassFlag(search: string, storage: StorageLike | null): GlassFlag {
  const params = new URLSearchParams(search || '');
  let stored: string | null = null;
  try {
    stored = storage?.getItem(GLASS_STORAGE_KEY) ?? null;
  } catch {
    stored = null;
  }
  const query = params.get('gpu');
  // The address bar wins for this visit; the stored override decides otherwise.
  const enabled = query !== null ? truthy(query) || query === '' : stored !== null ? truthy(stored) : false;
  const debug = params.has('gpu-debug') && params.get('gpu-debug') !== '0';
  const backend = query === 'webgl2' || stored === 'webgl2' ? 'webgl2' : 'auto';
  return { enabled: enabled || debug, debug, backend };
}
