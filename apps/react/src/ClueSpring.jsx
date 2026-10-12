import React, { memo, useLayoutEffect, useRef } from 'react';
import { coilPath, springEnds, springSegments, springTension } from './springGeometry';
import { chainAtRest, createChain, cubicBezier, pluck, stepChain } from './springMotion';
import { cssRgb, laneTint, readTokens } from './glass/tint';

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

// How long the coils' own moments last (ms), as the stylesheet once timed
// them: a new spring fading in, a jolt's flash, a popped row letting go.
const FADE_IN = 240;
const JOLT = 760;
const RELEASE_DELAY = 120;
const RELEASE = 820;
// The lane light's cross-fade, eased here on the canvas (the stylesheet steps it).
const LANE_FADE = 280;
const easeOut = (t) => 1 - (1 - t) * (1 - t);
const easeIn = (t) => t * t;
const clamp01 = (t) => Math.min(1, Math.max(0, t));

// The chips sit at different heights because every clue row sizes itself, so the
// springs are drawn from measured rectangles rather than from CSS arithmetic.
// They are painted on a canvas the size of the lane's visible area, held in
// place over the scroll with a transform: a coil moving every frame is a
// redraw of pixels, never a change to the document, so the springs can ring
// through a whole check without the page restyling or laying out once. The
// canvas is the list's last child so the ladder's :nth-child rules still count
// only clue rows.
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

/** What the stylesheet says about the springs, read once per change of theme
 *  or setting: the clue hues (tint.ts, as vision.css computes them), the flash
 *  colours, and the dimmer tiers. */
function readInk(root) {
  const tokens = readTokens(root);
  const probe = document.createElement('span');
  probe.style.display = 'none';
  root.appendChild(probe);
  const resolve = (value, fallback) => {
    probe.style.color = value;
    return getComputedStyle(probe).color || fallback;
  };
  const ink = {
    tokens,
    jolt: resolve('var(--combo-break, #ff9c9c)', '#ff9c9c'),
    release: resolve('var(--rapture-green, #8fe4b1)', '#8fe4b1'),
    dim: root.matches?.("[data-luma='dim'], [data-luma='veil']") ?? false,
    direction: root.getAttribute('data-direction') === 'down' ? 'down' : 'across',
    tints: new Map(),
  };
  probe.remove();
  return ink;
}

function ClueSpring({ lane, numbers, ramp, states }) {
  const layer = useRef(null);
  // Kept in a ref so the observers always measure the latest props without being
  // torn down and rebuilt on every selection change.
  const latest = useRef({ lane, numbers, ramp, states });
  latest.current = { lane, numbers, ramp, states };
  // Chip geometry only moves when the listed rows change; a selection flip just
  // re-marks the same rows. Re-reading every chip rectangle forces a synchronous
  // layout on each direction switch, so the selection path reuses the cached
  // centres and only recomputes the (pure, cheap) segments. Anything that can
  // actually move rows for good — resizes, font loads — measures fresh (rows
  // bouncing into place after a check are drawn by the motion layer below),
  // and the row ResizeObservers below repair the cache if a highlight ever does
  // shift a row's height a frame later.
  const geometry = useRef({ key: '', centres: null });
  // The springs as one moving object (springMotion.js): knocks travel through
  // the chain and rows sliding into place carry their chips along. Each frame
  // the moving coils' paths are recomputed from the cached centres and
  // painted, so the motion never reads layout and never renders React.
  const motion = useRef({ chain: createChain(), settles: new Map(), frame: 0, last: 0, chips: null, moving: false, remeasure: false });
  const segmentsRef = useRef(/** @type {any[]} */ ([]));
  // Per coil: the path it is drawn with while it moves, and when its moments
  // began (born, jolted, released).
  const coils = useRef({ moved: new Map(), born: new Map(), jolted: new Map(), released: new Map(), shapes: new Map(), gradients: new Map() });
  const ink = useRef(/** @type {any} */ (null));
  const laneLight = useRef({ from: 1, to: 1, at: 0 });
  // The lane's visible area, kept from its ResizeObserver and scroll events so
  // painting never reads layout (a read inside a commit would force the whole
  // page's style).
  const view = useRef({ width: 0, height: 0, top: 0 });

  const liveFor = (now) => {
    const light = laneLight.current;
    return light.from + (light.to - light.from) * easeOut(clamp01((now - light.at) / LANE_FADE));
  };

  const tintFor = (rank) => {
    const current = ink.current;
    const key = rank ?? 0;
    let tint = current.tints.get(key);
    if (!tint) {
      tint = cssRgb(laneTint(current.tokens, latest.current.lane, key));
      current.tints.set(key, tint);
    }
    return tint;
  };

  const shapeOf = (d) => {
    const shapes = coils.current.shapes;
    let shape = shapes.get(d);
    if (!shape) {
      if (shapes.size > 600) shapes.clear();
      shape = new Path2D(d);
      shapes.set(d, shape);
    }
    return shape;
  };

  /** Paint every visible coil; returns whether a coil is still mid-moment. */
  const paint = () => {
    const canvas = layer.current;
    const list = canvas?.parentElement;
    const context = canvas?.getContext?.('2d');
    if (!canvas || !list || !context) return false;
    const root = list.closest('#app') ?? document.documentElement;
    if (!ink.current) {
      ink.current = readInk(root);
      const live = ink.current.direction === latest.current.lane ? 1 : ink.current.tokens.laneRest;
      laneLight.current = { from: live, to: live, at: 0 };
    }
    const { width, height, top } = view.current;
    if (!width || !height) return false;
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const pixelsX = Math.max(1, Math.round(width * ratio));
    const pixelsY = Math.max(1, Math.round(height * ratio));
    if (canvas.width !== pixelsX || canvas.height !== pixelsY) {
      canvas.width = pixelsX;
      canvas.height = pixelsY;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    }
    const shift = `translateY(${top}px)`;
    if (canvas.style.transform !== shift) canvas.style.transform = shift;
    context.setTransform(ratio, 0, 0, ratio, 0, -top * ratio);
    context.clearRect(0, top, width, height);
    context.lineCap = 'round';
    context.lineJoin = 'round';

    const now = performance.now();
    const current = ink.current;
    const live = liveFor(now);
    let busy = now - laneLight.current.at < LANE_FADE;
    const { moved, born, jolted, released } = coils.current;
    for (const segment of segmentsRef.current) {
      const lowest = Math.min(segment.from.y, segment.to.y) - 40;
      const highest = Math.max(segment.from.y, segment.to.y) + 40;
      if (highest < top || lowest > top + height) continue;
      // Opacity and weight as vision.css section 2 set them.
      let alpha;
      let lineWidth = 1.6;
      if (segment.state === 'active') {
        alpha = current.dim ? 0.9 : 1;
        lineWidth = 2.1;
      } else if (segment.state === 'affected') {
        alpha = current.dim ? 0.9 : 0.88;
      } else {
        alpha = current.dim ? 0.26 + 0.34 * live : 0.3 + 0.4 * live;
      }
      const age = now - (born.get(segment.key) ?? -Infinity);
      if (age < FADE_IN) {
        alpha *= easeOut(clamp01(age / FADE_IN));
        busy = true;
      }
      let stroke;
      const releasedAt = released.get(segment.key);
      if (releasedAt !== undefined) {
        // A popped row's springs go green and let go.
        const t = (now - releasedAt - RELEASE_DELAY) / RELEASE;
        alpha = 0.9 * (1 - easeIn(clamp01(t)));
        stroke = current.release;
        if (t < 1) busy = true;
      } else {
        // A coil's gradient runs between its resting ends: made once per
        // layout, not per frame.
        const gradients = coils.current.gradients;
        stroke = gradients.get(segment);
        if (!stroke) {
          stroke = context.createLinearGradient(segment.from.x, segment.from.y, segment.to.x, segment.to.y);
          stroke.addColorStop(0, tintFor(segment.fromRamp));
          stroke.addColorStop(1, tintFor(segment.toRamp));
          gradients.set(segment, stroke);
        }
      }
      if (alpha <= 0.002) continue;
      const shape = shapeOf(moved.get(segment.key) ?? segment.d);
      context.globalAlpha = alpha;
      context.lineWidth = lineWidth;
      context.strokeStyle = stroke;
      context.stroke(shape);
      // A jolt: the coil flashes the break colour, then eases back.
      const joltedAt = jolted.get(segment.key);
      if (joltedAt !== undefined) {
        const t = (now - joltedAt) / JOLT;
        if (t >= 1) {
          jolted.delete(segment.key);
        } else {
          const flash = t < 0.3 ? 1 : 1 - easeOut((t - 0.3) / 0.7);
          context.globalAlpha = flash;
          context.lineWidth = lineWidth + 0.6 * flash;
          context.strokeStyle = current.jolt;
          context.stroke(shape);
          busy = true;
        }
      }
    }
    context.globalAlpha = 1;
    return busy;
  };

  // One loop for everything that moves: the chain's motion, rows settling,
  // and the coils' own moments. It parks as soon as nothing is moving.
  const loop = (time) => {
    const state = motion.current;
    state.frame = 0;
    const moving = state.moving ? stepMotion(time) : false;
    const busy = paint();
    if (moving || busy) state.frame = requestAnimationFrame(loop);
  };

  const wake = () => {
    const state = motion.current;
    if (state.frame || typeof requestAnimationFrame === 'undefined') return;
    state.frame = requestAnimationFrame(loop);
  };

  const redraw = (fresh = false) => {
    const list = layer.current?.parentElement;
    if (!list) return;
    const { lane, numbers, ramp, states } = latest.current;
    const numbersKey = numbers.join(',');
    const chips = [...list.querySelectorAll(':scope > li > .clue-number')];
    if (chips.length !== numbers.length) {
      geometry.current = { key: '', centres: null };
      segmentsRef.current = [];
      wake();
      return;
    }
    let centres;
    if (!fresh && geometry.current.key === numbersKey && geometry.current.centres?.length === chips.length) {
      ({ centres } = geometry.current);
    } else {
      centres = readCentres(list, chips);
      geometry.current = { key: numbersKey, centres };
    }
    const segments = springSegments({ chips: centres, numbers, ramp, states, lane });
    const now = performance.now();
    const keys = new Set(segments.map((segment) => segment.key));
    const { born, jolted, released, moved } = coils.current;
    for (const segment of segments) if (!born.has(segment.key)) born.set(segment.key, now);
    for (const map of [born, jolted, released, moved]) {
      for (const key of map.keys()) if (!keys.has(key)) map.delete(key);
    }
    segmentsRef.current = segments;
    coils.current.gradients = new Map();
    wake();
  };

  const restMotion = () => {
    const state = motion.current;
    state.moving = false;
    state.chips?.forEach((chip) => { chip.style.translate = ''; });
    state.chips = null;
    coils.current.moved.clear();
    // A resize that arrived while rows were still sliding is measured now.
    if (state.remeasure) {
      state.remeasure = false;
      redraw(true);
    }
  };

  /** Advance the chain one frame; returns whether anything is still moving. */
  const stepMotion = (time) => {
    const state = motion.current;
    const list = layer.current?.parentElement;
    const { numbers } = latest.current;
    const cached = geometry.current;
    if (!list || !cached.centres || cached.centres.length !== numbers.length) {
      restMotion();
      return false;
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
    const moved = coils.current.moved;
    for (const segment of segmentsRef.current) {
      const a = centres[index.get(segment.fromNumber)];
      const b = centres[index.get(segment.toNumber)];
      if (!a || !b) continue;
      const restA = cached.centres[index.get(segment.fromNumber)];
      const restB = cached.centres[index.get(segment.toNumber)];
      // A spring at rest keeps its resting path.
      const still = Math.abs(a.x - restA.x) < 0.1 && Math.abs(b.x - restB.x) < 0.1 && Math.abs(a.y - restA.y) < 0.1 && Math.abs(b.y - restB.y) < 0.1;
      if (still) {
        moved.delete(segment.key);
        continue;
      }
      const shear = b.sway - a.sway;
      const tension = springTension(segment.steps);
      const ends = springEnds(a, b);
      moved.set(segment.key, coilPath(ends.from, ends.to, {
        ...tension,
        radius: tension.radius * (1 + Math.min(0.9, Math.abs(shear) / 14)),
        phase: shear * 0.24,
      }));
    }
    if (!settling && chainAtRest(state.chain)) {
      restMotion();
      return false;
    }
    return true;
  };

  const startMotion = () => {
    const state = motion.current;
    if (reducedMotion()) return;
    if (!state.moving) {
      state.moving = true;
      state.last = 0;
    }
    wake();
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
      const now = performance.now();
      if (detail.kind === 'release') {
        for (const segment of segmentsRef.current) {
          if (segment.fromNumber !== detail.number && segment.toNumber !== detail.number) continue;
          coils.current.released.set(segment.key, now);
        }
        wake();
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
          coils.current.jolted.set(segment.key, now);
        }
        startMotion();
        wake();
      }
    };
    window.addEventListener(SPRING_EVENT, onMotion);
    // The colours follow the theme and the settings; the lane's light follows
    // the direction being solved.
    const list = layer.current?.parentElement;
    const root = list?.closest('#app');
    // A direction switch only moves the lane's light: read the attribute,
    // never the computed style (that would force the whole page's style
    // inside the key press). Colours are re-read, a frame later and once,
    // only when the theme or the colour settings change.
    const aim = () => {
      const current = ink.current;
      if (!current || !root) return;
      const direction = root.getAttribute('data-direction') === 'down' ? 'down' : 'across';
      if (direction === current.direction) return;
      current.direction = direction;
      const live = direction === latest.current.lane ? 1 : current.tokens.laneRest;
      const now = performance.now();
      laneLight.current = { from: liveFor(now), to: live, at: now };
      wake();
    };
    let recolour = 0;
    const refresh = () => {
      if (recolour || !root) return;
      recolour = requestAnimationFrame(() => {
        recolour = 0;
        const direction = ink.current?.direction;
        ink.current = readInk(root);
        coils.current.gradients = new Map();
        if (direction) ink.current.direction = direction;
        aim();
        wake();
      });
    };
    const watchDirection = typeof MutationObserver === 'undefined' ? null : new MutationObserver(aim);
    const watch = typeof MutationObserver === 'undefined' ? null : new MutationObserver(refresh);
    if (root && watch && watchDirection) {
      watchDirection.observe(root, { attributes: true, attributeFilter: ['data-direction'] });
      watch.observe(root, { attributes: true, attributeFilter: ['data-ramp', 'data-vibrance', 'data-luma'] });
      watch.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class'] });
    }
    const scrolled = () => {
      if (list) view.current.top = list.scrollTop;
      wake();
    };
    if (list) view.current = { width: list.clientWidth, height: list.clientHeight, top: list.scrollTop };
    list?.addEventListener('scroll', scrolled, { passive: true });
    return () => {
      window.removeEventListener(SPRING_EVENT, onMotion);
      watch?.disconnect();
      watchDirection?.disconnect();
      cancelAnimationFrame(recolour);
      list?.removeEventListener('scroll', scrolled);
      cancelAnimationFrame(motion.current.frame);
      motion.current.frame = 0;
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
  useLayoutEffect(() => {
    redraw(false);
  }, [key, ramp]);

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
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.target !== list) continue;
        // After layout, so these reads are free.
        view.current = { width: list.clientWidth, height: list.clientHeight, top: list.scrollTop };
        wake();
      }
      schedule();
    });
    observer.observe(list);
    list.querySelectorAll(':scope > li').forEach((row) => observer.observe(row));
    document.fonts?.ready?.then(schedule);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [numbers.join(',')]);

  return <canvas ref={layer} className="clue-spring" aria-hidden="true" data-lane={lane} />;
}

export default memo(
  ClueSpring,
  (a, b) =>
    a.lane === b.lane &&
    a.ramp === b.ramp &&
    a.numbers.join(',') === b.numbers.join(',') &&
    a.states.join(',') === b.states.join(','),
);
