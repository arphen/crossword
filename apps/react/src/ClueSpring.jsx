import React, { memo, useLayoutEffect, useRef, useState } from 'react';
import { coilPath, springEnds, springSegments, springTension } from './springGeometry';
import { chainAtRest, createChain, cubicBezier, pluck, stepChain } from './springMotion';
import { cssVars } from './cssVars';

/** One window event carries every knock and settle to the lanes, so the
 *  springs need no prop (and no render) to move:
 *  { kind: 'pluck', lane, number, impulse }   a knock on one chip
 *  { kind: 'jolt', lane, numbers }            a hard shudder, the coils flash
 *  { kind: 'release', lane, number }          a popped row's springs let go
 *  { kind: 'settle', rows: [{ lane, number, dx, dy, delay, duration }] }
 *                                             rows sliding into place (FLIP) */
export const SPRING_EVENT = 'cluespring:motion';
export function moveSprings(detail) {
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent(SPRING_EVENT, { detail }));
}
const SETTLE_EASE = cubicBezier(0.3, 1.45, 0.5, 1);
const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;

// The chips sit at different heights because every clue row sizes itself, so the
// springs are drawn from measured rectangles rather than from CSS arithmetic. The
// layer is absolutely positioned inside the scrolling list, which means it scrolls
// with the clues for free, and it is the list's last child so the ladder's
// :nth-child rules still count only clue rows.
function readCentres(list, chips) {
  const box = list.getBoundingClientRect();
  return chips.map((chip) => {
    const rect = chip.getBoundingClientRect();
    // A chip caught mid-sway (springMotion) is measured at rest.
    const sway = Number.parseFloat(chip.style.translate) || 0;
    return {
      x: rect.left + rect.width / 2 - sway - box.left + list.scrollLeft,
      y: rect.top + rect.height / 2 - box.top + list.scrollTop,
      hw: rect.width / 2,
      hh: rect.height / 2,
    };
  });
}

function readHeight(chips) {
  // From the last row, not scrollHeight: the layer itself counts toward the
  // list's scrollable height and would hold it open after a clue is solved.
  const last = chips.at(-1)?.parentElement;
  return last ? last.offsetTop + last.offsetHeight : 0;
}

function ClueSpring({ lane, numbers, ramp, states }) {
  const layer = useRef(null);
  const [drawn, setDrawn] = useState({ height: 0, segments: [] });
  // Kept in a ref so the observers always measure the latest props without being
  // torn down and rebuilt on every selection change.
  const latest = useRef({ lane, numbers, ramp, states });
  latest.current = { lane, numbers, ramp, states };
  const stamp = useRef('');
  // Chip geometry only moves when the listed rows change; a selection flip just
  // re-marks the same rows. Re-reading every chip rectangle forces a synchronous
  // layout on each direction switch, so the selection path reuses the cached
  // centres and only recomputes the (pure, cheap) segments. Anything that can
  // actually move rows for good — resizes, font loads — measures fresh (rows
  // bouncing into place after a check are drawn by the motion layer below),
  // and the row ResizeObservers below repair the cache if a highlight ever does
  // shift a row's height a frame later.
  const geometry = useRef({ key: '', centres: null, height: 0 });
  // The springs as one moving object (springMotion.js): knocks travel through
  // the chain and rows sliding into place carry their chips along. Drawn
  // straight onto the paths and chips each frame from the cached centres, so
  // the motion never reads layout and never renders React.
  const motion = useRef({ chain: createChain(), settles: new Map(), frame: 0, last: 0, chips: null, drawn: new Map(), remeasure: false });
  const paths = useRef(new Map());
  const segmentsRef = useRef(/** @type {any[]} */ ([]));
  segmentsRef.current = drawn.segments;

  const redraw = (fresh = false) => {
    const list = layer.current?.parentElement;
    if (!list) return;
    const { lane, numbers, ramp, states } = latest.current;
    const numbersKey = numbers.join(',');
    const chips = [...list.querySelectorAll(':scope > li > .clue-number')];
    if (chips.length !== numbers.length) {
      geometry.current = { key: '', centres: null, height: 0 };
      if (stamp.current === 'empty') return;
      stamp.current = 'empty';
      setDrawn({ height: 0, segments: [] });
      return;
    }
    let centres;
    let height;
    if (!fresh && geometry.current.key === numbersKey && geometry.current.centres?.length === chips.length) {
      ({ centres, height } = geometry.current);
    } else {
      centres = readCentres(list, chips);
      height = readHeight(chips);
      geometry.current = { key: numbersKey, centres, height };
    }
    const segments = springSegments({ chips: centres, numbers, ramp, states, lane });
    const signature = `${height}|${segments.map((segment) => `${segment.key}:${segment.d}:${segment.state}`).join('|')}`;
    if (signature === stamp.current) return;
    stamp.current = signature;
    setDrawn({ height, segments });
  };

  const restMotion = () => {
    const state = motion.current;
    state.frame = 0;
    state.chips?.forEach((chip) => { chip.style.translate = ''; });
    state.chips = null;
    for (const segment of segmentsRef.current) {
      if (state.drawn.has(segment.key)) paths.current.get(segment.key)?.setAttribute('d', segment.d);
    }
    state.drawn.clear();
    // A resize that arrived while rows were still sliding is measured now.
    if (state.remeasure) {
      state.remeasure = false;
      redraw(true);
    }
  };

  const animate = (time) => {
    const state = motion.current;
    const list = layer.current?.parentElement;
    const { numbers } = latest.current;
    const cached = geometry.current;
    if (!list || !cached.centres || cached.centres.length !== numbers.length) {
      restMotion();
      return;
    }
    const dt = state.last ? Math.min(0.05, (time - state.last) / 1000) : 1 / 60;
    state.last = time;
    stepChain(state.chain, numbers, dt);
    if (!state.chips || state.chips.length !== numbers.length || !state.chips[0]?.isConnected) {
      state.chips = [...list.querySelectorAll(':scope > li > .clue-number')];
    }
    // Rows still sliding into place, as the browser is drawing them.
    let settling = false;
    const now = performance.now();
    const offset = (number) => {
      const settle = state.settles.get(number);
      if (!settle) return [0, 0];
      const progress = (now - settle.start - settle.delay) / settle.duration;
      if (progress >= 1) {
        state.settles.delete(number);
        return [0, 0];
      }
      settling = true;
      const remaining = 1 - SETTLE_EASE(Math.max(0, progress));
      return [settle.dx * remaining, settle.dy * remaining];
    };
    const centres = numbers.map((number, index) => {
      const sway = state.chain.u.get(number) || 0;
      const [dx, dy] = offset(number);
      const chip = state.chips[index];
      const translate = Math.abs(sway) > 0.05 ? `${sway.toFixed(1)}px 0` : '';
      if (chip && chip.style.translate !== translate) chip.style.translate = translate;
      const centre = cached.centres[index];
      return { ...centre, x: centre.x + dx + sway, y: centre.y + dy, sway };
    });
    const index = new Map(numbers.map((number, position) => [number, position]));
    for (const segment of segmentsRef.current) {
      const element = paths.current.get(segment.key);
      const a = centres[index.get(segment.fromNumber)];
      const b = centres[index.get(segment.toNumber)];
      if (!element || !a || !b) continue;
      // Only springs that moved are redrawn; one at rest keeps its path.
      const signature = `${a.x.toFixed(1)},${a.y.toFixed(1)},${b.x.toFixed(1)},${b.y.toFixed(1)}`;
      const still = Math.abs(a.x - cached.centres[index.get(segment.fromNumber)].x) < 0.1
        && Math.abs(b.x - cached.centres[index.get(segment.toNumber)].x) < 0.1
        && Math.abs(a.y - cached.centres[index.get(segment.fromNumber)].y) < 0.1
        && Math.abs(b.y - cached.centres[index.get(segment.toNumber)].y) < 0.1;
      if (still) {
        if (state.drawn.has(segment.key)) {
          element.setAttribute('d', segment.d);
          state.drawn.delete(segment.key);
        }
        continue;
      }
      if (state.drawn.get(segment.key) === signature) continue;
      state.drawn.set(segment.key, signature);
      const shear = b.sway - a.sway;
      const tension = springTension(segment.steps);
      const ends = springEnds(a, b);
      element.setAttribute('d', coilPath(ends.from, ends.to, {
        ...tension,
        radius: tension.radius * (1 + Math.min(0.9, Math.abs(shear) / 14)),
        phase: shear * 0.24,
      }));
    }
    if (!settling && chainAtRest(state.chain)) {
      restMotion();
      return;
    }
    state.frame = requestAnimationFrame(animate);
  };

  const startMotion = () => {
    const state = motion.current;
    if (state.frame || typeof requestAnimationFrame === 'undefined' || reducedMotion()) return;
    state.last = 0;
    state.frame = requestAnimationFrame(animate);
  };

  useLayoutEffect(() => {
    const onMotion = (event) => {
      const detail = /** @type {CustomEvent} */ (event).detail || {};
      const { lane: own } = latest.current;
      if (detail.kind === 'settle') {
        const start = performance.now();
        let mine = false;
        for (const row of detail.rows || []) {
          if (row.lane !== own) continue;
          motion.current.settles.set(row.number, { ...row, start });
          mine = true;
        }
        if (mine) startMotion();
        return;
      }
      if (detail.lane !== own && detail.lane !== '*') return;
      if (detail.kind === 'release') {
        for (const segment of segmentsRef.current) {
          if (segment.fromNumber !== detail.number && segment.toNumber !== detail.number) continue;
          paths.current.get(segment.key)?.setAttribute('data-release', '');
        }
        return;
      }
      if (detail.kind === 'pluck') {
        if (!latest.current.numbers.includes(detail.number)) return;
        pluck(motion.current.chain, detail.number, detail.impulse);
        startMotion();
      } else if (detail.kind === 'jolt') {
        const hit = new Set(detail.numbers || []);
        latest.current.numbers.forEach((number, position) => {
          if (hit.size && !hit.has(number)) return;
          pluck(motion.current.chain, number, (position % 2 ? -1 : 1) * (detail.impulse || 260));
        });
        for (const segment of segmentsRef.current) {
          if (hit.size && !hit.has(segment.fromNumber) && !hit.has(segment.toNumber)) continue;
          const element = paths.current.get(segment.key);
          if (!element) continue;
          // Two names for one flash, so a second jolt restarts it without
          // forcing a layout to reset the first.
          const flash = element.getAttribute('data-jolt') === 'a' ? 'b' : 'a';
          element.setAttribute('data-jolt', flash);
          setTimeout(() => {
            if (element.getAttribute('data-jolt') === flash) element.removeAttribute('data-jolt');
          }, 760);
        }
        startMotion();
      }
    };
    window.addEventListener(SPRING_EVENT, onMotion);
    return () => {
      window.removeEventListener(SPRING_EVENT, onMotion);
      cancelAnimationFrame(motion.current.frame);
      restMotion();
    };
  }, []);

  // Picking a clue taps its chip, so the lane answers the hand that moves it.
  const activeNumber = numbers[states.indexOf('active')];
  const lastActive = useRef(activeNumber);
  useLayoutEffect(() => {
    if (activeNumber !== undefined && lastActive.current !== undefined && activeNumber !== lastActive.current) {
      pluck(motion.current.chain, activeNumber, 70);
      startMotion();
    }
    lastActive.current = activeNumber;
  }, [activeNumber]);

  // Every commit that changes which clues are listed, or how they are marked,
  // redraws synchronously so a solved clue never leaves a spring dangling for a
  // frame. Selection-only changes reuse the cached geometry (see above).
  const key = `${lane}|${numbers.join(',')}|${states.join(',')}`;
  useLayoutEffect(() => { redraw(false); }, [key, ramp]);

  useLayoutEffect(() => {
    const list = layer.current?.parentElement;
    if (!list || typeof ResizeObserver === 'undefined') return undefined;
    let frame = 0;
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        // Rows sliding into place are mid-transform: measuring them now
        // would capture where they are passing, not where they will rest.
        if (motion.current.settles.size) motion.current.remeasure = true;
        else redraw(true);
      });
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(list);
    list.querySelectorAll(':scope > li').forEach((row) => observer.observe(row));
    document.fonts?.ready?.then(schedule);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [numbers.join(',')]);

  return (
    <svg
      ref={layer}
      className="clue-spring"
      aria-hidden="true"
      focusable="false"
      data-lane={lane}
      style={{ height: drawn.height || undefined }}
    >
      <defs>
        {drawn.segments.map((segment) => (
          <linearGradient
            key={segment.key}
            id={`spring-${segment.key}`}
            gradientUnits="userSpaceOnUse"
            x1={segment.from.x}
            y1={segment.from.y}
            x2={segment.to.x}
            y2={segment.to.y}
          >
            <stop offset="0" className="spring-stop" style={cssVars({ '--clue-ramp': segment.fromRamp })} />
            <stop offset="1" className="spring-stop" style={cssVars({ '--clue-ramp': segment.toRamp })} />
          </linearGradient>
        ))}
      </defs>
      {drawn.segments.map((segment) => (
        <path
          key={segment.key}
          ref={(element) => {
            if (element) paths.current.set(segment.key, element);
            else paths.current.delete(segment.key);
          }}
          d={segment.d}
          className="spring-coil"
          data-state={segment.state || undefined}
          data-taut={segment.taut}
          stroke={`url(#spring-${segment.key})`}
        />
      ))}
    </svg>
  );
}

export default memo(
  ClueSpring,
  (a, b) =>
    a.lane === b.lane &&
    a.ramp === b.ramp &&
    a.numbers.join(',') === b.numbers.join(',') &&
    a.states.join(',') === b.states.join(','),
);
