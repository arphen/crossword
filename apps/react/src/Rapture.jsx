import React, { useState } from 'react';
import { confettiSpecs, finaleMessage } from './celebration';
import { cssVars } from './cssVars';

// The pieces of a celebration that are drawn rather than computed. All of it is
// plain DOM animated by celebration.css (transform and opacity, finite), so there
// is no canvas and nothing keeps running once the moment has passed.

/** Sparks leaving one solved clue's chip. Alternate rows mirror and rotate the same
 *  spec so a batch does not read as one stamp repeated. */
export function RaptureSparks({ specs, index = 0 }) {
  const turned = specs.length ? [...specs.slice(index % specs.length), ...specs.slice(0, index % specs.length)] : specs;
  return (
    <span className="rapture-sparks" aria-hidden="true" style={cssVars({ '--flip': index % 2 ? -1 : 1 })}>
      {turned.map((spark, position) => (
        <i
          key={position}
          data-tone={spark.tone}
          style={cssVars({
            '--dx': `${spark.dx}px`,
            '--dy': `${spark.dy}px`,
            '--size': `${spark.size}px`,
            '--spark-delay': `${spark.delay}ms`,
            '--spark-time': `${spark.duration}ms`,
          })}
        />
      ))}
    </span>
  );
}

/** What a big enough check adds to the whole board: a green wash, a note, and for
 *  a clean sweep a little confetti in the number colours. */
export function RaptureLayer({ active }) {
  if (!active || active.tier < 2) return null;
  return (
    <div className="rapture-layer" data-tier={active.tier} aria-hidden={active.note ? undefined : 'true'}>
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

function Confetti({ count, seed }) {
  return (
    <div className="confetti" aria-hidden="true">
      {confettiSpecs(count, seed).map((piece, index) => (
        <i
          key={index}
          style={cssVars({
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

/** The finish. It answers to how the puzzle was solved, not just that it was. */
export function Finale({ app }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  const message = finaleMessage({ score: app.score, checks: app.checksUsed, reveals: app.revealsUsed });
  return (
    <div className="finale" data-grade={message.grade}>
      <div className="rapture-wash" />
      <Confetti count={72} seed={app.checksUsed + app.score} />
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
          <div><dt>Checks</dt><dd>{app.checksUsed}</dd></div>
          <div><dt>Reveals</dt><dd>{app.revealsUsed}</dd></div>
        </dl>
      </div>
    </div>
  );
}
