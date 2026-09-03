import { useState } from 'react';
import { enterRebus } from '@crossword/domain';
import { ClueColumn } from '../components/legacy/ClueColumn';
import { LegacyGrid } from '../components/legacy/LegacyGrid';
import { resolveHarnessFixture, resolveHarnessMode, type HarnessMode } from './fixtures';

const noop = () => undefined;

export function HarnessPage({ fixtureId, mode }: { fixtureId: string | null; mode: HarnessMode }) {
  const fixture = resolveHarnessFixture(fixtureId);
  const { puzzle, index, session: initialSession, incorrectCellIds } = fixture.build();
  const [session, setSession] = useState(initialSession);
  const acrossEntries = puzzle.entries.filter((entry) => entry.direction === 'across');
  const downEntries = puzzle.entries.filter((entry) => entry.direction === 'down');

  function handleEnterRebus(token: string) {
    setSession((current) => enterRebus(current, puzzle, index, token));
  }

  return (
    <div
      id="app"
      className={`harness-root${mode === 'dark' ? ' harness-night' : ''}`}
      data-mode={mode}
      style={mode === 'dark' ? { colorScheme: 'dark' } : undefined}
    >
      <div id="notmenu">
        <ClueColumn
          checkedCellIds={session.checkedCellIds}
          direction="across"
          entries={acrossEntries}
          incorrectCellIds={incorrectCellIds}
          index={index}
          label="ACROSS"
          onSelectEntry={noop}
          onSelectPattern={noop}
          session={session}
        />
        <div className="center-column">
          <div id="crossword-container">
            <LegacyGrid
              checkedCellIds={session.checkedCellIds}
              index={index}
              incorrectCellIds={incorrectCellIds}
              onClear={noop}
              onEnter={noop}
              onEnterRebus={handleEnterRebus}
              onMove={noop}
              onSelectCell={noop}
              onToggleDirection={noop}
              puzzle={puzzle}
              session={session}
            />
          </div>
        </div>
        <ClueColumn
          checkedCellIds={session.checkedCellIds}
          direction="down"
          entries={downEntries}
          incorrectCellIds={incorrectCellIds}
          index={index}
          label="DOWN"
          onSelectEntry={noop}
          onSelectPattern={noop}
          session={session}
        />
      </div>

      <section className="harness-notes" aria-label="Fixture notes">
        <ul>
          {fixture.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
          {mode === 'forced' && <li>Placeholder: forced-colors cannot be emulated in-page; Playwright forced-colors emulation covers it later.</li>}
          {mode === 'zoom' && <li>Placeholder: 200% zoom is a browser-level state; use browser zoom or Playwright zoom emulation.</li>}
        </ul>
      </section>

      <nav className="harness-index" aria-label="Fixture index">
        {['empty-15', 'active-across', 'active-down-typed', 'check-error', 'half-collapsed', 'long-clue', 'special-cells', 'rebus'].map((id) => (
          <a key={id} href={`/harness?fixture=${id}&mode=${mode}`}>{id}</a>
        ))}
        <span className="harness-modes">
          {(['light', 'dark', 'forced', 'zoom'] as const).map((candidate) => (
            <a key={candidate} href={`/harness?fixture=${fixture.id}&mode=${candidate}`}>{candidate}</a>
          ))}
        </span>
      </nav>
    </div>
  );
}
