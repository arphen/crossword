import React, { useEffect, useRef, useState } from 'react';
import { COMBO_TIERS, comboHeat, comboMultiplier, comboTier } from './combo';
import { cssVars } from './cssVars';

// Points and the run in the masthead. At rest it shows the behaviour's totals;
// while a check plays back it follows the sequence beat by beat (the bus from
// useRapture), so the number climbs with each word as it pops and the meter
// cracks when the mistakes land. Only this component renders per beat.

const formatPoints = (value) => Math.max(0, Math.round(value)).toLocaleString('en-US');
const multiplierText = (value) => `×${value % 1 ? value.toFixed(1) : value}`;

// A few jagged lines from a point near the middle: the fracture drawn on a
// broken run. Fixed shapes, so the crack reads the same every time.
const CRACKS = [
  'M50 46 L41 38 L35 40 L24 27 L18 28 L9 17',
  'M50 46 L58 40 L66 43 L74 31 L83 30 L92 19',
  'M50 46 L47 58 L39 64 L36 76',
  'M50 46 L56 55 L64 58 L71 72 L79 75',
  'M41 38 L42 29',
  'M66 43 L70 52',
];

export default function ComboMeter({ app, bus }) {
  const [shown, setShown] = useState(/** @type {null | { points: number, combo: number }} */ (null));
  const [flash, setFlash] = useState(/** @type {null | { kind: string, n: number }} */ (null));
  const [deltas, setDeltas] = useState(/** @type {Array<{ n: number, text: string, kind: string }>} */ ([]));
  const counter = useRef(0);
  const timers = useRef([]);

  useEffect(() => {
    if (!bus) return undefined;
    const later = (fn, ms) => timers.current.push(setTimeout(fn, ms));
    const pop = (text, kind) => {
      const n = (counter.current += 1);
      setDeltas((list) => [...list.slice(-3), { n, text, kind }]);
      later(() => setDeltas((list) => list.filter((delta) => delta.n !== n)), 900);
    };
    const unsubscribe = bus.subscribe((event) => {
      if (event.type === 'start') {
        if (event.beats?.length) setShown({ points: event.from.points, combo: event.from.combo });
      } else if (event.type === 'word' && event.beat) {
        const { beat } = event;
        setShown({ points: beat.total, combo: beat.combo });
        if (beat.points > 0) pop(`+${formatPoints(beat.points)}`, beat.tierUp ? 'tier' : 'word');
        const n = (counter.current += 1);
        setFlash({ kind: beat.tierUp ? 'tier' : 'word', n });
      } else if (event.type === 'break' && event.beat) {
        const { beat } = event;
        setShown({ points: beat.total, combo: 0 });
        if (beat.penalty > 0) pop(`−${formatPoints(beat.penalty)}`, 'break');
        const n = (counter.current += 1);
        setFlash({ kind: beat.lost > 0 ? 'shatter' : 'dent', n });
        later(() => setFlash((current) => (current?.n === n ? null : current)), 1500);
      } else if (event.type === 'end') {
        setShown(null);
      } else if (event.type === 'instant') {
        setShown(null);
      }
    });
    return () => {
      unsubscribe();
      timers.current.forEach(clearTimeout);
      timers.current = [];
    };
  }, [bus]);

  const points = shown ? shown.points : app.points;
  const combo = shown ? shown.combo : app.combo;
  const tier = comboTier(combo);
  const multiplier = comboMultiplier(combo);
  const top = COMBO_TIERS.at(-1).from;
  const fracture = flash?.kind === 'shatter' || flash?.kind === 'dent' ? flash : null;
  const label = combo > 0
    ? `${formatPoints(points)} points, ${combo} in a row, ${multiplierText(multiplier)}; best run ${app.bestCombo}`
    : `${formatPoints(points)} points; best run ${app.bestCombo}`;

  return (
    <div
      className="stat-item combo-meter"
      data-tier={tier}
      data-live={combo > 0 ? 'true' : undefined}
      data-flash={flash && !fracture ? `${flash.kind}-${flash.n % 2}` : undefined}
      data-fracture={fracture ? `${fracture.kind}-${fracture.n % 2}` : undefined}
      style={cssVars({ '--heat': comboHeat(combo), '--run': Math.min(1, combo / top) })}
      role="status"
      aria-label={label}
      title={`Best run: ${app.bestCombo}`}
    >
      <span className="stat-value">
        <span className="combo-mult" aria-hidden="true">{combo > 0 ? multiplierText(multiplier) : '×1'}</span>
        <span className="combo-points">{formatPoints(points)}</span>
      </span>
      <span className="stat-label">
        Points
        <span className="combo-streak" aria-hidden="true">{combo > 0 ? ` · ${combo} run` : ''}</span>
      </span>
      <span className="combo-heat" aria-hidden="true">
        {COMBO_TIERS.slice(1).map((step) => (
          <i key={step.from} style={cssVars({ '--at': step.from / top })} />
        ))}
      </span>
      <span className="combo-deltas" aria-hidden="true">
        {deltas.map((delta) => (
          <b key={delta.n} data-kind={delta.kind}>{delta.text}</b>
        ))}
      </span>
      {fracture && (
        <svg key={fracture.n} className="combo-crack" viewBox="0 0 100 92" preserveAspectRatio="none" aria-hidden="true">
          {CRACKS.map((d, index) => (
            <path key={index} d={d} style={cssVars({ '--i': index })} />
          ))}
        </svg>
      )}
    </div>
  );
}
