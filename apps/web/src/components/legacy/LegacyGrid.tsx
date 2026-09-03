import type { Cell, CellId, Direction, PuzzleDocument, PuzzleIndex } from '@crossword/domain';
import type { SolveSessionSnapshot } from '@crossword/domain';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';

type LegacyGridProps = {
  puzzle: PuzzleDocument;
  index: PuzzleIndex;
  session: SolveSessionSnapshot;
  incorrectCellIds: readonly CellId[];
  checkedCellIds: readonly CellId[];
  onSelectCell: (cellId: CellId) => void;
  onEnter: (letter: string) => void;
  onEnterRebus: (token: string) => void;
  onClear: () => void;
  onMove: (key: 'ArrowUp' | 'ArrowDown' | 'ArrowLeft' | 'ArrowRight') => void;
  onToggleDirection: () => void;
};

/**
 * Exact replica of the legacy grid (newapp.html): real inputs per white
 * cell, native typing feel, black squares as divs, clue indices, shaded /
 * circled / rebus cell classes, highlighted-entry fill.
 */
export function LegacyGrid({
  puzzle,
  index,
  session,
  incorrectCellIds,
  checkedCellIds,
  onSelectCell,
  onEnter,
  onEnterRebus,
  onClear,
  onMove,
  onToggleDirection
}: LegacyGridProps) {
  const numbersByCellId = new Map<CellId, string>();
  const solutionByCellId = new Map<CellId, string>();
  for (const entry of puzzle.entries) {
    entry.cellIds.forEach((cellId, position) => {
      solutionByCellId.set(cellId, entry.answer[position] ?? '');
    });
  }
  for (const entry of puzzle.entries) {
    const firstCellId = entry.cellIds[0];
    if (!firstCellId) continue;
    const current = numbersByCellId.get(firstCellId);
    if (!current) numbersByCellId.set(firstCellId, `${entry.number}`);
    else if (current !== `${entry.number}`) numbersByCellId.set(firstCellId, `${current}/${entry.number}`);
  }

  const activeEntry = index.entriesById.get(session.selection.entryId);
  const activeCellIds = new Set(activeEntry?.cellIds ?? []);

  function handleKeyDown(event: ReactKeyboardEvent<HTMLInputElement>, cell: Cell) {
    // port of legacy handle_crossword_cell_keydown: arrows move within the
    // direction, or switch direction at the edge of their family
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      if (session.selection.direction === 'across') onMove('ArrowRight');
      else onToggleDirection();
      return;
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      if (session.selection.direction === 'across') onMove('ArrowLeft');
      else onToggleDirection();
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (session.selection.direction === 'down') onMove('ArrowDown');
      else onToggleDirection();
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (session.selection.direction === 'down') onMove('ArrowUp');
      else onToggleDirection();
      return;
    }
    if (event.key === 'Backspace') {
      event.preventDefault();
      onClear();
      return;
    }
    if (event.key.length === 1 && /^[a-zA-Z]$/.test(event.key)) {
      event.preventDefault();
      onEnter(event.key);
    }
  }

  const rows = Array.from({ length: puzzle.height }, (_, row) =>
    puzzle.cells.filter((cell) => cell.row === row)
  );

  return (
    <div id="crossword-container">
      <div
        className="grid"
        style={{ gridTemplateRows: `repeat(${puzzle.height}, var(--cell-size))` }}
      >
        {rows.map((row, rowIndex) => (
          <div
            className="grid-row"
            key={rowIndex}
            style={{ gridTemplateColumns: `repeat(${row.length}, var(--cell-size))` }}
          >
            {row.map((cell) => {
              if (cell.block) {
                return <div className="grid-cell black-cell" key={cell.id} />;
              }
              const letter = session.entered[cell.id] ?? '';
              const highlighted = activeCellIds.has(cell.id);
              const selected = session.selection.cellId === cell.id;
              const incorrect = incorrectCellIds.includes(cell.id);
              const green = checkedCellIds.includes(cell.id) && !incorrect;
              const inputClasses = [
                incorrect ? 'red' : '',
                green ? 'green' : '',
                selected ? 'current-cell' : ''
              ].filter(Boolean).join(' ');
              const stateClasses = [
                cell.shaded ? 'shaded' : '',
                cell.circled ? 'circled' : '',
                cell.rebus !== undefined ? 'rebus' : ''
              ].filter(Boolean).join(' ');
              return (
                <div
                  className={`grid-cell ${stateClasses} ${highlighted ? 'highlighted-cell' : ''}`}
                  key={cell.id}
                >
                  <span className="clue-index">{numbersByCellId.get(cell.id) ?? ''}</span>
                  <input
                    aria-label={`${numbersByCellId.get(cell.id) ? `${numbersByCellId.get(cell.id)}, ` : ''}row ${cell.row + 1}, column ${cell.column + 1}${letter ? `, ${letter}` : ', empty'}${selected ? ', selected' : ''}`}
                    className={inputClasses}
                    data-cell={cell.column}
                    data-cell-id={cell.id as string}
                    data-row={cell.row}
                    data-solution={solutionByCellId.get(cell.id) ?? ''}
                    maxLength={cell.rebus !== undefined ? 10 : 1}
                    onContextMenu={(event) => {
                      if (cell.rebus === undefined) return;
                      event.preventDefault();
                      const token = window.prompt('Rebus entry (up to 10 letters):');
                      if (token) onEnterRebus(token);
                    }}
                    onChange={(event) => {
                      // paste, dictation, IME and autofill land here; the
                      // keyboard path stays on keydown for legacy speed
                      const sanitized = event.target.value.replace(/[^A-Za-z]/g, '');
                      if (sanitized) onEnter(sanitized);
                    }}
                    onPaste={(event) => {
                      const text = event.clipboardData.getData('text').replace(/[^A-Za-z]/g, '').toUpperCase();
                      if (!text) return;
                      event.preventDefault();
                      for (const ch of text) onEnter(ch);
                    }}
                    onClick={() => onSelectCell(cell.id as CellId)}
                    onFocus={() => onSelectCell(cell.id as CellId)}
                    onKeyDown={(event) => handleKeyDown(event as ReactKeyboardEvent<HTMLInputElement>, cell)}
                    readOnly={false}
                    type="text"
                    value={letter}
                  />
                  {cell.rebus !== undefined && (
                    <span className="rebus-indicator">{cell.rebus.length}</span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
