import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { celebrationTier, raptureNote } from './celebration';
import { planSequence } from './checkSequence';
import { moveSprings } from './ClueSpring';
import { entryKey } from './entryKey';

// A check, played back. The behaviour works the whole check out in one go
// (check_all with deferVerdicts); this hook shows it as a short sequence
// (checkSequence.js) instead of one frame that does everything: the solved
// words pop one after another — their letters turn, their row lifts off the
// ladder, a firework leaves the word's notch and its chip knocks the springs
// — then the other right letters settle in and any mistakes land last, as one
// blow. When the popped rows have gone, the rest slide up into place (FLIP)
// and the springs follow them by arithmetic, not by measuring each frame.
//
// Everything a step touches is written straight to the DOM or announced on a
// small bus the canvas and the combo meter listen to, so the board view
// renders a few times per check (rows held, rows released, the end), never
// once per step. Until the end the view keeps drawing the board as it stood
// before the check (`shown`): the solved squares, the root's light and the
// answer boxes' verdicts all restyle most of the page, so they land once,
// when the sequence is over, instead of in the first frame.

const SETTLE_MS = 700;
const LANDING_GAP_MS = 180;
const MOMENT_MS = 3400;

const reducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;

function createBus() {
  const listeners = new Set();
  return {
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    emit(event) {
      listeners.forEach((listener) => listener(event));
    },
  };
}

const cellsOf = (entry) =>
  entry.characters.map((_, index) =>
    entry.direction === 'across'
      ? `${entry.start_y},${entry.start_x + index}`
      : `${entry.start_y + index},${entry.start_x}`,
  );

/** Points and combo as they stood before a check, worked back from its beats. */
function standingBefore(app, beats) {
  const first = beats[0];
  if (!first) return { points: app.points, combo: app.combo };
  if (first.kind === 'break') return { points: first.total + first.penalty, combo: first.lost };
  return { points: first.total - first.points, combo: first.repeat ? first.combo : first.combo - 1 };
}

/**
 * @param {any} app  the desktop controller's app
 * @param {{ boardRef?: { current: HTMLElement | null } }} [options]
 */
export function useRapture(app, { boardRef } = {}) {
  const [active, setActive] = useState(null);
  const [bus] = useState(createBus);
  const timers = useRef([]);
  const run = useRef(/** @type {{ frame: number, id: number, unpaint: null | ((force?: boolean) => void) }} */ ({ frame: 0, id: 0, unpaint: null }));
  const flip = useRef(null);

  const stop = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    cancelAnimationFrame(run.current.frame);
    run.current.frame = 0;
    // A sequence cut short takes its painted boxes with it.
    run.current.unpaint?.(true);
    run.current.unpaint = null;
  }, []);

  useEffect(() => stop, [stop]);

  // A new puzzle replaces the list the held rows belonged to.
  const crossword = app.crossword;
  useEffect(() => {
    stop();
    setActive(null);
  }, [crossword, stop]);

  const play = useCallback((check, shown = null) => {
    if (!check) return;
    stop();
    const id = (run.current.id += 1);
    const verdicts = check.verdicts || [];
    const inputAt = (cell) => {
      const [row, column] = cell.split(',');
      return app.$refs[`input-${row}-${column}`]?.[0] || null;
    };
    // The answer boxes that show each square, in either lane, found once.
    const boxes = new Map();
    for (const box of document.querySelectorAll('#app .state[data-cell]')) {
      const cell = box.getAttribute('data-cell');
      if (!boxes.has(cell)) boxes.set(cell, []);
      boxes.get(cell).push(box);
    }
    const painted = new Set();
    // Verdicts are painted only while the check is still showing: typing
    // during the sequence clears it, and nothing late may repaint it.
    const paint = (cells) => {
      if (!app.isChecking || run.current.id !== id) return;
      for (const [cell, verdict] of cells) {
        const targets = [inputAt(cell), ...(boxes.get(cell) || [])];
        for (const target of targets) {
          if (!target) continue;
          target.classList.remove(verdict === 'green' ? 'red' : 'green');
          target.classList.add(verdict);
          if (target.classList.contains('state')) painted.add(target);
        }
      }
    };
    // The boxes are React's: once the view takes the verdicts back (the end),
    // anything painted for a check that has since been cleared comes off.
    const unpaint = (force = false) => {
      if (app.isChecking && !force) return;
      painted.forEach((box) => box.classList.remove('red', 'green'));
      painted.clear();
    };
    run.current.unpaint = unpaint;
    const beats = check.beats || [];
    const breakBeat = beats.find((beat) => beat.kind === 'break') || null;
    const start = standingBefore(app, beats);

    if (reducedMotion()) {
      for (const [cell, verdict] of verdicts) {
        const input = verdict === 'blank' ? null : inputAt(cell);
        if (input) input.classList.add(verdict);
      }
      setActive(null);
      bus.emit({ type: 'instant', beats });
      return;
    }

    const entries = new Map((app.crossword || []).map((entry) => [entryKey(entry), entry]));
    const words = check.gained
      .map((key) => entries.get(key))
      .filter(Boolean)
      .map((entry) => ({ key: entryKey(entry), entry, cells: cellsOf(entry) }));
    const plan = planSequence({ words, verdicts, breakBeat });

    // Everything the fireworks need to know about where things are, read now,
    // in one go, while the page is still laid out from the last frame.
    const board = boardRef?.current;
    /** @returns {HTMLElement | null} */
    const cellAt = (row, column) => /** @type {HTMLElement | null} */ (board?.children[row]?.children[column] || null);
    const beatOf = new Map(beats.filter((beat) => beat.kind === 'word').map((beat) => [beat.key, beat]));
    const launches = new Map();
    for (const { key, entry } of words) {
      const cell = cellAt(entry.start_y, entry.start_x);
      const chip = document.querySelector(`#app li[data-entry="${key}"] > .clue-number`);
      const box = cell?.getBoundingClientRect();
      const chipBox = chip?.getBoundingClientRect();
      launches.set(key, {
        key,
        direction: entry.direction,
        length: entry.characters.length,
        // The notch: the edge a word is entered through.
        origin: box
          ? entry.direction === 'across'
            ? { x: box.left, y: box.top + box.height / 2 }
            : { x: box.left + box.width / 2, y: box.top }
          : null,
        span: box ? box.width * entry.characters.length : 0,
        chip: chipBox ? { x: chipBox.left + chipBox.width / 2, y: chipBox.top + chipBox.height / 2 } : null,
        color: chip ? getComputedStyle(chip).color : null,
        beat: beatOf.get(key) || null,
      });
    }
    const wrongCells = (check.wrongCells || []).map((cell) => {
      const [row, column] = cell.split(',').map(Number);
      const box = cellAt(row, column)?.getBoundingClientRect();
      return box ? { cell, x: box.left + box.width / 2, y: box.top + box.height / 2, size: box.width } : null;
    }).filter(Boolean);
    const brokenWords = new Map();
    for (const entry of entries.values()) {
      if (!cellsOf(entry).some((cell) => check.wrongCells?.includes(cell))) continue;
      if (!brokenWords.has(entry.direction)) brokenWords.set(entry.direction, []);
      brokenWords.get(entry.direction).push(entry.clue_number);
    }
    const flareAt = (entry) => {
      // The black square whose tick opens the word, or, on the rim, the
      // word's own first square (whose rim tick stands in for it).
      const opener = entry.direction === 'across'
        ? cellAt(entry.start_y, entry.start_x - 1)
        : cellAt(entry.start_y - 1, entry.start_x);
      const target = opener?.classList.contains('black-cell') ? opener : cellAt(entry.start_y, entry.start_x);
      return target ? { target, side: entry.direction === 'across' ? 'e' : 's' } : null;
    };

    const tier = celebrationTier({ solved: words.length, mistakes: check.wrongCells?.length || 0 });
    const lift = words.length > 0;
    // The rows a check solves stay listed (held) until the sequence lands;
    // each one is marked to pop at its own beat, on the row alone.
    const rows = new Map(words.map(({ key }) => [key, /** @type {HTMLElement | null} */ (document.querySelector(`#app li[data-entry="${key}"]`))]));
    // The landing: the popped rows leave, the rest slide up, and the board
    // takes on its new state (solved squares, light, verdicts).
    const landing = plan.end + 60;
    setActive({
      id,
      holding: lift,
      tier,
      order: new Map(words.map((word, index) => [word.key, index])),
      note:
        lift && tier >= 3 && app.completedWords.size < app.crossword.length
          ? raptureNote({ solved: words.length, mistakes: check.wrongCells?.length || 0 })
          : null,
      noteDelay: Math.max(0, plan.releaseAt - 500),
      mistakes: check.wrongCells?.length || 0,
      busy: true,
      shown,
    });
    bus.emit({ type: 'start', id, from: start, beats });

    // The timeline: one frame loop fires every step that is due.
    const queue = [];
    for (const event of plan.events) {
      if (event.type === 'break') {
        const crackDelay = new Map(event.cells.map(([cell, , delay]) => [cell, delay || 0]));
        const shards = wrongCells.map((cell) => ({ ...cell, delay: crackDelay.get(cell.cell) || 0 }));
        queue.push({ at: event.at, run: () => {
          bus.emit({ type: 'break', id, beat: breakBeat, cells: shards });
          for (const [lane, numbers] of brokenWords) moveSprings({ kind: 'jolt', lane, numbers, impulse: 300 });
          const container = board?.parentElement;
          if (container) container.setAttribute('data-jolt', container.getAttribute('data-jolt') === 'a' ? 'b' : 'a');
        } });
        // The crack spreads: each wrong letter lands at its own moment.
        const slices = new Map();
        for (const [cell, verdict, delay = 0] of event.cells) {
          const at = event.at + Math.floor(delay / 16) * 16;
          if (!slices.has(at)) slices.set(at, []);
          slices.get(at).push([cell, verdict]);
        }
        slices.forEach((cells, at) => queue.push({ at, run: () => paint(cells) }));
      } else if (event.type === 'word') {
        const launch = launches.get(event.key);
        const entry = entries.get(event.key);
        const row = rows.get(event.key);
        const squares = event.cells.map(([cell]) => {
          const [r, c] = cell.split(',').map(Number);
          return cellAt(r, c);
        }).filter(Boolean);
        queue.push({ at: event.at, run: () => {
          if (run.current.id !== id) return;
          paint(event.cells);
          // The word's squares flash in its hue as it pops (vision.css), and
          // its row rises off the ladder (celebration.css).
          for (const square of squares) {
            if (launch?.color) square.style.setProperty('--pop-tint', launch.color);
            square.setAttribute('data-pop', '');
          }
          timers.current.push(setTimeout(() => squares.forEach((square) => square.removeAttribute('data-pop')), 800));
          if (row) {
            row.style.setProperty('--rapture-delay', '0ms');
            row.setAttribute('data-rapture', String(Math.max(1, tier)));
          }
          bus.emit({ type: 'word', id, ...launch });
          const level = launch?.beat?.tier ?? 0;
          moveSprings({ kind: 'release', lane: entry.direction, number: entry.clue_number });
          moveSprings({ kind: 'pluck', lane: entry.direction, number: entry.clue_number, impulse: (event.index % 2 ? -1 : 1) * (120 + 42 * level) });
          const flare = flareAt(entry);
          if (flare) {
            flare.target.setAttribute('data-flare', flare.side);
            timers.current.push(setTimeout(() => flare.target.removeAttribute('data-flare'), 900));
          }
        } });
      } else {
        queue.push({ at: event.at, run: () => paint(event.cells) });
      }
    }
    queue.sort((a, b) => a.at - b.at);
    const began = performance.now();
    let next = 0;
    const tick = () => {
      const elapsed = performance.now() - began;
      while (next < queue.length && queue[next].at <= elapsed) queue[next++].run();
      run.current.frame = next < queue.length ? requestAnimationFrame(tick) : 0;
    };
    run.current.frame = requestAnimationFrame(tick);

    // The landing comes in two steps a few frames apart, so neither is one
    // long frame: first the popped rows leave and the rest slide up (their
    // slide is composited, so it carries on through the second step), then
    // the board's state lands.
    if (lift) {
      timers.current.push(setTimeout(() => {
        // Positions as they are about to change, read while the popped rows
        // are still in the list.
        flip.current = new Map(
          [...document.querySelectorAll('#app #across > li, #app #down > li')]
            .filter((row) => !row.hasAttribute('data-rapture'))
            .map((row) => [row, row.getBoundingClientRect()]),
        );
        setActive((current) => (current && current.id === id ? { ...current, holding: false } : current));
      }, landing));
    }
    timers.current.push(setTimeout(() => {
      unpaint();
      run.current.unpaint = null;
      bus.emit({ type: 'end', id });
      setActive((current) => (current && current.id === id ? { ...current, holding: false, busy: false } : current));
    }, landing + (lift ? LANDING_GAP_MS : 0)));
    timers.current.push(setTimeout(() => {
      setActive((current) => (current && current.id === id ? null : current));
    }, Math.max(landing + LANDING_GAP_MS + SETTLE_MS + 200, lift && tier >= 3 ? plan.releaseAt + MOMENT_MS - 500 : 0)));
  }, [app, boardRef, bus, stop]);

  // After the held rows are gone: slide everything that remains into place,
  // and tell the springs where each chip is coming from.
  const holding = Boolean(active?.holding);
  useLayoutEffect(() => {
    const previous = flip.current;
    if (!previous || holding) return;
    flip.current = null;
    if (typeof Element.prototype.animate !== 'function') return;
    let index = 0;
    const rows = [];
    previous.forEach((from, row) => {
      if (!row.isConnected) return;
      const to = row.getBoundingClientRect();
      const dx = from.left - to.left;
      const dy = from.top - to.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
      const delay = Math.min(index, 14) * 14;
      row.animate(
        [
          { transform: `translate(${dx}px, ${dy}px)`, opacity: 0.35 },
          { transform: 'translate(0, 0)', opacity: 1 },
        ],
        {
          duration: SETTLE_MS,
          delay,
          easing: 'cubic-bezier(0.3, 1.45, 0.5, 1)',
          fill: 'backwards',
        },
      );
      const [lane, number] = String(row.getAttribute('data-entry') || '').split('-');
      if (lane && number) rows.push({ lane, number: Number(number), dx, dy, delay, duration: SETTLE_MS });
      index += 1;
    });
    if (rows.length) moveSprings({ kind: 'settle', rows });
  }, [holding]);

  return { active, play, bus, busy: Boolean(active?.busy) };
}
