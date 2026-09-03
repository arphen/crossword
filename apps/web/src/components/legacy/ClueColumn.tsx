import type { CellId, Direction, Entry, PuzzleIndex } from '@crossword/domain';
import type { SolveSessionSnapshot } from '@crossword/domain';

type ClueColumnProps = {
  direction: Direction;
  label: 'ACROSS' | 'DOWN';
  entries: readonly Entry[];
  index: PuzzleIndex;
  session: SolveSessionSnapshot;
  incorrectCellIds: readonly CellId[];
  checkedCellIds: readonly CellId[];
  onSelectEntry: (entry: Entry) => void;
  onSelectPattern: (entry: Entry, position: number) => void;
};

function isEntryCompleted(entry: Entry, session: SolveSessionSnapshot): boolean {
  return entry.cellIds.length > 0 && entry.cellIds.every((cellId) => Boolean(session.entered[cellId]));
}

/**
 * Exact replica of the legacy clue column (newapp.html): a wrapped list whose
 * odd/even rows mirror around the number seam, giant rotated watermark
 * behind (styled by the ported legacy stylesheet), affected clues tinted by
 * the active direction.
 */
export function ClueColumn({
  direction,
  label,
  entries,
  index,
  session,
  incorrectCellIds,
  checkedCellIds,
  onSelectEntry,
  onSelectPattern
}: ClueColumnProps) {
  const active = session.selection.direction === direction;
  const activeEntry = index.entriesById.get(session.selection.entryId);

  // legacy getIntersectingClues: opposite-direction entries crossing the
  // active entry, mapped to their exact shared cell ids
  const shared = new Map<string, CellId[]>();
  if (activeEntry) {
    const other: Direction = activeEntry.direction === 'across' ? 'down' : 'across';
    for (const cellId of activeEntry.cellIds) {
      const crossingId = index.entryAt.get(cellId)?.[other];
      if (!crossingId || crossingId === activeEntry.id) continue;
      const cells = shared.get(crossingId);
      if (cells) cells.push(cellId);
      else shared.set(crossingId, [cellId]);
    }
  }

  // the template names the intersection class after the ACTIVE direction,
  // so the ring color follows the active entry's family
  const intersectionClass = activeEntry?.direction === 'across'
    ? 'intersection-cell-across'
    : 'intersection-cell-down';

  const visible = entries.filter((entry) => !isEntryCompleted(entry, session));

  return (
    <div
      aria-label={`${label} clues`}
      className={`clue-column ${active ? 'active' : 'inactive'}`}
      data-label={label}
      tabIndex={0}
    >
      <ul id={direction}>
        {visible.map((entry) => {
          const highlighted = session.selection.entryId === entry.id;
          const affected = shared.has(entry.id);
          const sharedCells = shared.get(entry.id) ?? [];
          return (
            <li
              aria-label={`${entry.number} ${entry.direction}: ${entry.clue}`}
              className={`${highlighted ? 'highlighted-clue' : ''} ${affected ? 'affected-clue' : ''}`}
              onClick={() => onSelectEntry(entry)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onSelectEntry(entry);
                }
              }}
              tabIndex={0}
            >        {direction === 'down' && <strong className="clue-number">{entry.number}.</strong>}
              <div className="clue-content">
                <span className="clue-text">{entry.clue}</span>
                <div className="state-container">
                  {entry.cellIds.map((cellId, position) => {
                    const char = session.entered[cellId] ?? ' ';
                    const incorrect = incorrectCellIds.includes(cellId);
                    const green = checkedCellIds.includes(cellId) && !incorrect;
                    const crossing = sharedCells.includes(cellId) ? ` ${intersectionClass}` : '';
                    return (
                      <span
                        aria-label={`${entry.number} ${entry.direction}, letter ${position + 1}`}
                        className={`state${crossing}${incorrect ? ' red' : ''}${green ? ' green' : ''}`}
                        key={cellId}
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelectPattern(entry, position);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            event.stopPropagation();
                            onSelectPattern(entry, position);
                          }
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        {char === ' ' ? '\u00A0' : char}
                      </span>
                    );
                  })}
                </div>
              </div>
              {direction === 'across' && <strong className="clue-number">{entry.number}.</strong>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
