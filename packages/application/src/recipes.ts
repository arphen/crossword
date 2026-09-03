/**
 * Day recipes: the Monday-through-Saturday construction contracts.
 *
 * Weekday labels are recipes, not a global difficulty ladder
 * (docs/plans/01 "Daily contracts"). Each recipe pins the grid format, the
 * template style, fill-quality thresholds, theme-lock policy, and clue
 * difficulty band. A day is playable only when its recipe's gates pass;
 * Sunday remains unavailable until a 21x21 template bank and its resource
 * gates exist, and the recipe says so honestly.
 */

export type DayOfWeek =
  | 'monday'
  | 'tuesday'
  | 'wednesday'
  | 'thursday'
  | 'friday'
  | 'saturday'
  | 'sunday';

export type DayRecipe = Readonly<{
  day: DayOfWeek;
  width: number;
  height: number;
  /** Curated templates this day may draw from, in preference order. */
  templateIds: readonly string[];
  /** Model-supplied theme locks required before fill (0 for early days). */
  themeLocks: 0 | 2 | 3;
  /** Fill-quality threshold the complete fill must meet. */
  qualityThreshold: number;
  /** Search budget per attempt (nodes). */
  maxNodes: number;
  /** Seeded restart attempts before the day is declared unavailable today. */
  maxRestarts: number;
  /** Clue mechanism mix by day, as target shares. */
  clueMix: Readonly<{
    direct: number;
    standard: number;
    oblique: number;
  }>;
  available: boolean;
  note: string;
}>;

const MONDAY: DayRecipe = {
  day: 'monday',
  width: 15,
  height: 15,
  templateIds: ['human-15x15', 'pinwheel-33', 'stagger-32'],
  themeLocks: 0,
  qualityThreshold: 0.55,
  maxNodes: 150_000,
  maxRestarts: 3,
  clueMix: { direct: 0.6, standard: 0.35, oblique: 0.05 },
  available: true,
  note: 'Clean fill, direct clues, generous crossings.'
};

const TUESDAY: DayRecipe = {
  ...MONDAY,
  day: 'tuesday',
  templateIds: ['human-15x15', 'pinwheel-33', 'stagger-32'],
  clueMix: { direct: 0.4, standard: 0.45, oblique: 0.15 },
  note: 'Broader vocabulary and light wordplay on the same calm topology.'
};

const WEDNESDAY: DayRecipe = {
  ...MONDAY,
  day: 'wednesday',
  templateIds: ['human-15x15', 'side-towers-31'],
  clueMix: { direct: 0.25, standard: 0.5, oblique: 0.25 },
  note: 'Balanced knowledge and word intelligence; medium grids.'
};

const THURSDAY: DayRecipe = {
  ...MONDAY,
  day: 'thursday',
  templateIds: ['human-15x15', 'side-towers-31'],
  themeLocks: 2,
  clueMix: { direct: 0.15, standard: 0.45, oblique: 0.4 },
  note: 'Gimmick day: model-supplied theme entries lock long slots.'
};

const FRIDAY: DayRecipe = {
  ...MONDAY,
  day: 'friday',
  templateIds: ['human-15x15', 'side-towers-31'],
  clueMix: { direct: 0.1, standard: 0.4, oblique: 0.45 },
  qualityThreshold: 0.62,
  note: 'Themeless-leaning: longer answers, oblique clueing, fair crossings.'
};

const SATURDAY: DayRecipe = {
  ...MONDAY,
  day: 'saturday',
  templateIds: ['human-15x15', 'side-towers-31'],
  qualityThreshold: 0.68,
  maxNodes: 250_000,
  clueMix: { direct: 0.1, standard: 0.35, oblique: 0.55 },
  note: 'The most oblique clueing and broadest vocabulary, with fair crossings.'
};

const SUNDAY: DayRecipe = {
  day: 'sunday',
  width: 21,
  height: 21,
  templateIds: [],
  themeLocks: 3,
  qualityThreshold: 0.6,
  maxNodes: 600_000,
  maxRestarts: 3,
  clueMix: { direct: 0.1, standard: 0.4, oblique: 0.5 },
  available: false,
  note: '21x21 format waits for its measured template bank and fill-latency gates (ADR 0003); the day stays honestly unavailable until then.'
};

export const DAY_RECIPES: Readonly<Record<DayOfWeek, DayRecipe>> = {
  monday: MONDAY,
  tuesday: TUESDAY,
  wednesday: WEDNESDAY,
  thursday: THURSDAY,
  friday: FRIDAY,
  saturday: SATURDAY,
  sunday: SUNDAY
};

export function dayRecipe(day: DayOfWeek): DayRecipe {
  return DAY_RECIPES[day];
}

export function parseDayOfWeek(value: string): DayOfWeek | undefined {
  return (Object.keys(DAY_RECIPES) as DayOfWeek[]).find((day) => day === value);
}

/** Days whose recipes are available AND have measured templates. */
export function constructableDays(): readonly DayOfWeek[] {
  return (Object.keys(DAY_RECIPES) as DayOfWeek[]).filter(
    (day) => DAY_RECIPES[day]!.available && DAY_RECIPES[day]!.templateIds.length > 0
  );
}
