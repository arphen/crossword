// view-settings.js — the whole contract between JS and CSS.
// Three tiers, smallest surface first. Everything is presentation only,
// persisted locally, and published as data-* attributes on the root element.
// JS never sets colours, sizes or shadows; it only names a state.

export const VIEW_SETTINGS_KEY = 'myapp.view.v1';

export const TIERS = [
  { key: 'mini', title: 'Mini', hint: 'Comfort', rows: [
    { key: 'luma', label: 'Brightness', options: ['standard', 'dim', 'veil'] },
    { key: 'scale', label: 'Size', options: ['compact', 'normal', 'full'] },
  ] },
  { key: 'micro', title: 'Micro', hint: 'Reading aids', rows: [
    { key: 'ramp', label: 'Item colours', options: [false, true] },
    { key: 'vibrance', label: 'Colour intensity', options: ['soft', 'vivid', 'bold'] },
  ] },
  { key: 'nano', title: 'Nano', hint: 'Fine cues', rows: [
    { key: 'cues', label: 'Edge cues', options: [false, true] },
    { key: 'glyph', label: 'Letter weight', options: ['regular', 'firm'] },
  ] },
];

export const VIEW_DEFAULTS = {
  luma: 'standard', scale: 'normal', ramp: true, vibrance: 'vivid',
  cues: true, glyph: 'regular',
};

const OPTIONS = Object.fromEntries(
  TIERS.flatMap((tier) => tier.rows).map((row) => [row.key, row.options]),
);

// Never trust storage: unknown values fall back to the default.
export function normalizeViewSettings(value, defaults = VIEW_DEFAULTS) {
  const stored = value && typeof value === 'object' ? value : {};
  return Object.fromEntries(
    Object.keys(defaults).map((key) => [
      key,
      OPTIONS[key].includes(stored[key]) ? stored[key] : defaults[key],
    ]),
  );
}

// A display that reports reduced contrast or transparency usually blooms or
// washes out: pick the dim tier on a first visit. A stored choice always wins.
export function prefersLowBloom(media = globalThis.matchMedia?.bind(globalThis)) {
  if (typeof media !== 'function') return false;
  return ['(prefers-contrast: less)', '(prefers-reduced-transparency: reduce)']
    .some((query) => media(query)?.matches === true);
}

export function readViewSettings({ storage = globalThis.localStorage, media } = {}) {
  const defaults = { ...VIEW_DEFAULTS, luma: prefersLowBloom(media) ? 'dim' : 'standard' };
  let stored = null;
  try { stored = JSON.parse(storage?.getItem?.(VIEW_SETTINGS_KEY) ?? 'null'); } catch { stored = null; }
  return normalizeViewSettings(stored, defaults);
}

export function writeViewSettings(settings, { storage = globalThis.localStorage } = {}) {
  try { storage?.setItem?.(VIEW_SETTINGS_KEY, JSON.stringify(settings)); } catch { /* private mode must not break the app */ }
}

// booleans become 'on' | 'off' so CSS can write [data-ramp='off'].
export function viewAttributes(settings) {
  return Object.fromEntries(
    Object.entries(settings).map(([key, value]) => [
      `data-${key}`,
      typeof value === 'boolean' ? (value ? 'on' : 'off') : value,
    ]),
  );
}

export function applyViewSettings(root, settings) {
  for (const [name, value] of Object.entries(viewAttributes(settings))) root.setAttribute(name, value);
}

// The rank -> colour mapping: rank, not value, so any list length spreads evenly
// across the whole arc. Items that share an identity (the same number in two
// lists) share one rank, so a colour learned in one place is found in the other.
export function createRamp(ids) {
  const unique = [...new Set(ids)].sort((a, b) => a - b);
  const span = unique.length > 1 ? unique.length - 1 : 1;
  return new Map(unique.map((id, rank) => [id, Math.round((rank / span) * 1000) / 1000]));
}
