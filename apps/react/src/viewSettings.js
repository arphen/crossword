// Reader-adjustable view settings for the desktop board. Three tiers, smallest
// surface first: mini (comfort: brightness and board size), micro (reading aids:
// rails, number colours, letter-track grouping) and nano (the fine board cues:
// square notches and letter weight). Everything is presentation only, persisted
// locally, and published as data-* attributes so CSS owns the appearance.

export const VIEW_SETTINGS_KEY = 'crossword.view.v1';

export const LUMA_LEVELS = ['standard', 'dim', 'veil'];
export const SCALE_LEVELS = ['compact', 'normal', 'full'];
export const GROUPING_MODES = ['auto', 'five', 'none'];
export const GLYPH_LEVELS = ['regular', 'firm'];

export const VIEW_DEFAULTS = {
  luma: 'standard',
  scale: 'normal',
  rail: true,
  ramp: true,
  grouping: 'auto',
  cues: true,
  glyph: 'regular',
};

// Displays that bloom or wash out are usually reported as reduced contrast or
// reduced transparency rather than as low brightness, so those hints pick the
// dim tier on a first visit. The reader can still override it in the cluster.
export function prefersLowBloom(media) {
  if (typeof media !== 'function') return false;
  return [
    '(prefers-contrast: less)',
    '(prefers-reduced-transparency: reduce)',
  ].some((query) => media(query)?.matches === true);
}

function pick(value, options, fallback) {
  return options.includes(value) ? value : fallback;
}

function boolean(value, fallback) {
  return value === true || value === false ? value : fallback;
}

export function normalizeViewSettings(value, defaults = VIEW_DEFAULTS) {
  const stored = value && typeof value === 'object' ? value : {};
  return {
    luma: pick(stored.luma, LUMA_LEVELS, defaults.luma),
    scale: pick(stored.scale, SCALE_LEVELS, defaults.scale),
    rail: boolean(stored.rail, defaults.rail),
    ramp: boolean(stored.ramp, defaults.ramp),
    grouping: pick(stored.grouping, GROUPING_MODES, defaults.grouping),
    cues: boolean(stored.cues, defaults.cues),
    glyph: pick(stored.glyph, GLYPH_LEVELS, defaults.glyph),
  };
}

/** Where the settings live and which display hints to consult. Both are optional:
 *  a server render has neither, and private browsing can refuse to write.
 * @typedef {object} ViewSettingsOptions
 * @property {{ getItem?: (key: string) => string | null, setItem?: (key: string, value: string) => void } | null} [storage]
 * @property {((query: string) => { matches?: boolean } | null) | null} [media]
 */

/** Read persisted settings. A stored value always beats the media hints; an
 *  absent one falls back to the low-bloom tier when the display asks for it.
 * @param {ViewSettingsOptions} [options]
 */
export function readViewSettings({ storage, media } = {}) {
  const defaults = {
    ...VIEW_DEFAULTS,
    luma: prefersLowBloom(media) ? 'dim' : VIEW_DEFAULTS.luma,
  };
  let stored = null;
  try {
    stored = JSON.parse(storage?.getItem?.(VIEW_SETTINGS_KEY) ?? 'null');
  } catch {
    stored = null;
  }
  return normalizeViewSettings(stored, defaults);
}

export function writeViewSettings(
  settings,
  { storage } = /** @type {ViewSettingsOptions} */ ({}),
) {
  try {
    storage?.setItem?.(VIEW_SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Private mode or a full quota must not break the board.
  }
}

/** The attributes the board root carries; every cue and tier in the stylesheets
 *  keys off these, so this is the whole contract between JS and CSS. */
export function viewAttributes(settings) {
  return {
    'data-luma': settings.luma,
    'data-scale': settings.scale,
    'data-rail': settings.rail ? 'on' : 'off',
    'data-ramp': settings.ramp ? 'on' : 'off',
    'data-grouping': settings.grouping,
    'data-cues': settings.cues ? 'on' : 'off',
    'data-glyph': settings.glyph,
  };
}
