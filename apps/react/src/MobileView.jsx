import React, { useCallback } from 'react';
import mobileCss from './mobile.css?inline';

/** Mobile markup for the observable controller; room/socket lifecycle belongs to its owner. */
export default function MobileView({ app }) {
  const setHiddenInput = useCallback((element) => {
    app.setRef('hiddenInput', element);
  }, [app]);

  return (
    <>
      <style>{mobileCss}</style>
      <div id="app">
        <div className="mobile-header">
          <div className={`role-badge role-${app.role}`}>{app.role}</div>
          <div>
            <button className="action-btn check-btn" onClick={() => app.toggleCheck()}>{app.checkButtonLabel}</button>{' '}
            <button className="action-btn swap-btn" onClick={() => app.requestSwap()}>Swap</button>
          </div>
        </div>

        {!app.crossword.length ? (
          <div className="loading">Loading puzzle...</div>
        ) : (
          <ul className="clue-list">
            {app.sortedEntries.map((entry) => (
              <li
                key={entry.clue_number + entry.direction}
                className={[
                  'clue-item',
                  app.activeEntry === entry && 'active',
                  app.solvedKeys.includes(entry.clue_number + '-' + entry.direction) && 'solved',
                ].filter(Boolean).join(' ')}
                onClick={() => app.selectEntry(entry)}
              >
                <div className="clue-header">
                  <span className="clue-number">{entry.clue_number}</span>{' '}
                  <span className="clue-text">{entry.clue_text}</span>
                </div>

                <div className="answer-input">
                  {entry.characters.map((char, idx) => (
                    <div
                      key={idx}
                      className={[
                        'char-box',
                        app.getCellValue(entry, idx) && 'filled',
                        app.activeEntry === entry && app.activeCharIndex === idx && 'active-cell',
                        app.isChecking && app.isCellCorrect(entry, idx) && 'correct',
                        app.isChecking && !app.isCellCorrect(entry, idx) && app.getCellValue(entry, idx) && 'incorrect',
                      ].filter(Boolean).join(' ')}
                      onClick={(event) => {
                        event.stopPropagation();
                        app.focusInput(entry, idx);
                      }}
                    >
                      {app.getCellValue(entry, idx)}
                    </div>
                  ))}
                </div>

                {/* Hidden input for typing */}
                {app.activeEntry === entry && (
                  <input
                    ref={setHiddenInput}
                    type="text"
                    style={{ opacity: 0, position: 'absolute', pointerEvents: 'none' }}
                    onInput={(event) => app.handleInput(event)}
                    onKeyDown={(event) => app.handleKeydown(event)}
                  />
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Swap Request Modal */}
        {app.showSwapRequest && (
          <div className="modal-overlay">
            <div className="modal-card">
              <h3>Swap Requested!</h3>
              <p>Partner wants to swap roles.</p>
              <div className="modal-actions">
                <button className="btn-deny" onClick={() => { app.showSwapRequest = false; }}>No</button>{' '}
                <button className="btn-accept" onClick={() => app.confirmSwap()}>Yes</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
