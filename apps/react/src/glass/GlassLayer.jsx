import React, { useEffect, useRef, useState } from 'react';
import { readGlassFlag } from './flag';
import { GlassEngine } from './engine';
import { weekdayIndex } from './palette';
import './glass.css';

// The optional glass layer behind the board (?gpu=1, or the stored override;
// off by default). It renders nothing of its own into React's tree but the
// debug readout: the engine makes its canvas behind the grid and only reads
// the board the CSS draws. When a backend is up, the view marks its root
// data-glass and glass.css makes the squares transparent; if none can start,
// nothing changes.

/**
 * @param {{
 *   gridRef: { current: HTMLElement | null },
 *   weekday: string,
 *   light: boolean,
 *   direction: 'across' | 'down',
 *   onBackend: (backend: 'webgpu' | 'webgl2' | null) => void,
 * }} props
 */
export default function GlassLayer({ gridRef, weekday, light, direction, onBackend }) {
  const [flag] = useState(() => readGlassFlag(
    typeof window === 'undefined' ? '' : window.location.search,
    typeof window === 'undefined' ? null : window.localStorage,
  ));
  const engine = useRef(/** @type {GlassEngine | null} */ (null));
  const debug = useRef(/** @type {HTMLDivElement | null} */ (null));
  const report = useRef(onBackend);
  report.current = onBackend;
  const mood = { weekday: weekdayIndex(weekday), light, direction };
  const latestMood = useRef(mood);
  latestMood.current = mood;

  useEffect(() => {
    const grid = gridRef.current;
    if (!flag.enabled || !grid) return undefined;
    const scale = Number.parseFloat(new URLSearchParams(window.location.search).get('gpu-scale') || '');
    const glass = new GlassEngine({
      grid,
      flag,
      debug: debug.current,
      fixedScale: Number.isFinite(scale) && scale > 0 ? scale : null,
      onBackend: (backend) => report.current(backend),
    });
    engine.current = glass;
    glass.setMood(latestMood.current);
    glass.start();
    return () => {
      glass.destroy();
      engine.current = null;
      report.current(null);
    };
  }, [flag, gridRef]);

  useEffect(() => {
    engine.current?.setMood(mood);
  }, [mood.weekday, mood.light, mood.direction]);

  if (!flag.debug) return null;
  return <div className="glass-debug" ref={debug} aria-hidden="true" />;
}
