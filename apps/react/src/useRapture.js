import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { celebrationTier, countMistakes, raptureNote, sparkSpecs } from './celebration';

// The rows a check solves do not vanish: they are held on the ladder for a beat so
// they can turn green, rise and dissolve, and only then leave. When they go, every
// row below slides and bounces into its new place (FLIP, on transform and opacity),
// and the springs are re-measured each frame so they stay attached to their chips.
// Two phases: `holding` while the rows are still listed, then the moment itself
// (note, wash, confetti) runs on until it has finished and is dropped.

const ASCEND_MS = 1000;
const STAGGER_MS = 45;
const STAGGER_STEPS = 18;
const SETTLE_MS = 700;
const MOMENT_MS = 3400;
export const RETRACE_EVENT = 'cluespring:retrace';

const reducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;

export function useRapture(app) {
  const [active, setActive] = useState(null);
  const timers = useRef([]);
  const flip = useRef(null);
  const frame = useRef({ id: 0, until: 0 });

  const retrace = useCallback((ms) => {
    const state = frame.current;
    state.until = Math.max(state.until, performance.now() + ms);
    if (state.id) return;
    const tick = () => {
      window.dispatchEvent(new Event(RETRACE_EVENT));
      state.id = performance.now() < state.until ? requestAnimationFrame(tick) : 0;
    };
    state.id = requestAnimationFrame(tick);
  }, []);

  useEffect(() => () => {
    timers.current.forEach(clearTimeout);
    cancelAnimationFrame(frame.current.id);
  }, []);

  // A new puzzle replaces the list the held rows belonged to.
  const crossword = app.crossword;
  useEffect(() => {
    timers.current.forEach(clearTimeout);
    setActive(null);
  }, [crossword]);

  const celebrate = useCallback((before) => {
    const gained = [...app.completedWords].filter((text) => !before.has(text));
    const mistakes = countMistakes(app.crossword, app.grid);
    const tier = celebrationTier({ solved: gained.length, mistakes });
    if (tier === 0 || reducedMotion()) return;

    const order = new Map();
    app.crossword
      .filter((entry) => gained.includes(entry.clue_text))
      .sort((a, b) => a.clue_number - b.clue_number)
      .forEach((entry) => {
        if (!order.has(entry.clue_text)) order.set(entry.clue_text, order.size);
      });
    const seed = gained.reduce((sum, text) => sum + text.length, 0) + gained.length;
    const sparks = sparkSpecs({ tier, solved: gained.length, seed });
    const longest = Math.min(order.size - 1, STAGGER_STEPS) * STAGGER_MS;
    const hold = ASCEND_MS + longest + 60;

    setActive({
      id: Date.now(),
      holding: true,
      tier,
      order,
      sparks,
      note:
        tier >= 3 && app.completedWords.size < app.crossword.length
          ? raptureNote({ solved: gained.length, mistakes })
          : null,
      mistakes,
      step: STAGGER_MS,
      maxStep: STAGGER_STEPS,
    });
    retrace(hold + SETTLE_MS + 200);

    timers.current.forEach(clearTimeout);
    timers.current = [
      setTimeout(() => {
        // Positions as they are about to change, read while the held rows are
        // still in the list.
        flip.current = new Map(
          [...document.querySelectorAll('#app #across > li, #app #down > li')]
            .filter((row) => !row.hasAttribute('data-rapture'))
            .map((row) => [row, row.getBoundingClientRect()]),
        );
        setActive((current) => (current ? { ...current, holding: false } : current));
      }, hold),
      setTimeout(() => setActive(null), Math.max(hold + 200, MOMENT_MS)),
    ];
  }, [app, retrace]);

  // After the held rows are gone: slide everything that remains into place.
  const holding = Boolean(active?.holding);
  useLayoutEffect(() => {
    const before = flip.current;
    if (!before || holding) return;
    flip.current = null;
    if (typeof Element.prototype.animate !== 'function') return;
    let index = 0;
    before.forEach((from, row) => {
      if (!row.isConnected) return;
      const to = row.getBoundingClientRect();
      const dx = from.left - to.left;
      const dy = from.top - to.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
      row.animate(
        [
          { transform: `translate(${dx}px, ${dy}px)`, opacity: 0.35 },
          { transform: 'translate(0, 0)', opacity: 1 },
        ],
        {
          duration: SETTLE_MS,
          delay: Math.min(index, 14) * 14,
          easing: 'cubic-bezier(0.3, 1.45, 0.5, 1)',
          fill: 'backwards',
        },
      );
      index += 1;
    });
  }, [holding]);

  return { active, celebrate };
}
