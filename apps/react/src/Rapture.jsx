import React, { useState } from 'react';
import { confettiSpecs, finaleMessage } from './celebration';
import { cssVars } from './cssVars';

// The pieces of a celebration that are drawn rather than computed: plain DOM
// animated by celebration.css (transform and opacity, finite), so nothing keeps
// running once the moment has passed. A check's fireworks are the one canvas
// (Volley.jsx); these are the board-wide moment and the finish.

/** What a big enough check adds to the whole board: a green wash, a note, and for
 *  a clean sweep a little confetti in the number colours. */
export function RaptureLayer({ active }) {
  if (!active || active.tier < 2) return null;
  return (
    <div className="rapture-layer" data-tier={active.tier} aria-hidden={active.note ? undefined : 'true'}
      style={cssVars({ '--moment-delay': `${active.noteDelay || 0}ms` })}>
      {active.tier >= 4 && <div className="rapture-wash" />}
      {active.note && (
        <div className="rapture-note" role="status">
          <strong>{active.note.title}</strong>
          <span data-clean={active.mistakes === 0 ? 'true' : 'false'}>{active.note.detail}</span>
        </div>
      )}
      {active.tier >= 5 && <Confetti count={28} seed={active.id} />}
    </div>
  );
}

/** Confetti falls from the top edge, or, given an origin, flares out of that
 *  point first and then falls: each piece leaves at its own angle and reach. */
function Confetti({ count, seed, origin = null }) {
  return (
    <div className="confetti" aria-hidden="true" data-origin={origin ? 'notch' : undefined}
      style={origin ? cssVars({ '--ox': `${Math.round(origin.x)}px`, '--oy': `${Math.round(origin.y)}px` }) : undefined}>
      {confettiSpecs(count, seed).map((piece, index) => (
        <i
          key={index}
          style={cssVars({
            '--bx': `${Math.round(Math.cos((piece.left / 100) * 2 * Math.PI) * (70 + ((piece.duration - 1900) / 1500) * 130))}px`,
            '--by': `${Math.round(Math.sin((piece.left / 100) * 2 * Math.PI) * (56 + ((piece.duration - 1900) / 1500) * 100) - 40)}px`,
            '--left': `${piece.left}%`,
            '--clue-ramp': piece.ramp,
            '--delay': `${piece.delay}ms`,
            '--fall': `${piece.duration}ms`,
            '--drift': `${piece.drift}px`,
            '--spin': `${piece.spin}deg`,
            '--w': `${piece.width}px`,
            '--h': `${piece.height}px`,
          })}
        />
      ))}
    </div>
  );
}

/** The finish. It answers to how the puzzle was solved, not just that it was,
 *  and when the board knows where its last notch was, the fireworks start
 *  there. */
export function Finale({ app, origin = null }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  const message = finaleMessage({ score: app.score, checks: app.checksUsed, reveals: app.revealsUsed });
  return (
    <div className="finale" data-grade={message.grade}>
      <div className="rapture-wash" />
      <Confetti count={72} seed={app.checksUsed + app.score} origin={origin} />
      <div className="finale-card" role="status" onClick={() => setDismissed(true)}>
        <svg className="finale-mark" viewBox="0 0 52 52" aria-hidden="true">
          <circle cx="26" cy="26" r="23" />
          <path d="M15 27.5 22.5 35 37 18.5" />
        </svg>
        <h2>{message.title}</h2>
        <p>{message.line}</p>
        <dl>
          <div><dt>Time</dt><dd>{app.formatTime(app.timer)}</dd></div>
          <div><dt>Score</dt><dd>{app.score}</dd></div>
          <div><dt>Points</dt><dd>{Math.round(app.points || 0).toLocaleString('en-US')}</dd></div>
          <div><dt>Best run</dt><dd>{app.bestCombo || 0}</dd></div>
          <div><dt>Checks</dt><dd>{app.checksUsed}</dd></div>
          <div><dt>Reveals</dt><dd>{app.revealsUsed}</dd></div>
        </dl>
      </div>
    </div>
  );
}
