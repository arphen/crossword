import React, { memo, useLayoutEffect, useRef, useState } from 'react';
import { springSegments } from './springGeometry';
import { cssVars } from './cssVars';
import { RETRACE_EVENT } from './useRapture';

// The chips sit at different heights because every clue row sizes itself, so the
// springs are drawn from measured rectangles rather than from CSS arithmetic. The
// layer is absolutely positioned inside the scrolling list, which means it scrolls
// with the clues for free, and it is the list's last child so the ladder's
// :nth-child rules still count only clue rows.
function readCentres(list, chips) {
  const box = list.getBoundingClientRect();
  return chips.map((chip) => {
    const rect = chip.getBoundingClientRect();
    return {
      x: rect.left + rect.width / 2 - box.left + list.scrollLeft,
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
  // actually move rows — resizes, font loads, rapture bounces — measures fresh,
  // and the row ResizeObservers below repair the cache if a highlight ever does
  // shift a row's height a frame later.
  const geometry = useRef({ key: '', centres: null, height: 0 });

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
      frame = requestAnimationFrame(() => redraw(true));
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(list);
    list.querySelectorAll(':scope > li').forEach((row) => observer.observe(row));
    document.fonts?.ready?.then(schedule);
    // While rows bounce into place the springs follow them frame by frame.
    const retrace = () => redraw(true);
    window.addEventListener(RETRACE_EVENT, retrace);
    return () => {
      window.removeEventListener(RETRACE_EVENT, retrace);
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
