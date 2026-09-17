import React from 'react';

// Vue-style class bindings, without a Vue runtime or additional DOM wrappers.
function classes(...values) {
    return values.map(value => {
        if (Array.isArray(value)) return classes(...value);
        if (value && typeof value === 'object') {
            return Object.keys(value).filter(key => value[key]).join(' ');
        }
        return value || '';
    }).filter(Boolean).join(' ');
}

export default function CrosswordView({ app }) {
    const clueClasses = entry => classes({
        'highlighted-clue': app.isActiveClue(entry),
        'affected-clue': app.isClueAffected(entry)
    });
    const answer = entry => Array.from(app.getCurrentAnswer(entry)).map((char, index) => (
        <span key={index} className={classes('state', {
            red: app.isChecking && char.toLowerCase() !== entry.characters[index].letters.toLowerCase() && char !== ' ',
            green: app.isChecking && char.toLowerCase() === entry.characters[index].letters.toLowerCase() && char !== ' ',
            'intersection-cell-across': app.activeDirection === 'across' && app.isCellInAffectedClue(entry, index),
            'intersection-cell-down': app.activeDirection === 'down' && app.isCellInAffectedClue(entry, index)
        })} onClick={event => app.handle_cell_click(event, entry, index)}>{char}</span>
    ));
    const selfClick = handler => event => {
        if (event.target === event.currentTarget) handler(event);
    };

    return (
        <div id="app" className={classes({ 'half-completed': app.isHalfCompleted })}>
            <div id="notmenu">
                <div className={classes('clue-column', { active: app.direction === 'across', inactive: app.direction !== 'across' })} data-label="ACROSS">
                    <ul id="across">
                        {app.crossword.filter(entry => entry.direction === 'across' && !app.completedWords.has(entry.clue_text)).map(entry => (
                            <li key={'across-' + entry.clue_number} onClick={event => app.handle_clue_click(event, entry)} className={clueClasses(entry)}>
                                <div className="clue-content">
                                    <span className="clue-text">{entry.clue_text}</span>
                                    <div className="state-container">{answer(entry)}</div>
                                </div>
                                <strong className="clue-number">{entry.clue_number}.</strong>
                            </li>
                        ))}
                    </ul>
                </div>

                <div className="center-column">
                    {/* Top Control Panel - Three Bars */}
                    <div id="menu-top" className="menu-section">
                        {/* Bar 1: Date and Authors */}
                        <div className="menu-row info-bar">
                            {app.currentPuzzleMetadata && <span className="puzzle-date">{app.formatDate(app.currentPuzzleMetadata.date)}</span>}
                            {app.currentPuzzleMetadata && <span className="puzzle-separator">•</span>}
                            {app.currentPuzzleMetadata && <span className="puzzle-weekday">{app.getCurrentDayName()}</span>}
                            {app.currentPuzzleMetadata && <span className="puzzle-separator">•</span>}
                            {app.currentPuzzleMetadata && <span className="puzzle-authors" data-full-text={app.currentPuzzleMetadata.authors.join(', ')}>{app.currentPuzzleMetadata.authors.join(', ')}</span>}
                            {Boolean(app.currentPuzzleMetadata && app.currentPuzzleMetadata.notepad) && (
                                <div className="puzzle-notepad">{app.currentPuzzleMetadata.notepad}</div>
                            )}
                        </div>

                        {/* Bar 2: Indicator Bar (Statistics) */}
                        <div className="menu-row indicator-bar">
                            <div className="stat-item blue-stat">
                                <span className="stat-label">Completed</span>
                                <span className="stat-value">{app.completedWords.size} / {app.crossword.length}</span>
                            </div>
                            <div className="stat-item blue-stat">
                                <span className="stat-label">Checks</span>
                                <span className="stat-value">{app.checksUsed}</span>
                            </div>
                            <div className="stat-item blue-stat">
                                <span className="stat-label">Reveals</span>
                                <span className="stat-value">{app.revealsUsed}</span>
                            </div>
                            <div className="stat-item orange-stat">
                                <span className="stat-label">Score</span>
                                <span className="stat-value">{app.score}</span>
                            </div>
                            <div className="stat-item orange-stat">
                                <span className="stat-label">Time</span>
                                <span className="stat-value">{app.formatTime(app.timer)}</span>
                            </div>
                        </div>

                        {/* Bar 3: Action Buttons */}
                        <div className="menu-row action-bar">
                            <button onClick={() => app.check_all()} id="check-all" className="action-button blue-action" title="Check all">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <circle cx="12" cy="12" r="10"></circle>
                                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                                </svg>
                                <span>Check</span>
                            </button>
                            <button onClick={() => app.revealAll()} id="reveal-all" className="action-button blue-action" title="Reveal all">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                    <circle cx="12" cy="12" r="3"></circle>
                                </svg>
                                <span>Reveal</span>
                            </button>
                            {app.currentPuzzleMetadata && (
                                <a href={app.getXWordInfoLink()} target="_blank" rel="noopener noreferrer" className="action-button center-action" title="View on XWord Info">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <circle cx="12" cy="12" r="10"></circle>
                                        <line x1="12" y1="16" x2="12" y2="12"></line>
                                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                                    </svg>
                                    <span>Solution</span>
                                </a>
                            )}
                            <button onClick={() => app.markCurrentPuzzleAsComplete()} id="complete-button" className="action-button orange-action" title="Mark as Complete">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                </svg>
                                <span>Complete</span>
                            </button>
                        </div>
                    </div>

                    {/* Crossword Grid */}
                    <div id="crossword-container">
                        <div className="grid" style={{ gridTemplateRows: `repeat(${app.grid.length}, var(--cell-size))` }}>
                            {app.grid.map((row, rowIndex) => (
                                <div className="grid-row" key={rowIndex} style={{ gridTemplateColumns: `repeat(${row.length}, var(--cell-size))` }}>
                                    {row.map((cell, cellIndex) => (
                                        <div key={cellIndex} className={classes('grid-cell', app.getCellClasses(rowIndex, cellIndex), {
                                            'black-cell': cell === null,
                                            'highlighted-cell': app.isCellInActiveEntry(rowIndex, cellIndex)
                                        })}>
                                            {Boolean(app.find_index(rowIndex, cellIndex)) && <span className="clue-index">{app.find_index(rowIndex, cellIndex)}</span>}
                                            {cell !== null && (
                                                <>
                                                    <input ref={element => { app.setRef('input-' + rowIndex + '-' + cellIndex, element); }} type="text"
                                                        maxLength={app.isRebus(cellIndex, rowIndex) ? 10 : 1}
                                                        value={app.grid[rowIndex][cellIndex]}
                                                        onChange={event => { app.grid[rowIndex][cellIndex] = event.target.value; }}
                                                        onClick={() => app.handle_grid_cell_click(rowIndex, cellIndex)}
                                                        onKeyDown={event => app.handle_crossword_cell_keydown(event, rowIndex, cellIndex)}
                                                        onContextMenu={event => app.handle_crossword_cell_contextmenu(event, rowIndex, cellIndex)}
                                                        data-row={rowIndex} data-cell={cellIndex}
                                                        data-solution={app.find_solution(rowIndex, cellIndex)}
                                                        aria-label={'grid cell ' + rowIndex + '-' + cellIndex} />
                                                    {Boolean(app.isRebus(cellIndex, rowIndex)) && <span className="rebus-indicator">{app.getRebusCount(cellIndex, rowIndex)}</span>}
                                                </>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Bottom Control Panel */}
                    <div id="menu-bottom" className="menu-section">
                        <div className="menu-row selection-row">
                            <div className="field-group weekday-group">
                                <label className="field-label" htmlFor="weekday-select">Weekday</label>
                                <div className="select-wrapper">
                                    <select id="weekday-select" value={app.selectedWeekday} onChange={event => { app.selectedWeekday = event.target.value; }}>
                                        {app.weekdayOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                                    </select>
                                </div>
                            </div>
                            <button onClick={() => app.loadSelectedWeekday()} id="get-puzzle-button" aria-label="Get new puzzle">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="feather feather-arrow-right-circle">
                                    <circle cx="12" cy="12" r="10"></circle>
                                    <polyline points="12 16 16 12 12 8"></polyline>
                                    <line x1="8" y1="12" x2="16" y2="12"></line>
                                </svg>
                            </button>
                            <div className="menu-spacer"></div>
                            <button onClick={() => app.openSolvedModal()} id="overview-button" className="icon-button" title="Overview">
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                    <line x1="3" y1="9" x2="21" y2="9"></line>
                                    <line x1="9" y1="21" x2="9" y2="9"></line>
                                </svg>
                            </button>
                            <button onClick={() => app.openCacheModal()} id="cache-button" className="icon-button" title="Cache Status">
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                                    <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                                    <line x1="12" y1="22.08" x2="12" y2="12"></line>
                                </svg>
                            </button>
                            <button onClick={() => app.openMultiplayerModal()} id="multiplayer-button" className="icon-button" title="Multiplayer">
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                                    <circle cx="9" cy="7" r="4"></circle>
                                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                                    <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                                </svg>
                            </button>
                            <div className="theme-switch">
                                <label className="switch">
                                    <input type="checkbox" checked={app.isDarkMode} onChange={event => {
                                        app.isDarkMode = event.target.checked;
                                        app.toggle_night_mode(event);
                                    }} aria-label="Toggle dark mode" />
                                    <svg className="theme-icon" aria-hidden="true" width="24" height="24" viewBox="0 0 24 24">
                                        <mask id="moon-mask">
                                            <rect x="0" y="0" width="100%" height="100%" fill="white" />
                                            <circle className="mask-circle" cx="25" cy="12" r="8" fill="black" />
                                        </mask>
                                        <circle className="sun-disc" cx="12" cy="12" r="8" mask="url(#moon-mask)" fill="currentColor" />
                                        <g className="sun-beams" stroke="currentColor">
                                            <line x1="12" y1="1" x2="12" y2="3" />
                                            <line x1="12" y1="21" x2="12" y2="23" />
                                            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                                            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                                            <line x1="1" y1="12" x2="3" y2="12" />
                                            <line x1="21" y1="12" x2="23" y2="12" />
                                            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                                            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                                        </g>
                                    </svg>
                                </label>
                            </div>
                        </div>
                    </div>
                </div>

                <div className={classes('clue-column', { active: app.direction === 'down', inactive: app.direction !== 'down' })} data-label="DOWN">
                    <ul id="down">
                        {app.crossword.filter(entry => entry.direction === 'down' && !app.completedWords.has(entry.clue_text)).map(entry => (
                            <li key={'down-' + entry.clue_number} onClick={event => app.handle_clue_click(event, entry)} className={clueClasses(entry)}>
                                <strong className="clue-number">{entry.clue_number}.</strong>
                                <div className="clue-content">
                                    <span className="clue-text">{entry.clue_text}</span>
                                    <div className="state-container">{answer(entry)}</div>
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>

            {/* Solved Puzzles Modal */}
            {app.showSolvedModal && (
                <div className="modal-overlay" onClick={selfClick(app.closeSolvedModal)}>
                    <div className="modal-content">
                        <div className="modal-header">
                            <h2>Solved Puzzles</h2>
                            <button onClick={app.closeSolvedModal} className="modal-close-button">&times;</button>
                        </div>
                        <div className="modal-body">
                            {Object.entries(app.solvedPuzzlesList).map(([dayKey, solvedEntries]) => (
                                <div key={dayKey} className="solved-day-section">
                                    {solvedEntries.length > 0 && <h3>{dayKey.charAt(0).toUpperCase() + dayKey.slice(1)} ({solvedEntries.length})</h3>}
                                    {solvedEntries.length > 0 && (
                                        <ul className="solved-puzzles-list">
                                            {solvedEntries.map((puzzle, index) => (
                                                <li key={puzzle.id + '-' + index} className="solved-puzzle-item">
                                                    <div className="puzzle-info">
                                                        <div className="puzzle-header">
                                                            <strong className="puzzle-title">{puzzle.title || 'Untitled Puzzle'}</strong>
                                                            <span className="puzzle-date">{puzzle.id}</span>
                                                        </div>
                                                        <div className="puzzle-authors">
                                                            <em>{puzzle.authors && puzzle.authors.length > 0 ? puzzle.authors.join(', ') : 'Unknown Author'}</em>
                                                        </div>
                                                        <div className="puzzle-stats">
                                                            {puzzle.score !== null && puzzle.score !== undefined && <span className="stat"><strong>Score:</strong> {puzzle.score}</span>}
                                                            {Boolean(puzzle.timeTaken) && <span className="stat"><strong>Time:</strong> {app.formatTime(puzzle.timeTaken)}</span>}
                                                            <span className="stat"><strong>Completed:</strong> {new Date(puzzle.dateSolved).toLocaleDateString()}</span>
                                                        </div>
                                                    </div>
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                    {solvedEntries.length === 0 && dayKey !== 'saturday' && dayKey !== 'sunday' && <p>No puzzles solved for {dayKey}.</p>}
                                </div>
                            ))}
                            {Object.values(app.solvedPuzzlesList).every(list => list.length === 0) && <p>You haven't solved any puzzles yet!</p>}
                        </div>
                    </div>
                </div>
            )}

            {/* Cache Status Modal */}
            {app.showCacheModal && (
                <div className="modal-overlay" onClick={selfClick(app.closeCacheModal)}>
                    <div className="modal-content">
                        <div className="modal-header">
                            <h2>Cache Status</h2>
                            <button onClick={app.closeCacheModal} className="modal-close-button">&times;</button>
                        </div>
                        <div className="modal-body">
                            <div className="cache-status-section">
                                <h3>Cached Puzzles</h3>
                                <ul className="cache-list">
                                    {Object.entries(app.cachedCrosswordsCount).map(([day, count]) => (
                                        <li key={day} className="cache-item">
                                            <span className="cache-day">{day.charAt(0).toUpperCase() + day.slice(1)}</span>
                                            <div className="cache-progress">
                                                <div className="cache-progress-bar" style={{ width: (count / 50 * 100) + '%' }}></div>
                                            </div>
                                            <span className="cache-count">{count} / 50</span>
                                        </li>
                                    ))}
                                </ul>
                                <div className="cache-actions">
                                    <button onClick={() => app.manuallyStartCaching()} className="action-button blue-action" disabled={app.isCachingInProgress}>
                                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <polyline points="23 4 23 10 17 10"></polyline>
                                            <polyline points="1 20 1 14 7 14"></polyline>
                                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                                        </svg>
                                        {!app.isCachingInProgress ? <span>Start Caching</span> : <span>Caching...</span>}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Multiplayer Modal */}
            {app.showMultiplayerModal && (
                <div className="modal-overlay" onClick={selfClick(app.closeMultiplayerModal)}>
                    <div className="modal-content" style={{ maxWidth: '600px' }}>
                        <div className="modal-header">
                            <h2>Multiplayer Setup</h2>
                            <button onClick={app.closeMultiplayerModal} className="modal-close-button">&times;</button>
                        </div>
                        <div className="modal-body">
                            {!app.multiplayerRoomId ? (
                                <div className="multiplayer-start">
                                    <p>Start a multiplayer session to play with friends on mobile devices.</p>
                                    <button onClick={() => app.startMultiplayerSession()} className="action-button blue-action" style={{ width: '100%', justifyContent: 'center', marginTop: '20px' }}>
                                        Start Session
                                    </button>
                                </div>
                            ) : (
                                <div className="multiplayer-lobby">
                                    <div className="lobby-header">
                                        <span className="room-code">Room: <strong>{app.multiplayerRoomId}</strong></span>
                                        <button onClick={() => app.createHotspot()} className="action-button orange-action" title="Open System Settings">
                                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <path d="M5 12.55a11 11 0 0 1 14.08 0"></path>
                                                <path d="M1.42 9a16 16 0 0 1 21.16 0"></path>
                                                <path d="M8.53 16.11a6 6 0 0 1 6.95 0"></path>
                                                <line x1="12" y1="20" x2="12.01" y2="20"></line>
                                            </svg>
                                            <span>WiFi Hotspot</span>
                                        </button>
                                    </div>
                                    <div className="qr-container" style={{ display: 'flex', justifyContent: 'space-around', marginTop: '20px' }}>
                                        <div className="qr-item" style={{ textAlign: 'center' }}>
                                            <h3>Player 1 (Across)</h3>
                                            {app.qrAcross ? <img src={app.qrAcross} style={{ width: '150px', height: '150px', border: '1px solid #ccc' }} /> : <div>Loading...</div>}
                                        </div>
                                        <div className="qr-item" style={{ textAlign: 'center' }}>
                                            <h3>Player 2 (Down)</h3>
                                            {app.qrDown ? <img src={app.qrDown} style={{ width: '150px', height: '150px', border: '1px solid #ccc' }} /> : <div>Loading...</div>}
                                        </div>
                                    </div>
                                    <p style={{ textAlign: 'center', marginTop: '20px', color: '#666' }}>
                                        Scan the QR codes to join. Ensure devices are on the same Wi-Fi.
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Rebus Context Menu */}
            {app.showRebusMenu && (
                <div className="rebus-context-menu" style={{ left: app.rebusMenuPosition.x + 'px', top: app.rebusMenuPosition.y + 'px', transform: 'translateX(-50%)' }} onClick={event => event.stopPropagation()}>
                    <div className="rebus-context-menu-header">Enter Rebus Answer</div>
                    <input type="text" className="rebus-context-menu-input" value={app.rebusInputValue}
                        onChange={event => { app.rebusInputValue = event.target.value; }}
                        onKeyDown={event => app.handleRebusMenuKeydown(event)} placeholder="Type letters..." maxLength={10} />
                    <div className="rebus-context-menu-hint">Press Enter to save, Esc to cancel</div>
                    <div className="rebus-context-menu-buttons">
                        <button className="rebus-context-menu-button cancel" onClick={() => app.closeRebusMenu()}>Cancel</button>
                        <button className="rebus-context-menu-button" onClick={() => app.saveRebusValue()}>Save</button>
                    </div>
                </div>
            )}

            {/* Fireworks Canvas Overlay: v-show keeps the canvas mounted. */}
            <canvas id="fireworks-canvas" style={{ display: app.showFireworks ? undefined : 'none' }}></canvas>
        </div>
    );
}
