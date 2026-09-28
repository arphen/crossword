import React, { useEffect, useMemo, useState } from 'react';
import { assistanceLadder } from './assistanceLadder';

function idFor(entry) {
  return entry ? `${entry.direction}-${entry.clue_number}` : '';
}

function blankCell(entry, index, app) {
  const row = entry.direction === 'across' ? entry.start_y : entry.start_y + index;
  const column = entry.direction === 'across' ? entry.start_x + index : entry.start_x;
  return { row, column, beforeToken: app.grid?.[row]?.[column] || null };
}

function revealEntry(app, entry, mode, onCellRevealed) {
  let revealed = 0;
  for (let index = 0; index < entry.characters.length; index += 1) {
    if (mode === 'letter' && revealed > 0) break;
    const cell = blankCell(entry, index, app);
    if (cell.beforeToken) continue;
    const token = String(entry.characters[index]?.letters || '').toUpperCase();
    if (!token) continue;
    app.grid[cell.row][cell.column] = token;
    app.revealsUsed = (app.revealsUsed || 0) + 1;
    app.score = Math.max(0, (app.score || 0) - 20);
    onCellRevealed?.({ ...cell, token }, app);
    revealed += 1;
  }
  if (revealed && app.isChecking) app.clearChecks?.();
  return revealed;
}

export default function AssistanceLadder({
  app,
  entry,
  onHintShown,
  onCellRevealed,
}) {
  const entryKey = idFor(entry);
  const [shown, setShown] = useState([]);
  const ladder = useMemo(
    () => assistanceLadder(app, entry),
    [app, entry],
  );

  useEffect(() => setShown([]), [entryKey]);

  if (!entry || !ladder.length) return null;
  const hasBlank = entry.characters.some((_, index) => {
    const cell = blankCell(entry, index, app);
    return !cell.beforeToken;
  });
  const next = hasBlank
    ? ladder.find((hint) => !shown.includes(hint.assistanceTier))
    : null;
  return (
    <section className="future-assistance" aria-label="Clue assistance">
      <div className="future-assistance-heading">
        <span className="future-eyebrow">Need a thread?</span>
        <span className="future-assistance-entry">
          {entry.direction === 'across' ? 'Across' : 'Down'} {entry.clue_number}
        </span>
      </div>
      {shown.length > 0 && (
        <div className="future-assistance-notes" aria-live="polite">
          {ladder
            .filter((hint) => shown.includes(hint.assistanceTier))
            .map((hint) => (
              <article key={hint.assistanceTier} className="future-assistance-note">
                <span className="future-assistance-tier">{hint.label}</span>
                <p>{hint.text}</p>
              </article>
            ))}
        </div>
      )}
      {next && (
        <button
          type="button"
          className="future-assistance-button"
          onClick={() => {
            setShown((value) => [...value, next.assistanceTier]);
            onHintShown?.({
              entryId: entryKey,
              hintId: next.hintId,
              assistanceTier: next.assistanceTier,
              affectedCellIds: next.affectedCellIds,
            });
            if (next.reveal) revealEntry(app, entry, next.reveal, onCellRevealed);
          }}
        >
          {next.label}
          <span aria-hidden="true">↗</span>
        </button>
      )}
    </section>
  );
}
