import React, { memo, useLayoutEffect, useRef, useState } from 'react';
import { springSegments } from './springGeometry';
import { cssVars } from './cssVars';
import { RETRACE_EVENT } from './useRapture';

// The chips sit at different heights because every clue row sizes itself, so the
// springs are drawn from measured rectangles rather than from CSS arithmetic. The
// layer is absolutely positioned inside the scrolling list, which means it scrolls
// with the clues for free, and it is the list's last child so the ladder's
// :nth-child rules still count only clue rows.
function measure(list, { lane, numbers, ramp, states }) {
  const chips = [...list.querySelectorAll(':scope > li > .clue-number')];
  if (chips.length !== numbers.length) return { height: 0, segments: [] };
  const box = list.getBoundingClientRect();
  const centres = chips.map((chip) => {
    const rect = chip.getBoundingClientRect();
    return {
      x: rect.left + rect.width / 2 - box.left + list.scrollLeft,
      y: rect.top + rect.height / 2 - box.top + list.scrollTop,
      hw: rect.width / 2,
      hh: rect.height / 2,
    };
  });
  // From the last row, not scrollHeight: the layer itself counts toward the
  // list's scrollable height and would hold it open after a clue is solved.
  const last = chips.at(-1)?.parentElement;
  return {
    height: last ? last.offsetTop + last.offsetHeight : 0,
    segments: springSegments({ chips: centres, numbers, ramp, states, lane }),
  };
}

function ClueSpring({ lane, numbers, ramp, states }) {
  const layer = useRef(null);
  const [drawn, setDrawn] = useState({ height: 0, segments: [] });
  // Kept in a ref so the observers always measure the latest props without being
  // torn down and rebuilt on every selection change.
  const latest = useRef({ lane, numbers, ramp, states });
  latest.current = { lane, numbers, ramp, states };
  const stamp = useRef('');

  const redraw = () => {
    const list = layer.current?.parentElement;
    if (!list) return;
    const next = measure(list, latest.current);
    const signature = `${next.height}|${next.segments.map((segment) => `${segment.key}:${segment.d}:${segment.state}`).join('|')}`;
    if (signature === stamp.current) return;
    stamp.current = signature;
    setDrawn(next);
  };

  // Every commit that changes which clues are listed, or how they are marked,
  // measures synchronously so a solved clue never leaves a spring dangling for a
  // frame.
  const key = `${lane}|${numbers.join(',')}|${states.join(',')}`;
  useLayoutEffect(redraw, [key, ramp]);

  useLayoutEffect(() => {
    const list = layer.current?.parentElement;
    if (!list || typeof ResizeObserver === 'undefined') return undefined;
    let frame = 0;
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(redraw);
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(list);
    list.querySelectorAll(':scope > li').forEach((row) => observer.observe(row));
    document.fonts?.ready?.then(schedule);
    // While rows bounce into place the springs follow them frame by frame.
    window.addEventListener(RETRACE_EVENT, redraw);
    return () => {
      window.removeEventListener(RETRACE_EVENT, redraw);
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
