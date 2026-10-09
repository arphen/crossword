// The light each weekday is lit by. Every puzzle day has its own voice, kept
// inside the app's language: a dark obsidian base, orange for Across, blue for
// Down, green and red for the check. What changes from day to day is the
// room: the hue of the aurora behind the glass, the tint of the glass itself
// and the warmth of the key light. Monday is a clear dawn, Saturday a deep
// night; Sunday, the big puzzle, is the warmest. Colours are linear RGB, ready
// for the shaders (HDR values above 1 are allowed for light).

export type Rgb = [number, number, number];

export interface GlassPalette {
  /** The two ends of the aurora behind the glass. */
  skyLow: Rgb;
  skyHigh: Rgb;
  /** Caustic light swimming through the aurora. */
  caustic: Rgb;
  /** The glass body. */
  glass: Rgb;
  /** Black squares: polished obsidian. */
  obsidian: Rgb;
  /** Shaded squares: tinted glass. */
  shade: Rgb;
  /** Circled squares: the luminous ring. */
  ring: Rgb;
  /** Direction light: Across and Down. */
  across: Rgb;
  down: Rgb;
  /** The check. */
  correct: Rgb;
  wrong: Rgb;
  /** The key light. */
  key: Rgb;
}

const srgb = (hex: string): Rgb => {
  const value = Number.parseInt(hex.replace('#', ''), 16);
  const channel = (shift: number) => {
    const c = ((value >> shift) & 255) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return [channel(16), channel(8), channel(0)];
};

const scale = (rgb: Rgb, k: number): Rgb => [rgb[0] * k, rgb[1] * k, rgb[2] * k];

// The constant voice: direction and verdict colours from the app's tokens
// (desktop.css), lifted a little so they read as light rather than paint.
const ACROSS = scale(srgb('#ffad32'), 1.15);
const DOWN = scale(srgb('#8dc7ff'), 1.1);
const CORRECT = scale(srgb('#8fe4b1'), 1.05);
const WRONG = scale(srgb('#ff7b7b'), 1.1);

interface Day {
  low: string;
  high: string;
  caustic: string;
  glass: string;
  key: string;
}

// Sunday first, as Date.getDay() counts.
const DAYS: Day[] = [
  { low: '#140b07', high: '#5a2a14', caustic: '#ffb46a', glass: '#2a2522', key: '#ffe2bf' }, // Sunday: ember
  { low: '#07101a', high: '#1d4a66', caustic: '#9fe6ff', glass: '#1e2a33', key: '#e8f6ff' }, // Monday: clear dawn
  { low: '#081310', high: '#1f5a48', caustic: '#9fffd6', glass: '#1d2c28', key: '#eafff6' }, // Tuesday: sea glass
  { low: '#0b0b18', high: '#33307a', caustic: '#b9b4ff', glass: '#23233a', key: '#efeeff' }, // Wednesday: indigo
  { low: '#140912', high: '#5c2350', caustic: '#ff9be0', glass: '#2c1f2a', key: '#ffe9f7' }, // Thursday: orchid
  { low: '#111007', high: '#5a4a16', caustic: '#ffe08a', glass: '#2b2820', key: '#fff4d8' }, // Friday: brass
  { low: '#05070c', high: '#16203d', caustic: '#7f9cff', glass: '#161b26', key: '#dfe6ff' }, // Saturday: deep night
];

const DAY_NAMES = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];

/** Day index (0 Sunday … 6 Saturday) from a day name; Monday when unknown. */
export function weekdayIndex(name: string | null | undefined): number {
  const index = DAY_NAMES.indexOf(String(name || '').trim().toLowerCase());
  return index >= 0 ? index : 1;
}

/** The palette for a weekday, on paper (`light`) or at night. */
export function glassPalette(weekday: number, light = false): GlassPalette {
  const day = DAYS[((weekday % 7) + 7) % 7] ?? DAYS[1];
  if (!light) {
    return {
      skyLow: srgb(day.low),
      skyHigh: srgb(day.high),
      caustic: scale(srgb(day.caustic), 0.9),
      glass: srgb(day.glass),
      obsidian: srgb('#05070a'),
      shade: scale(srgb(day.caustic), 0.35),
      ring: scale(srgb(day.caustic), 1.6),
      across: ACROSS,
      down: DOWN,
      correct: CORRECT,
      wrong: WRONG,
      key: scale(srgb(day.key), 1.4),
    };
  }
  // Paper: the room is a pale wash of the day's hue, the glass is milky, and
  // black squares are slate. The direction and verdict lights deepen so they
  // still read against white.
  const mix = (a: Rgb, b: Rgb, t: number): Rgb => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
  const paper = srgb('#f3f3ef');
  return {
    skyLow: mix(paper, srgb(day.high), 0.12),
    skyHigh: mix(paper, srgb(day.caustic), 0.32),
    caustic: scale(srgb(day.caustic), 0.6),
    glass: mix(srgb('#ffffff'), srgb(day.glass), 0.08),
    obsidian: srgb('#2c3834'),
    shade: mix(srgb('#c9d3cc'), srgb(day.caustic), 0.25),
    ring: scale(srgb(day.high), 1.4),
    across: srgb('#d9740a'),
    down: srgb('#2f7fc8'),
    correct: srgb('#2e9d5e'),
    wrong: srgb('#d23b45'),
    key: srgb('#ffffff'),
  };
}

/** The palette as a flat list of vec4s (rgb, 1), in a fixed order the shaders
 *  read: skyLow, skyHigh, caustic, glass, obsidian, shade, ring, across, down,
 *  correct, wrong, key. */
export const PALETTE_SLOTS = 12;
export function paletteFloats(palette: GlassPalette, out = new Float32Array(PALETTE_SLOTS * 4)): Float32Array {
  const order: Rgb[] = [
    palette.skyLow,
    palette.skyHigh,
    palette.caustic,
    palette.glass,
    palette.obsidian,
    palette.shade,
    palette.ring,
    palette.across,
    palette.down,
    palette.correct,
    palette.wrong,
    palette.key,
  ];
  order.forEach((rgb, index) => {
    out[index * 4] = rgb[0];
    out[index * 4 + 1] = rgb[1];
    out[index * 4 + 2] = rgb[2];
    out[index * 4 + 3] = 1;
  });
  return out;
}
