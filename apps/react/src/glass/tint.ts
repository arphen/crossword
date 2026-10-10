// The board's own colour language, for the glass layer. The CSS board names
// every word with a hue on its lane's half of the wheel (vision.css sections
// 0, 1 and 11): Across on the warm arc, a step brighter; Down on the cool arc,
// a step quieter; each rank nudged along the screen's colour solid. The gel
// has to speak the same hues, so this reads the very tokens vision.css reads
// (plain numbers and hex colours on #app) and does the same arithmetic,
// ending in linear RGB for the shaders. Nothing here is a palette of its own.

export type Rgb = [number, number, number];

export interface GlassTokens {
  acrossArc: [number, number];
  downArc: [number, number];
  chroma: number;
  lightness: number;
  acrossContour: [number, number, number];
  downContour: [number, number, number];
  acrossLift: number;
  downDrop: number;
  highlightLift: number;
  highlightDrop: number;
  flameChroma: number;
  /** Shares of light, 0..1 (the CSS percentages). */
  spotAlpha: number;
  flameAlpha: number;
  cursorAlpha: number;
  laneRest: number;
  /** Linear RGB. */
  orange: Rgb;
  blue: Rgb;
  black: Rgb;
  cell: Rgb;
  shaded: Rgb;
  red: Rgb;
  green: Rgb;
  ink: Rgb;
  /** Number colours on (data-ramp) and board notches on (data-cues). */
  ramp: boolean;
  cues: boolean;
}

/** vision.css and desktop.css defaults, for anything a theme leaves unset. */
export const DEFAULT_TOKENS: GlassTokens = {
  acrossArc: [2, 142],
  downArc: [183, 323],
  chroma: 0.14,
  lightness: 0.82,
  acrossContour: [-0.115, 0, 0.105],
  downContour: [0.035, -0.24, 0.24],
  acrossLift: 0.07,
  downDrop: 0.07,
  highlightLift: 0.11,
  highlightDrop: 0.1,
  flameChroma: 1.75,
  spotAlpha: 0.16,
  flameAlpha: 0.34,
  cursorAlpha: 0.46,
  laneRest: 0.3,
  orange: hexToLinear('#ffad32'),
  blue: hexToLinear('#8dc7ff'),
  black: hexToLinear('#0d1218'),
  cell: hexToLinear('#343a45'),
  shaded: hexToLinear('#3c4650'),
  red: hexToLinear('#ff9c9c'),
  green: hexToLinear('#8fe4b1'),
  ink: hexToLinear('#f2f2f6'),
  ramp: true,
  cues: true,
};

function srgbToLinear(channel: number): number {
  return channel <= 0.04045 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);
}

/** A CSS hex or rgb() colour in linear RGB, or null if it is neither. */
export function parseColor(value: string): Rgb | null {
  const text = value.trim().toLowerCase();
  const hex = /^#([0-9a-f]{3,8})$/.exec(text);
  if (hex) {
    let digits = hex[1];
    if (digits.length === 3 || digits.length === 4) digits = [...digits].map((d) => d + d).join('');
    if (digits.length !== 6 && digits.length !== 8) return null;
    return [0, 2, 4].map((at) => srgbToLinear(Number.parseInt(digits.slice(at, at + 2), 16) / 255)) as Rgb;
  }
  const rgb = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/.exec(text);
  if (rgb) return [rgb[1], rgb[2], rgb[3]].map((v) => srgbToLinear(Number(v) / 255)) as Rgb;
  return null;
}

export function hexToLinear(hex: string): Rgb {
  return parseColor(hex) ?? [0, 0, 0];
}

/** OKLCH (lightness 0..1, chroma, hue in degrees) to linear sRGB, clipped. */
export function oklchToLinear(lightness: number, chroma: number, hue: number): Rgb {
  const radians = (hue * Math.PI) / 180;
  const a = chroma * Math.cos(radians);
  const b = chroma * Math.sin(radians);
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (lightness - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const clip = (v: number) => Math.min(1, Math.max(0, v));
  return [
    clip(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    clip(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    clip(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ];
}

function contour(c: [number, number, number], rank: number): number {
  return c[0] + c[1] * rank + c[2] * rank * rank;
}

/** A word's colour on its lane's arc, as the board's spills and gate ticks
 *  wear it (--spot-acolor / --spot-dcolor, --gate-across-tint / -down-tint). */
export function laneTint(tokens: GlassTokens, lane: 'across' | 'down', rank: number): Rgb {
  const across = lane === 'across';
  const [start, end] = across ? tokens.acrossArc : tokens.downArc;
  const lightness = across
    ? tokens.lightness + tokens.acrossLift + contour(tokens.acrossContour, rank)
    : tokens.lightness - tokens.downDrop + contour(tokens.downContour, rank);
  return oklchToLinear(lightness, tokens.chroma, start + rank * (end - start));
}

/** The active word's flame (--active-clue-flame): its hue on the direction
 *  being solved, at the highlight's value and the flame's chroma. */
export function flameTint(tokens: GlassTokens, direction: 'across' | 'down', rank: number): Rgb {
  const across = direction === 'across';
  const [start, end] = across ? tokens.acrossArc : tokens.downArc;
  const lightness = across
    ? tokens.lightness + tokens.highlightLift + contour(tokens.acrossContour, rank)
    : tokens.lightness - tokens.highlightDrop + contour(tokens.downContour, rank);
  return oklchToLinear(lightness, tokens.chroma * tokens.flameChroma, start + rank * (end - start));
}

/** The board's charge (vision.css section 11): light gathers into the notches
 *  still open as words are solved, dims with a low score, warms with a combo. */
export function boardCharge(remaining: number, libido: number, heat: number): number {
  const raw = libido * Math.pow(Math.max(remaining, 0.05), -0.5) * (1 + 0.45 * heat);
  return Math.min(2.6, Math.max(0.18, raw));
}

function share(value: string, fallback: number): number {
  const text = value.trim();
  if (!text) return fallback;
  const number = Number.parseFloat(text);
  if (!Number.isFinite(number)) return fallback;
  return text.endsWith('%') ? number / 100 : number;
}

/** Read the tokens off the board's root as the cascade resolves them there
 *  (theme, vibrance and low-bloom tiers included). */
export function readTokens(root: Element): GlassTokens {
  const style = getComputedStyle(root);
  const read = (name: string) => style.getPropertyValue(name);
  const n = (name: string, fallback: number) => share(read(name), fallback);
  const color = (name: string, fallback: Rgb) => parseColor(read(name)) ?? fallback;
  const d = DEFAULT_TOKENS;
  return {
    acrossArc: [n('--across-arc-start', d.acrossArc[0]), n('--across-arc-end', d.acrossArc[1])],
    downArc: [n('--down-arc-start', d.downArc[0]), n('--down-arc-end', d.downArc[1])],
    chroma: n('--ramp-chroma', d.chroma),
    lightness: n('--ramp-lightness', d.lightness),
    acrossContour: [n('--across-l0', d.acrossContour[0]), n('--across-l1', d.acrossContour[1]), n('--across-l2', d.acrossContour[2])],
    downContour: [n('--down-l0', d.downContour[0]), n('--down-l1', d.downContour[1]), n('--down-l2', d.downContour[2])],
    acrossLift: n('--across-lift', d.acrossLift),
    downDrop: n('--down-drop', d.downDrop),
    highlightLift: n('--highlight-lift', d.highlightLift),
    highlightDrop: n('--highlight-drop', d.highlightDrop),
    flameChroma: n('--flame-chroma', d.flameChroma),
    spotAlpha: n('--spot-alpha', d.spotAlpha),
    flameAlpha: n('--flame-alpha', d.flameAlpha),
    cursorAlpha: n('--cursor-alpha', d.cursorAlpha),
    laneRest: n('--lane-rest', d.laneRest),
    orange: color('--react-orange', d.orange),
    blue: color('--react-blue', d.blue),
    black: color('--board-black', d.black),
    cell: color('--react-cell', d.cell),
    shaded: color('--cell-shaded', d.shaded),
    red: color('--react-red', d.red),
    green: color('--react-green', d.green),
    ink: color('--react-ink', d.ink),
    ramp: root.getAttribute('data-ramp') !== 'off',
    cues: root.getAttribute('data-cues') !== 'off',
  };
}

/** The numbers the root publishes inline for the board's light. */
export function readRootLight(root: HTMLElement): { charge: number; activeRank: number | null } {
  const style = root.style;
  const num = (name: string, fallback: number) => {
    const value = Number.parseFloat(style.getPropertyValue(name));
    return Number.isFinite(value) ? value : fallback;
  };
  const active = Number.parseFloat(style.getPropertyValue('--active-clue-ramp'));
  return {
    charge: boardCharge(num('--remaining', 1), num('--libido', 1), num('--combo-heat', 0)),
    activeRank: Number.isFinite(active) ? active : null,
  };
}
