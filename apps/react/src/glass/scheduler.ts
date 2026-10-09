// When the glass layer draws. Nothing per frame unless something moves: an
// event (a key, the cursor, a check) asks for frames until its animation has
// played out; between events the room breathes at most 30 times a second, and
// only while the reader is around. The tab hidden, or reduced motion, means no
// breathing at all. The render scale follows the frame budget.

export interface SchedulerOptions {
  /** Ambient frames per second while idle (0 for none). */
  ambientFps: number;
  /** Seconds after the last interaction that the room keeps breathing. */
  ambientFor: number;
}

export const DEFAULT_SCHEDULE: SchedulerOptions = { ambientFps: 30, ambientFor: 90 };

/**
 * Whether a frame is due at time `now` (seconds). `animateUntil` is the end of
 * the latest event animation, `lastFrame` the time of the last frame drawn,
 * `lastInput` the last interaction; `ambient` is false when the reader asked
 * for reduced motion or the tab is hidden.
 */
export function frameDue(
  now: number,
  state: { animateUntil: number; lastFrame: number; lastInput: number; ambient: boolean },
  options: SchedulerOptions = DEFAULT_SCHEDULE,
): boolean {
  if (now < state.animateUntil) return true;
  if (!state.ambient || options.ambientFps <= 0) return false;
  if (now - state.lastInput > options.ambientFor) return false;
  return now - state.lastFrame >= 1 / options.ambientFps - 0.002;
}

/** Whether the loop should keep running at all (so it can park when not). */
export function loopNeeded(
  now: number,
  state: { animateUntil: number; lastInput: number; ambient: boolean },
  options: SchedulerOptions = DEFAULT_SCHEDULE,
): boolean {
  return now < state.animateUntil || (state.ambient && options.ambientFps > 0 && now - state.lastInput <= options.ambientFor);
}

/**
 * Dynamic resolution: the next render scale from the last frame's cost.
 * Over budget, step down quickly; comfortably under for `calmNeeded` samples
 * in a row, creep back up. Steps are coarse so the render targets are not
 * rebuilt every frame.
 */
export function nextRenderScale(
  scale: number,
  frameMs: number,
  budgetMs: number,
  calmFrames: number,
  limits = { min: 0.5, max: 1, calmNeeded: 90 },
): { scale: number; calmFrames: number } {
  if (!(frameMs > 0)) return { scale, calmFrames };
  if (frameMs > budgetMs * 1.2) {
    return { scale: Math.max(limits.min, Math.round((scale - 0.1) * 100) / 100), calmFrames: 0 };
  }
  if (frameMs < budgetMs * 0.55) {
    const calm = calmFrames + 1;
    if (calm >= limits.calmNeeded && scale < limits.max) return { scale: Math.min(limits.max, Math.round((scale + 0.05) * 100) / 100), calmFrames: 0 };
    return { scale, calmFrames: calm };
  }
  return { scale, calmFrames: 0 };
}
