import React, { useEffect, useMemo, useRef, useState } from 'react';
import './desktop.css';
import './vision.css';
import './celebration.css';
import './combo.css';
import ViewControls from './ViewControls';
import ClueSpring from './ClueSpring';
import { Finale, RaptureLayer } from './Rapture';
import { useRapture } from './useRapture';
import ComboMeter from './ComboMeter';
import Volley from './Volley';
import { comboHeat } from './combo';
import GlassLayer from './glass/GlassLayer';
import { createSelectionPresentation } from './selectionPresentation';
import { cellCues, clueRampStyle, createClueRamp, entryStartingAt, groupRuns, spotlightCues, wordsThroughSquares } from './boardCues';
import { normalizeViewSettings, readViewSettings, VIEW_DEFAULTS, viewAttributes, writeViewSettings } from './viewSettings';
import { normalizeFutureKey } from './future/languageInput';
import { entryKey } from './entryKey';

export function displayedPuzzleWeekday(app, displayWeekday) {
    return displayWeekday || app.getCurrentDayName();
}

const CLUE_SIGNAL_PATTERN = /("[^"\n]+"|“[^”\n]+”|'[^'\n]+'|‘[^’\n]+’|(?:\[|\()\s*pl\.?\s*(?:\]|\))|(?:\[|\()\s*(?:past|present|future)(?:\s+tense)?\s*(?:\]|\))|\b(?:past|present|future)\s+tense\b|\[[^\n]+\]|\?+|_{3,}|\.{3,}|…+|\b(?:abbr\.?|briefly|initially)\b)/gi;

const CLUE_SIGNAL_COPY = {
    quote: 'Quotation marks signal something that can be said aloud.',
    bracket: 'Brackets describe a sound, gesture, or editorial aside.',
  question: 'A question mark allows a playful or indirect reading.',
  blank: 'A blank marks a missing part of a phrase.',
  plural: 'A plural marker says the answer should be plural.',
  tense: 'A tense marker says the answer should match that verb tense.',
  abbreviation: 'This marker signals a shortened answer.',
};

function clueSignalKind(value) {
  if (/^["“'‘]/.test(value)) return 'quote';
  if (/^(?:\[|\()\s*pl\.?\s*(?:\]|\))$/i.test(value)) return 'plural';
  if (/^(?:(?:\[|\()\s*)?(?:past|present|future)(?:\s+tense)?\s*(?:(?:\]|\))?)$|\btense\b/i.test(value)) return 'tense';
    if (value.startsWith('[')) return 'bracket';
    if (/^\?+$/.test(value)) return 'question';
    if (/^(?:_+|\.{3,}|…+)$/.test(value)) return 'blank';
    return 'abbreviation';
}

export function renderClueSurface(text, annotate = false) {
    if (!annotate || typeof text !== 'string') return text;
    const parts = [];
    let cursor = 0;
    for (const match of text.matchAll(CLUE_SIGNAL_PATTERN)) {
        const value = match[0];
        const index = match.index ?? cursor;
        if (index > cursor) parts.push(text.slice(cursor, index));
        const kind = clueSignalKind(value);
        parts.push(
            <span
                key={`${kind}-${index}`}
                className={`clue-signal clue-signal-${kind}`}
                data-clue-signal={kind}
                tabIndex={0}
                aria-label={`${value}: ${CLUE_SIGNAL_COPY[kind]}`}
                title={CLUE_SIGNAL_COPY[kind]}
            >
                {value}
            </span>,
        );
        cursor = index + value.length;
    }
    if (cursor < text.length) parts.push(text.slice(cursor));
    return parts.length ? parts : text;
}

// Conditional class bindings, without additional DOM wrappers.
function classes(...values) {
    return values.map(value => {
        if (Array.isArray(value)) return classes(...value);
        if (value && typeof value === 'object') {
            return Object.keys(value).filter(key => value[key]).join(' ');
        }
        return value || '';
    }).filter(Boolean).join(' ');
}

export default function CrosswordView({
    app,
    languageInput = null,
    onEntryFocused = undefined,
    onCellChanged = undefined,
    onCheckAll = undefined,
    onRevealAll = undefined,
    onCellRevealed = undefined,
    onComplete = undefined,
    displayWeekday = undefined,
    annotateClueGrammar = false,
}) {
    const [cursorCell, setCursorCell] = useState(null);
    // The optional GPU glass layer (glass/): which backend is drawing, if any.
    const [glass, setGlass] = useState(/** @type {'webgpu' | 'webgl2' | null} */ (null));
    const [rebusDisplayValue, setRebusDisplayValue] = useState('');
    const inputSources = useRef(new Map());
    const boardRef = useRef(/** @type {HTMLDivElement | null} */ (null));
    const glowRef = useRef(/** @type {HTMLDivElement | null} */ (null));
    const acrossRef = useRef(/** @type {HTMLUListElement | null} */ (null));
    const downRef = useRef(/** @type {HTMLUListElement | null} */ (null));
    const scheduleTerritory = useRef(() => {});
    // Reader-adjustable view settings: presentation only, kept in local storage,
    // and published to the board root as data-* attributes so that vision.css can
    // own every visual consequence (see viewSettings.js). A first visit on a
    // display that reports low contrast or reduced transparency starts on the dim
    // tier rather than at full bloom; the reader can move it from there.
    const browserStorage = typeof window === 'undefined' ? null : window.localStorage;
    const [settings, setSettings] = useState(() => readViewSettings({
        storage: browserStorage,
        media: typeof window === 'undefined' ? null : window.matchMedia?.bind(window)
    }));
    const changeSettings = next => {
        const normalized = normalizeViewSettings(next);
        setSettings(normalized);
        writeViewSettings(normalized, { storage: browserStorage });
    };
    const describeRebusInput = value => {
        const normalized = languageInput?.normalizeRebus
            ? languageInput.normalizeRebus(value)
            : languageInput?.normalizeForCell(value, { isRebus: true });
        return normalized?.accepted
            ? normalized
            : { accepted: false, display: value, fill: value };
    };
    // Read-once locals for the render below: every app.* access crosses the
    // controller's observable proxy, so the hot loops work from these instead of
    // paying the trap per square and per letter. Event handlers keep reading
    // live controller state; these are only the render's snapshot.
    const grid = app.grid;
    const entries = app.crossword || [];
    const isChecking = app.isChecking;
    const completedWords = app.completedWords;
    const tokenCells = app.currentPuzzleTokenManifest?.cells ?? null;
    const entryContainsCell = (entry, rowIndex, cellIndex) => entry?.characters.some((_, index) => (
        entry.direction === 'across'
            ? entry.start_y === rowIndex && entry.start_x + index === cellIndex
            : entry.start_x === cellIndex && entry.start_y + index === rowIndex
    ));
    const entryAtCell = (rowIndex, cellIndex, direction = app.direction) => {
        const directional = (app.crossword || []).find(entry => {
        if (entry.direction !== direction) return false;
        return entryContainsCell(entry, rowIndex, cellIndex);
        });
        if (directional) return directional;
        const active = app.activeClueNumber && app.activeDirection
            ? app.getEntryByClueNumber(app.activeClueNumber, app.activeDirection)
            : null;
        return entryContainsCell(active, rowIndex, cellIndex) ? active : null;
    };
    // Future token manifests keep canonical fill values in the controller,
    // while this view can show the declared display grapheme. The lookup is
    // inert for the daily route, which has no token manifest.
    const tokenAt = (rowIndex, cellIndex) => tokenCells?.find(cell => (
        cell.row === rowIndex && cell.column === cellIndex
    )) || null;
    const displayGridValue = (value, rowIndex, cellIndex) => {
        if (value === null || value === undefined || value === '') return value;
        const token = tokenAt(rowIndex, cellIndex);
        if (token && token.fillToken !== String(value)) return value;
        return token?.displayToken || value;
    };
    const rebusRow = app.rebusMenuCell?.row ?? -1;
    const rebusColumn = app.rebusMenuCell?.col ?? -1;
    useEffect(() => {
        if (!app.showRebusMenu || rebusRow < 0 || rebusColumn < 0) {
            setRebusDisplayValue('');
            return;
        }
        const canonical =
            app.rebusInputValue || app.grid?.[rebusRow]?.[rebusColumn] || '';
        setRebusDisplayValue(
            displayGridValue(canonical, rebusRow, rebusColumn) || canonical,
        );
    }, [
        app.showRebusMenu,
        app.rebusInputValue,
        rebusRow,
        rebusColumn,
        app.currentPuzzleTokenManifest,
    ]);
    const gridValues = () => new Map(grid.flatMap((row, rowIndex) => row.flatMap((value, cellIndex) => (
        value === null ? [] : [[`r${rowIndex}c${cellIndex}`, value ? String(value) : null]]
    ))));
    const clueClasses = entry => classes({
        'highlighted-clue': app.isActiveClue(entry),
        'affected-clue': isClueAffected(entry)
    });
    const activeEntry = app.activeClueNumber && app.activeDirection
        ? app.getEntryByClueNumber(app.activeClueNumber, app.activeDirection)
        : null;
    // Best-effort glow: the selection's light (blurred shadows, its ignition
    // animations) is the most expensive paint on the board, so a fresh
    // selection first lands without it — cursor, letters and washes stay
    // live on the cheap first frame — and the glow catches up a couple of
    // frames later. Fast repeated navigation cancels the catch-up and
    // re-arms it, so the glow never blocks the cursor; it settles in when
    // the reader pauses. Keystrokes inside a word never change the key, so
    // typing never dims the light.
    const selectionKey = `${app.activeClueNumber}|${app.activeDirection}`;
    const [litKey, setLitKey] = useState(selectionKey);
    useEffect(() => {
        if (litKey === selectionKey) return undefined;
        if (typeof requestAnimationFrame === 'undefined') {
            setLitKey(selectionKey);
            return undefined;
        }
        let first = 0;
        let second = 0;
        first = requestAnimationFrame(() => {
            second = requestAnimationFrame(() => setLitKey(selectionKey));
        });
        return () => {
            cancelAnimationFrame(first);
            cancelAnimationFrame(second);
        };
    }, [litKey, selectionKey]);
    const glowOn = litKey === selectionKey;
    const selection = createSelectionPresentation(activeEntry);
    // A lit square carries the active entry's rank alongside its coordinate, so
    // every representation of the selection — board squares and answer boxes —
    // glows in the hue of the clue being solved.
    const cellPresentation = (rowIndex, cellIndex) => {
        const cell = selection.get(`${rowIndex},${cellIndex}`);
        if (!cell || !activeEntry) return {};
        const active = settings.ramp ? clueRampStyle(clueRamp, activeEntry.clue_number) : {};
        return { style: { ...cell.style, ...active }, 'data-entry-index': cell.index, title: cell.title };
    };
    const activeEntryCellClasses = (rowIndex, cellIndex) => {
        const cell = selection.get(`${rowIndex},${cellIndex}`);
        if (!cell) return {};
        const entryIndex = cell.index;
        return {
            'active-entry-across': activeEntry.direction === 'across',
            'active-entry-down': activeEntry.direction === 'down',
            'active-entry-start': entryIndex === 0,
            'active-entry-end': entryIndex === activeEntry.characters.length - 1
        };
    };
    // One hue per distinct clue number, spread across the arc by rank rather than
    // by value: the ladder anchor and the square index at that number read as the
    // same colour, so a hue is learned once and points at the board either way.
    const clueRamp = useMemo(() => createClueRamp(app.crossword), [app.crossword]);
    // Where each numbered square starts, first entry wins — the same answer
    // app.find_index gives, without scanning the entries per square per render.
    const startNumbers = useMemo(() => {
        const starts = new Map();
        for (const entry of entries) {
            const key = `${entry.start_y},${entry.start_x}`;
            if (!starts.has(key)) starts.set(key, entry.clue_number);
        }
        return starts;
    }, [entries]);
    // How many words run through each square, so a solved square can tell
    // whether it is finished with (every word through it is solved) or still
    // lends its letter to an open crossing word.
    const wordsThroughSquare = useMemo(() => wordsThroughSquares(entries), [entries]);
    // The opposite-lane clues the active word crosses, as a set of
    // `direction:clue_number` keys. app.isClueAffected rebuilds this from nested
    // scans on every call — once per row, several times per render — so it is
    // built once per selection here and probed as a set below. Same membership,
    // same null guards, no repeated work.
    const affectedKeys = useMemo(() => {
        const keys = new Set();
        if (!activeEntry) return keys;
        const opposite = activeEntry.direction === 'across' ? 'down' : 'across';
        const byCell = new Map();
        for (const entry of entries) {
            if (entry.direction !== opposite) continue;
            const length = entry.characters.length;
            for (let index = 0; index < length; index++) {
                const x = opposite === 'across' ? entry.start_x + index : entry.start_x;
                const y = opposite === 'across' ? entry.start_y : entry.start_y + index;
                const key = `${x},${y}`;
                let list = byCell.get(key);
                if (!list) { list = []; byCell.set(key, list); }
                list.push(entry);
            }
        }
        const length = activeEntry.characters.length;
        for (let index = 0; index < length; index++) {
            const x = activeEntry.direction === 'across' ? activeEntry.start_x + index : activeEntry.start_x;
            const y = activeEntry.direction === 'across' ? activeEntry.start_y : activeEntry.start_y + index;
            for (const entry of byCell.get(`${x},${y}`) || []) {
                keys.add(`${entry.direction}:${entry.clue_number}`);
            }
        }
        return keys;
    }, [entries, activeEntry]);
    const isClueAffected = entry => affectedKeys.has(`${entry.direction}:${entry.clue_number}`);
    // The neighbour-derived cues for every square — edge slots, gate ticks,
    // spotlight distances — depend only on the puzzle definition, never on the
    // selection or the typed letters, so they are walked once per load and read
    // back per square instead of re-walked on every render.
    const staticCues = useMemo(() => {
        const cues = new Map();
        const rows = grid.length;
        const columns = grid[0]?.length || 0;
        for (let rowIndex = 0; rowIndex < rows; rowIndex++) {
            for (let cellIndex = 0; cellIndex < columns; cellIndex++) {
                const cuesForCell = cellCues(grid, rowIndex, cellIndex);
                const gates = {};
                if (cuesForCell.style && ('--open-e' in cuesForCell.style || '--open-s' in cuesForCell.style)) {
                    // A gate tick names the word it opens: the east tick the Across
                    // word starting to the east, the south tick the Down word starting
                    // below. Stubs that open no word publish nothing and keep the
                    // quiet direction colour (section 4 of vision.css).
                    const east = entryStartingAt(entries, rowIndex, cellIndex + 1, 'across');
                    const south = entryStartingAt(entries, rowIndex + 1, cellIndex, 'down');
                    const eastRank = east ? clueRamp.get(east.clue_number) : undefined;
                    const southRank = south ? clueRamp.get(south.clue_number) : undefined;
                    if (eastRank !== undefined) gates['--gate-across'] = String(eastRank);
                    if (southRank !== undefined) gates['--gate-down'] = String(southRank);
                }
                const spot = spotlightCues(grid, entries, clueRamp, rowIndex, cellIndex);
                // The pieces stay separate so the render can withhold the
                // rank-derived ones (gates, spotlight) while Number colours are
                // off, exactly as the per-square guards used to.
                cues.set(`${rowIndex},${cellIndex}`, {
                    style: cuesForCell.style,
                    gates,
                    spot: spot.style,
                    dataStart: cuesForCell.dataStart
                });
            }
        }
        return cues;
    }, [entries, clueRamp, grid.length, grid[0]?.length]);
    // The clues still on the ladder: a solved clue leaves it, and the springs
    // follow the same list so the chips either side of the gap are joined directly.
    // Clues a check has just solved are held a moment so they can celebrate.
    const rapture = useRapture(app, { boardRef });
    const held = rapture.active?.holding ? rapture.active.order : undefined;
    // While a check plays back, the board is drawn as it stood before it: the
    // sequence paints its steps onto the few squares and boxes involved, and
    // the state that restyles most of the page (solved squares, the root's
    // light, the boxes' verdicts) lands once, at the end (useRapture.js).
    const shown = rapture.active?.busy ? rapture.active.shown : null;
    const settledWords = shown ? shown.completed : completedWords;
    const shownScore = shown ? shown.score : app.score;
    const shownCombo = shown ? shown.combo : app.combo;
    const showVerdicts = isChecking && !shown;
    const laneEntries = direction => entries.filter(entry => entry.direction === direction && (!completedWords.has(entryKey(entry)) || held?.has(entryKey(entry))));
    // The row carries its own rank next to the chip it already sits beside, so
    // the answer track and every glow on the row read the same hue as the
    // number. The pigment only travels while the reader has Number colours on.
    // (A row a check solves is popped by the sequence itself, at its beat:
    // useRapture marks it directly, so the hold costs no restyle here.)
    const rowProps = entry => (settings.ramp ? { style: clueRampStyle(clueRamp, entry.clue_number) } : {});
    const springState = entry => (app.isActiveClue(entry) ? 'active' : isClueAffected(entry) ? 'affected' : '');
    const laneSprings = (direction, entries) => settings.rail && (
        <ClueSpring
            lane={direction}
            ramp={clueRamp}
            numbers={entries.map(entry => entry.clue_number)}
            states={entries.map(springState)}
        />
    );
    // Everything a square needs to be drawn: the selection styling the controller
    // already knows about, plus the neighbour-derived cues. JS only names what a
    // square is (where a word starts, which black squares open a slot); the
    // appearance belongs to vision.css. The static cues are precomputed per
    // puzzle above; the per-square work here is map lookups, not walks.
    // The board's libido: one charge of light shared by the notches still
    // open. As words are solved their notches go out and the charge flows into
    // the ones that remain, which burn brighter (vision.css section 11); every
    // check and reveal drains the whole charge with the score.
    let solvedCount = 0;
    // What the solve has closed, per square: the directions of the solved words
    // a square belongs to, and on a black square which of the words it opens
    // are solved. vision.css lets a solved word settle into the board and its
    // notch close down to a single remaining point (section 11). Derived from
    // the controller's completed words on every render; nothing is stored.
    const solvedSquares = new Map();
    const solvedOpenings = new Set();
    for (const entry of entries) {
        if (!settledWords.has(entryKey(entry))) continue;
        solvedOpenings.add(`${entry.start_y},${entry.start_x},${entry.direction}`);
        solvedCount += 1;
        entry.characters.forEach((_, index) => {
            const key = entry.direction === 'across'
                ? `${entry.start_y},${entry.start_x + index}`
                : `${entry.start_y + index},${entry.start_x}`;
            solvedSquares.set(key, [...(solvedSquares.get(key) || []), entry.direction]);
        });
    }
    const solvedProps = (rowIndex, cellIndex) => {
        const key = `${rowIndex},${cellIndex}`;
        const directions = solvedSquares.get(key);
        if (directions) {
            const solved = ['across', 'down'].filter(direction => directions.includes(direction));
            // Settled: no open word is left through this square, so vision.css
            // can quiet its letter fully; a square an open word still crosses
            // keeps most of its contrast, because that letter is a clue there.
            const settled = solved.length >= (wordsThroughSquare.get(key) || 1);
            return { 'data-solved': solved.join(' '), ...(settled ? { 'data-solved-all': '' } : {}) };
        }
        const closed = [
            solvedOpenings.has(`${rowIndex},${cellIndex + 1},across`) && 'e',
            solvedOpenings.has(`${rowIndex + 1},${cellIndex},down`) && 's',
        ].filter(Boolean);
        return closed.length && grid[rowIndex]?.[cellIndex] === null ? { 'data-gate-solved': closed.join(' ') } : {};
    };
    const gridCellProps = (rowIndex, cellIndex) => {
        const presentation = { ...cellPresentation(rowIndex, cellIndex), ...solvedProps(rowIndex, cellIndex) };
        // A numbered square wears its own clue's rank; the selection style is
        // spread over it afterwards, so a lit square shows the active clue's
        // hue instead — interaction over identity, on the same property.
        const clueNumber = settings.ramp ? startNumbers.get(`${rowIndex},${cellIndex}`) ?? null : null;
        const style = { ...(clueNumber ? clueRampStyle(clueRamp, clueNumber) : {}), ...presentation.style };
        const withStyle = Object.keys(style).length > 0 ? { style } : {};
        if (!settings.cues) return { ...presentation, ...withStyle };
        const cached = staticCues.get(`${rowIndex},${cellIndex}`);
        return {
            ...presentation,
            ...withStyle,
            style: {
                ...style,
                ...cached?.style,
                ...(settings.ramp ? cached?.gates : null),
                ...(settings.ramp ? cached?.spot : null)
            },
            'data-start': cached?.dataStart
        };
    };
    const isCursorCell = (entry, index) => {
        if (!cursorCell) return false;
        const rowIndex = entry.direction === 'across' ? entry.start_y : entry.start_y + index;
        const cellIndex = entry.direction === 'across' ? entry.start_x + index : entry.start_x;
        return cursorCell.rowIndex === rowIndex && cursorCell.cellIndex === cellIndex;
    };
    // Whether one box of an opposite-lane row sits on the active word: the
    // selection map already answers it, so this is a coordinate lookup instead
    // of the controller's per-letter scan. Same guards (no active word, or the
    // row's own lane, is never a crossing).
    const isCellInActiveSelection = (entry, index) => {
        if (!activeEntry || entry.direction === activeEntry.direction) return false;
        const x = entry.direction === 'across' ? entry.start_x + index : entry.start_x;
        const y = entry.direction === 'across' ? entry.start_y : entry.start_y + index;
        return selection.has(`${y},${x}`);
    };
    const answer = entry => {
        const letters = entry.characters.map((character, index) => {
            const row = entry.start_y + (entry.direction === 'down' ? index : 0);
            const col = entry.start_x + (entry.direction === 'across' ? index : 0);
            const rawChar = grid[row]?.[col] || ' ';
            const char = displayGridValue(rawChar, row, col) || ' ';
            return <span key={index} {...cellPresentation(row, col)} data-cell={`${row},${col}`} className={classes('state', {
                red: showVerdicts && rawChar.toLowerCase() !== character.letters.toLowerCase() && rawChar !== ' ',
                green: showVerdicts && rawChar.toLowerCase() === character.letters.toLowerCase() && rawChar !== ' ',
                'intersection-cell-across': app.activeDirection === 'across' && isCellInActiveSelection(entry, index),
                'intersection-cell-down': app.activeDirection === 'down' && isCellInActiveSelection(entry, index),
                'cursor-cell': isCursorCell(entry, index),
                shaded: Boolean(app.getCell(col, row)?.is_shaded),
                'rebus-state': rawChar.length > 1
            })} onClick={event => {
                app.handle_cell_click(event, entry, index);
                onEntryFocused?.(entry, 'pointer');
            }}>{char}</span>;
        });
        // Grouping follows the answer, not a counter: runs break where the answer
        // has a real word gap and balance to at most five letters elsewhere, and a
        // track that has to wrap breaks between runs instead of through one. A run
        // set that disagrees with the cells about the length - a rebus carrying a
        // word gap inside a single box, say - stays one run rather than inventing
        // boundaries the answer does not have.
        const runs = groupRuns(entry, settings.grouping);
        const sized = runs.reduce((total, run) => total + run.size, 0);
        const grouped = sized === letters.length ? runs : [{ size: letters.length, wordEnd: false }];
        if (!letters.length) return letters;
        let taken = 0;
        return grouped.map((run, runIndex) => {
            const slice = letters.slice(taken, taken + run.size);
            taken += run.size;
            return <span key={runIndex} className={classes('state-run', { 'word-end': run.wordEnd })}>{slice}</span>;
        });
    };
    // The board takes on the territory: each corner of the grid is lit from
    // behind in the hue of the clue showing in that corner of the screen, so
    // the middle says where the reader is in each lane - the yellow and purple
    // corners, or the blue and green ones. Written straight onto the grid's
    // style on scroll (one frame at most per burst), never through a React
    // render; vision.css owns how much light that becomes. Without number
    // colours the rows carry no rank and the board keeps its plain edge.
    useEffect(() => {
        const panel = boardRef.current;
        const across = acrossRef.current;
        const down = downRef.current;
        if (!panel || !across || !down || typeof requestAnimationFrame === 'undefined') return undefined;
        /** @type {Array<[string, HTMLUListElement]>} */
        const lanes = [['across', across], ['down', down]];
        let frame = 0;
        const rankOf = row => {
            const value = Number.parseFloat(row?.style.getPropertyValue('--clue-ramp') ?? '');
            return Number.isFinite(value) ? value : null;
        };
        // The grid wears the territory on its edge, the glow layer as the light
        // behind it; each reads the ranks from its own style.
        const wearers = [panel, glowRef.current].filter(element => element instanceof HTMLElement);
        const publish = (name, value) => {
            const next = value === null ? null : String(Math.round(value * 100) / 100);
            for (const wearer of wearers) {
                const current = wearer.style.getPropertyValue(name);
                if (next === null) {
                    if (current === '') continue;
                    wearer.style.removeProperty(name);
                } else {
                    if (current === next) continue;
                    wearer.style.setProperty(name, next);
                }
            }
        };
        const measure = () => {
            frame = 0;
            for (const [lane, list] of lanes) {
                // Layout positions, not bounding rects: rects include the
                // celebration transforms (rapture lift, FLIP settle), so a
                // re-read taken while rows are still moving would capture
                // mid-animation rows as the lane's corners and keep them.
                // offsetTop is relative to the positioned list, which is
                // exactly the scroll coordinate space below; at rest both
                // readings agree.
                const top = list.scrollTop;
                const bottom = top + list.clientHeight;
                let first = null;
                let last = null;
                for (const row of list.children) {
                    if (row.tagName !== 'LI') continue;
                    const cell = /** @type {HTMLElement} */ (row);
                    const rowTop = cell.offsetTop;
                    if (rowTop + cell.offsetHeight <= top || rowTop >= bottom) continue;
                    first ??= row;
                    last = row;
                }
                publish(`--territory-${lane}-top`, rankOf(first));
                publish(`--territory-${lane}-bottom`, rankOf(last));
            }
        };
        // Read just after a frame has been drawn, when the layout is already
        // clean: reading row offsets inside the frame, right after a commit,
        // would force the whole page's style and layout a second time.
        let after = 0;
        const schedule = () => {
            if (frame || after) return;
            frame = requestAnimationFrame(() => {
                after = window.setTimeout(() => {
                    after = 0;
                    measure();
                }, 0);
            });
        };
        schedule();
        scheduleTerritory.current = schedule;
        for (const [, list] of lanes) list.addEventListener('scroll', schedule, { passive: true });
        window.addEventListener('resize', schedule);
        return () => {
            scheduleTerritory.current = () => {};
            cancelAnimationFrame(frame);
            window.clearTimeout(after);
            for (const [, list] of lanes) list.removeEventListener('scroll', schedule);
            window.removeEventListener('resize', schedule);
        };
    }, [entries, settings.ramp]);
    // Rows also leave a lane without any scroll (a check solves them), so the
    // corners are re-read when the solved set changes size and when the
    // celebration releases its held rows: a check marks words solved while
    // their rows are still listed (held for the rapture), and the rows only
    // leave the lane when holding ends — measuring on size alone would keep
    // the holding-era corners. Typing a letter moves no row, so keystrokes
    // skip the measure (still one frame per burst when it does run).
    // Not while a check plays back: the read would force a restyle mid-sequence;
    // the end of the sequence re-reads once.
    const holding = Boolean(rapture.active?.holding);
    useEffect(() => {
        if (rapture.busy) return;
        scheduleTerritory.current();
    }, [completedWords.size, holding, rapture.busy]);
    // The last notch becomes the fireworks: the board remembers which words
    // were still open, and when the puzzle completes the finale bursts from the
    // opening of the last of them (the black square's edge or the board's rim
    // in front of its first square). Without a board to measure, the finale
    // falls from the top as before.
    const lastOpen = useRef(/** @type {any[]} */ ([]));
    const [finaleOrigin, setFinaleOrigin] = useState(/** @type {{ x: number, y: number } | null | undefined} */ (undefined));
    useEffect(() => {
        if (!app.showFireworks) {
            const open = entries.filter(entry => !completedWords.has(entryKey(entry)));
            if (open.length) lastOpen.current = open;
            if (finaleOrigin !== undefined) setFinaleOrigin(undefined);
            return;
        }
        if (finaleOrigin !== undefined) return;
        const last = lastOpen.current[0];
        const cell = last ? boardRef.current?.children[last.start_y]?.children[last.start_x] : null;
        const box = cell?.getBoundingClientRect();
        setFinaleOrigin(box
            ? (last.direction === 'across' ? { x: box.left, y: box.top + box.height / 2 } : { x: box.left + box.width / 2, y: box.top })
            : null);
    });
    const selfClick = handler => event => {
        if (event.target === event.currentTarget) handler(event);
    };

    return (
        <div id="app" className={classes({ 'half-completed': entries.length > 0 && settledWords.size / entries.length > 0.5, 'react-desktop-app': true })}
            data-direction={app.activeDirection || 'across'}
            data-glow={glowOn ? 'on' : 'off'}
            data-lit={selection.size > 0 ? '' : undefined}
            data-notepad={app.currentPuzzleMetadata?.notepad ? '' : undefined}
            data-glass={glass || undefined}
            {...viewAttributes(settings)}
            style={/** @type {React.CSSProperties} */ ({
                '--grid-columns': grid[0]?.length || 15,
                '--grid-rows': grid.length || 15,
                // The highlighted word's rank for the background layers — lane
                // watermarks and grid wash — that have no rank of their own.
                // A distinct property, never --clue-ramp itself, so nothing
                // else inherits a rank it was not given.
                ...(settings.ramp && activeEntry && clueRamp.has(activeEntry.clue_number)
                    ? { '--active-clue-ramp': String(clueRamp.get(activeEntry.clue_number)) }
                    : {}),
                '--remaining': String(entries.length ? (entries.length - solvedCount) / entries.length : 1),
                '--libido': String(Math.round(Math.pow(Math.min(1, Math.max(0, shownScore / 100)), 1.25) * 1000) / 1000),
                // A clean run warms the notches further (vision.css section 11).
                '--combo-heat': String(comboHeat(shownCombo)),
            })}>
            <div id="notmenu">
                <div className={classes('clue-column', { active: app.direction === 'across', inactive: app.direction !== 'across' })} data-label="ACROSS">
                    <ul id="across" ref={acrossRef}>
                        {laneEntries('across').map(entry => (
                            <li key={'across-' + entry.clue_number} data-entry={entryKey(entry)} onClick={event => {
                                app.handle_clue_click(event, entry);
                                onEntryFocused?.(entry, 'pointer');
                            }} className={clueClasses(entry)} {...rowProps(entry)}>
                                <div className="clue-content">
                                    <span className="clue-text">{renderClueSurface(entry.clue_text, annotateClueGrammar)}</span>
                                    <div className="state-container">{answer(entry)}</div>
                                </div>
                                <strong className="clue-number" style={settings.ramp ? clueRampStyle(clueRamp, entry.clue_number) : undefined}>{entry.clue_number}</strong>
                            </li>
                        ))}
                        {laneSprings('across', laneEntries('across'))}
                    </ul>
                </div>

                <div className="center-column">
                    {/* Masthead: which puzzle this is, and the numbers a solver
                        actually glances at. Checks and reveals are what the score
                        is made of, so they sit behind it (hover or focus). */}
                    <div id="menu-top" className="menu-section">
                        <div className="menu-row info-bar">
                            {app.currentPuzzleMetadata && <span className="puzzle-weekday">{displayedPuzzleWeekday(app, displayWeekday)}</span>}
                            {app.currentPuzzleMetadata && (
                                <span className="puzzle-meta">
                                    <span className="puzzle-date">{app.formatDate(app.currentPuzzleMetadata.date)}</span>
                                    <span className="puzzle-separator" aria-hidden="true">·</span>
                                    <span className="puzzle-authors" data-full-text={app.currentPuzzleMetadata.authors.join(', ')} title={app.currentPuzzleMetadata.authors.join(', ')}>{app.currentPuzzleMetadata.authors.join(', ')}</span>
                                </span>
                            )}
                        </div>
                        {Boolean(app.currentPuzzleMetadata && app.currentPuzzleMetadata.notepad) && (
                            <div className="puzzle-notepad">{app.currentPuzzleMetadata.notepad}</div>
                        )}

                        <div className="menu-row indicator-bar">
                            <div className="stat-item stat-progress" style={/** @type {React.CSSProperties} */ ({ '--progress': entries.length ? settledWords.size / entries.length : 0 })}>
                                <span className="stat-label">Completed</span>
                                <span className="stat-value">{settledWords.size} / {entries.length}</span>
                                <span className="progress-track" aria-hidden="true"></span>
                            </div>
                            <ComboMeter app={app} bus={rapture.bus} />
                            <div className="stat-item stat-time">
                                <span className="stat-label">Time</span>
                                <span className="stat-value">{app.formatTime(app.timer)}</span>
                            </div>
                            <div className="score-cluster" tabIndex={0} aria-label={`Score ${app.score}: ${app.checksUsed} checks, ${app.revealsUsed} reveals`}>
                                <div className="stat-item stat-score">
                                    <span className="stat-label">Score</span>
                                    <span className="stat-value">{app.score}</span>
                                </div>
                                <div className="stat-detail">
                                    <div className="stat-item">
                                        <span className="stat-label">Checks</span>
                                        <span className="stat-value">{app.checksUsed}</span>
                                    </div>
                                    <div className="stat-item">
                                        <span className="stat-label">Reveals</span>
                                        <span className="stat-value">{app.revealsUsed}</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                            <div className="puzzle-loader-header">
                                <label className="field-label" htmlFor="header-weekday-select">Weekday</label>
                                <select id="header-weekday-select" value={app.selectedWeekday} onChange={event => { app.selectedWeekday = event.target.value; }}>
                                    {app.weekdayOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                                </select>
                                <button onClick={() => app.loadSelectedWeekday()} id="header-get-puzzle-button" aria-label="Get new puzzle">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <circle cx="12" cy="12" r="10"></circle>
                                        <polyline points="12 16 16 12 12 8"></polyline>
                                        <line x1="8" y1="12" x2="16" y2="12"></line>
                                    </svg>
                                </button>
                            </div>

                    </div>

                    {/* Crossword Grid */}
                    <div id="crossword-container">
                        <div className="board-glow" ref={glowRef} aria-hidden="true"></div>
                        <GlassLayer gridRef={boardRef} light={!app.isDarkMode} direction={app.activeDirection === 'down' ? 'down' : 'across'} onBackend={setGlass} />
                        <div className="grid" ref={boardRef} style={{ gridTemplateRows: `repeat(${grid.length}, var(--cell-size))` }}>
                            {grid.map((row, rowIndex) => (
                                <div className="grid-row" key={rowIndex} style={{ gridTemplateColumns: `repeat(${row.length}, var(--cell-size))` }}>
                                    {row.map((cell, cellIndex) => (
                                        <div key={cellIndex} {...gridCellProps(rowIndex, cellIndex)} className={classes('grid-cell', app.getCellClasses(rowIndex, cellIndex), {
                                            'black-cell': cell === null,
                                            'has-letter': Boolean(cell),
                                            'highlighted-cell': selection.has(`${rowIndex},${cellIndex}`),
                                            'future-token-cell': Boolean(tokenAt(rowIndex, cellIndex)),
                                            ...activeEntryCellClasses(rowIndex, cellIndex)
                                        })} data-token-display={tokenAt(rowIndex, cellIndex)?.displayToken || undefined}>
                                            {/* The square carries the rank (see gridCellProps); the index just inherits its tone. */}
                                            {Boolean(startNumbers.get(`${rowIndex},${cellIndex}`)) && <span className="clue-index">{startNumbers.get(`${rowIndex},${cellIndex}`)}</span>}
                                            {cell !== null && (
                                                <>
                                                <input ref={element => { app.setRef('input-' + rowIndex + '-' + cellIndex, element); }} type="text"
                                                        maxLength={app.isRebus(cellIndex, rowIndex) ? 10 : 1}
                                                        value={displayGridValue(grid[rowIndex][cellIndex], rowIndex, cellIndex)}
                                                        aria-label={tokenAt(rowIndex, cellIndex)
                                                            ? `grid cell ${rowIndex}-${cellIndex}, declared token ${tokenAt(rowIndex, cellIndex).displayToken}`
                                                            : 'grid cell ' + rowIndex + '-' + cellIndex}
                                                        title={tokenAt(rowIndex, cellIndex)
                                                            ? `Declared token: ${tokenAt(rowIndex, cellIndex).displayToken}`
                                                            : undefined}
                                                        onChange={event => {
                                                            const cellId = `r${rowIndex}c${cellIndex}`;
                                                            const marker = inputSources.current.get(cellId);
                                                            const nativeEvent = /** @type {InputEvent} */ (event.nativeEvent);
                                                            const inputType = nativeEvent.inputType || '';
                                                            const source = nativeEvent.isComposing || inputType.includes('Composition')
                                                                ? 'composition'
                                                                : inputType === 'insertFromPaste'
                                                                    ? 'paste'
                                                                    : marker?.source === 'touch' && Date.now() - marker.at < 1500
                                                                        ? 'touch'
                                                                        : marker?.source === 'keyboard' ? 'keyboard' : 'unknown';
                                                            const beforeToken = app.grid[rowIndex][cellIndex] || null;
                                                            const isRebusCell = Boolean(app.isRebus(cellIndex, rowIndex));
                                                            const normalized = languageInput?.normalizeForCell(event.target.value, { isRebus: isRebusCell });
                                                            const afterToken = normalized?.accepted ? normalized.fill : event.target.value;
                                                            const sourceEntry = entryAtCell(rowIndex, cellIndex);
                                                            const sourceEntryId = sourceEntry ? `${sourceEntry.direction}-${sourceEntry.clue_number}` : null;
                                                            app.grid[rowIndex][cellIndex] = afterToken;
                                                            inputSources.current.delete(cellId);
                                                            if (beforeToken !== afterToken) {
                                                                onCellChanged?.({ row: rowIndex, column: cellIndex, beforeToken, afterToken, source, activeEntryId: sourceEntryId });
                                                            }
                                                        }}
                                                        onFocus={() => {
                                                            setCursorCell({ rowIndex, cellIndex });
                                                            requestAnimationFrame(() => {
                                                                const entry = entryAtCell(rowIndex, cellIndex);
                                                                if (entry) onEntryFocused?.(entry, 'programmatic');
                                                            });
                                                        }}
                                                        onBlur={() => setCursorCell(null)}
                                                        onPointerDown={event => {
                                                            if (event.pointerType === 'touch') inputSources.current.set(`r${rowIndex}c${cellIndex}`, { source: 'touch', at: Date.now() });
                                                        }}
                                                        onClick={() => {
                                                            app.handle_grid_cell_click(rowIndex, cellIndex);
                                                            const entry = entryAtCell(rowIndex, cellIndex);
                                                            if (entry) onEntryFocused?.(entry, 'pointer');
                                                        }}
                                                        onKeyDown={event => {
                                                            const cellId = `r${rowIndex}c${cellIndex}`;
                                                            const marker = inputSources.current.get(cellId);
                                                            if (!event.key.startsWith('Arrow') && !(marker?.source === 'touch' && Date.now() - marker.at < 1500)) {
                                                                inputSources.current.set(cellId, { source: 'keyboard', at: Date.now() });
                                                            }
                                                            const beforeToken = app.grid[rowIndex][cellIndex] || null;
                                                            const sourceEntry = entryAtCell(rowIndex, cellIndex);
                                                            const sourceEntryId = sourceEntry ? `${sourceEntry.direction}-${sourceEntry.clue_number}` : null;
                                                            const isRebusCell = Boolean(app.isRebus(cellIndex, rowIndex));
                                                            const normalized = normalizeFutureKey(languageInput, event.key, {
                                                                isRebus: isRebusCell,
                                                                ctrlKey: event.ctrlKey,
                                                                metaKey: event.metaKey,
                                                                altKey: event.altKey
                                                            });
                                                            // The existing controller owns all ordinary ASCII navigation. A future
                                                            // language pack only intercepts a supported, single-cell token whose
                                                            // canonical fill differs from that ASCII path (for example é → E).
                                                            // Rebus/multi-token input remains in the existing context-menu path.
                                                            if (!isRebusCell && normalized?.accepted && normalized.fill.length === 1 && normalized.fill !== event.key.toUpperCase()) {
                                                                event.preventDefault();
                                                                app.grid[rowIndex][cellIndex] = normalized.fill;
                                                                app.$forceUpdate();
                                                                app.move(rowIndex, cellIndex, 'forward');
                                                                if (app.isChecking) app.clearChecks();
                                                                inputSources.current.delete(cellId);
                                                                onCellChanged?.({ row: rowIndex, column: cellIndex, beforeToken, afterToken: normalized.fill, source: 'keyboard', activeEntryId: sourceEntryId });
                                                                return;
                                                            }
                                                            app.handle_crossword_cell_keydown(event, rowIndex, cellIndex);
                                                            const afterToken = app.grid[rowIndex][cellIndex] || null;
                                                            if (beforeToken !== afterToken) {
                                                                const source = marker?.source === 'touch' && Date.now() - marker.at < 1500 ? 'touch' : 'keyboard';
                                                                inputSources.current.delete(cellId);
                                                                onCellChanged?.({ row: rowIndex, column: cellIndex, beforeToken, afterToken, source, activeEntryId: sourceEntryId });
                                                            }
                                                            if (event.key.startsWith('Arrow') || event.key === 'Tab') {
                                                                const entry = entryAtCell(rowIndex, cellIndex);
                                                                if (entry) onEntryFocused?.(entry, 'keyboard');
                                                            }
                                                        }}
                                                        onContextMenu={event => {
                                                            const beforeToken = app.grid[rowIndex][cellIndex] || null;
                                                            app.handle_crossword_cell_contextmenu(event, rowIndex, cellIndex);
                                                            const token = app.grid[rowIndex][cellIndex] || null;
                                                            if (beforeToken !== token && token) {
                                                                onCellRevealed?.({ row: rowIndex, column: cellIndex, beforeToken, token }, app);
                                                            }
                                                        }}
                                                        data-row={rowIndex} data-cell={cellIndex}
                                                        data-solution={app.find_solution(rowIndex, cellIndex)}
                                                        />
                                                    {tokenAt(rowIndex, cellIndex) && (
                                                        <span className="future-token-marker" aria-hidden="true">◇</span>
                                                    )}
                                                    {Boolean(app.isRebus(cellIndex, rowIndex)) && <span className="rebus-indicator">{app.getRebusCount(cellIndex, rowIndex)}</span>}
                                                </>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* The commands a solver reaches for mid-solve. */}
                    <div className="menu-row action-bar">
                        <button onClick={() => {
                            const wasChecking = app.isChecking;
                            const before = { completed: new Set(app.completedWords), score: app.score, combo: app.combo };
                            // The check is worked out at once and played back
                            // as a short sequence (useRapture), verdicts included.
                            app.check_all({ deferVerdicts: true });
                            if (!wasChecking && app.isChecking) {
                                rapture.play(app.lastCheck, before);
                                onCheckAll?.(app);
                            }
                        }} id="check-all" className="action-button blue-action" title="Check all">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                                <line x1="12" y1="17" x2="12.01" y2="17"></line>
                            </svg>
                            <span>Check</span>
                        </button>
                        <button onClick={() => {
                            const before = onRevealAll ? gridValues() : null;
                            app.revealAll();
                            if (before) onRevealAll(before, app);
                        }} id="reveal-all" className="action-button blue-action" title="Reveal all">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                            <span>Reveal</span>
                        </button>
                        <button onClick={() => app.markCurrentPuzzleAsComplete(() => onComplete?.())} id="complete-button" className="action-button orange-action" title="Mark as Complete">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                            <span>Complete</span>
                        </button>
                    </div>

                    {/* The tray: per-session things, quiet until wanted. */}
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
                            {app.currentPuzzleMetadata && (
                                <a href={app.getXWordInfoLink()} target="_blank" rel="noopener noreferrer" className="icon-button solution-link" title="View the solution on XWord Info" aria-label="View the solution on XWord Info">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                        <circle cx="12" cy="12" r="10"></circle>
                                        <line x1="12" y1="16" x2="12" y2="12"></line>
                                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                                    </svg>
                                </a>
                            )}
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

                            <ViewControls settings={settings} onChange={changeSettings} onReset={() => changeSettings(VIEW_DEFAULTS)} />
                        </div>
                    </div>
                </div>

                <div className={classes('clue-column', { active: app.direction === 'down', inactive: app.direction !== 'down' })} data-label="DOWN">
                    <ul id="down" ref={downRef}>
                        {laneEntries('down').map(entry => (
                            <li key={'down-' + entry.clue_number} data-entry={entryKey(entry)} onClick={event => {
                                app.handle_clue_click(event, entry);
                                onEntryFocused?.(entry, 'pointer');
                            }} className={clueClasses(entry)} {...rowProps(entry)}>
                                <strong className="clue-number" style={settings.ramp ? clueRampStyle(clueRamp, entry.clue_number) : undefined}>{entry.clue_number}</strong>
                                <div className="clue-content">
                                    <span className="clue-text">{renderClueSurface(entry.clue_text, annotateClueGrammar)}</span>
                                    <div className="state-container">{answer(entry)}</div>
                                </div>
                            </li>
                        ))}
                        {laneSprings('down', laneEntries('down'))}
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
                    {/* Future packs may map one displayed character to several
                        canonical fill units (for example ß → SS). Keep that
                        conversion inside the future-only rebus path; the
                        shared daily solver still receives its original input. */}
                    <input type="text" className="rebus-context-menu-input" value={rebusDisplayValue}
                        onChange={event => {
                            const normalized = describeRebusInput(event.target.value);
                            app.rebusInputValue = normalized.fill;
                            setRebusDisplayValue(normalized.display);
                            app.$forceUpdate?.();
                        }}
                        onKeyDown={event => {
                            const row = app.rebusMenuCell.row;
                            const column = app.rebusMenuCell.col;
                            const beforeToken = app.grid[row]?.[column] || null;
                            const sourceEntry = entryAtCell(row, column);
                            const sourceEntryId = sourceEntry ? `${sourceEntry.direction}-${sourceEntry.clue_number}` : null;
                            app.handleRebusMenuKeydown(event);
                            const token = row >= 0 ? (app.grid[row]?.[column] || null) : null;
                            if (beforeToken !== token) {
                                onCellChanged?.({ row, column, beforeToken, afterToken: token, source: 'keyboard', activeEntryId: sourceEntryId });
                            }
                        }} placeholder="Type letters..." maxLength={10} />
                    <div className="rebus-context-menu-hint">Press Enter to save, Esc to cancel</div>
                    <div className="rebus-context-menu-buttons">
                        <button className="rebus-context-menu-button cancel" onClick={() => app.closeRebusMenu()}>Cancel</button>
                        <button className="rebus-context-menu-button" onClick={() => {
                            const row = app.rebusMenuCell.row;
                            const column = app.rebusMenuCell.col;
                            const beforeToken = app.grid[row]?.[column] || null;
                            const sourceEntry = entryAtCell(row, column);
                            const sourceEntryId = sourceEntry ? `${sourceEntry.direction}-${sourceEntry.clue_number}` : null;
                            app.saveRebusValue();
                            const token = row >= 0 ? (app.grid[row]?.[column] ?? null) : null;
                            if (beforeToken !== token) {
                                onCellChanged?.({ row, column, beforeToken, afterToken: token, source: 'unknown', activeEntryId: sourceEntryId });
                            }
                        }}>Save</button>
                    </div>
                </div>
            )}

            {/* The finish and the check celebrations are plain DOM, not a canvas. */}
            <Volley bus={rapture.bus} />
            <RaptureLayer active={rapture.active} />
            {/* The finish waits for the check that completed the puzzle to play out. */}
            {app.showFireworks && finaleOrigin !== undefined && !rapture.busy && <Finale app={app} origin={finaleOrigin} />}
        </div>
    );
}
