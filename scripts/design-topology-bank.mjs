#!/usr/bin/env node
/**
 * Scratch topology designer: searches for valid 15x15 crossword block masks
 * suitable for the curated template bank. Masks are left-right and top-bottom
 * mirror symmetric (hence 180-degree rotational), min run length 3, every
 * white cell checked, connected white graph, and a target block budget.
 *
 * Output is a printable set of masks for human review — nothing here is
 * imported by the app; the reviewed masks get frozen into
 * packages/construction/src/topology.ts.
 */
import { readFileSync } from 'node:fs';

const SIZE = 15;
const words = readFileSync('packages/construction/data/fill-lexicon-v1.txt', 'utf8')
  .split('\n')
  .filter(Boolean);

// ---------- mask primitives ----------
const idx = (r, c) => r * SIZE + c;
const isBlock = (mask, r, c) => mask[idx(r, c)] === '#';

function maskFromRows(rows) {
  return rows.join('').split('');
}

function rowsOf(mask) {
  const out = [];
  for (let r = 0; r < SIZE; r += 1) out.push(mask.slice(r * SIZE, r * SIZE + SIZE).join(''));
  return out;
}

function lrSymmetric(mask) {
  for (let r = 0; r < SIZE; r += 1) {
    for (let c = 0; c < SIZE; c += 1) {
      if (mask[idx(r, c)] !== mask[idx(r, SIZE - 1 - c)]) return false;
    }
  }
  return true;
}

function tbSymmetric(mask) {
  for (let r = 0; r < SIZE; r += 1) {
    for (let c = 0; c < SIZE; c += 1) {
      if (mask[idx(r, c)] !== mask[idx(SIZE - 1 - r, c)]) return false;
    }
  }
  return true;
}

function runs(line) {
  const out = [];
  let start = -1;
  for (let i = 0; i <= line.length; i += 1) {
    const white = i < line.length && line[i] === '.';
    if (white && start < 0) start = i;
    if (!white && start >= 0) {
      out.push([start, i - start]);
      start = -1;
    }
  }
  return out;
}

function acrossRuns(mask, r) { return runs(Array.from({ length: SIZE }, (_, c) => (isBlock(mask, r, c) ? '#' : '.')).join('')); }
function downRuns(mask, c) { return runs(Array.from({ length: SIZE }, (_, r) => (isBlock(mask, r, c) ? '#' : '.')).join('')); }

function minRunOk(mask) {
  for (let i = 0; i < SIZE; i += 1) {
    for (const [, len] of acrossRuns(mask, i)) if (len < 3) return false;
    for (const [, len] of downRuns(mask, i)) if (len < 3) return false;
  }
  return true;
}

function allChecked(mask) {
  for (let r = 0; r < SIZE; r += 1) {
    for (let c = 0; c < SIZE; c += 1) {
      if (isBlock(mask, r, c)) continue;
      const inAcross = acrossRuns(mask, r).some(([s, len]) => c >= s && c < s + len && len >= 2);
      const inDown = downRuns(mask, c).some(([s, len]) => r >= s && r < s + len && len >= 2);
      if (!inAcross || !inDown) return false;
    }
  }
  return true;
}

function connected(mask) {
  const start = mask.findIndex((v) => v === '.');
  if (start < 0) return false;
  const seen = new Set([start]);
  const queue = [start];
  while (queue.length > 0) {
    const current = queue.pop();
    const r = Math.floor(current / SIZE);
    const c = current % SIZE;
    for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nr = r + dr;
      const nc = c + dc;
      if (nr < 0 || nc < 0 || nr >= SIZE || nc >= SIZE || isBlock(mask, nr, nc)) continue;
      const next = idx(nr, nc);
      if (!seen.has(next)) { seen.add(next); queue.push(next); }
    }
  }
  return seen.size === mask.filter((v) => v === '.').length;
}

function chunky(mask) {
  // No 2x2 fully open areas larger than ... actually allow them; instead reject
  // blocks that touch only diagonally (isolated staircase) which look ragged.
  for (let r = 1; r < SIZE; r += 1) {
    for (let c = 1; c < SIZE; c += 1) {
      const here = isBlock(mask, r, c);
      const up = isBlock(mask, r - 1, c);
      const left = isBlock(mask, r, c - 1);
      const diag = isBlock(mask, r - 1, c - 1);
      if (here && diag && !up && !left) return false;
      if (!here && !diag && !up && !left) {
        // 2x2 open square — fine for quality, ignore.
      }
    }
  }
  return true;
}

function valid(mask) {
  return lrSymmetric(mask) && tbSymmetric(mask) && minRunOk(mask) && allChecked(mask) && connected(mask) && chunky(mask);
}

function blockCount(mask) { return mask.filter((v) => v === '#').length; }

// ---------- seeded RNG ----------
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- search: random quadrant + repair + down-quality scoring ----------
function mirrorComplete(quadrantMask) {
  // quadrant mask covers rows 0..7, cols 0..14 (top half). Complete with
  // top-bottom mirror, then left-right mirror is implied by quadrant row symmetry.
  const full = quadrantMask.slice();
  for (let r = 0; r < 7; r += 1) {
    for (let c = 0; c < SIZE; c += 1) {
      full[idx(SIZE - 1 - r, c)] = full[idx(r, c)];
    }
  }
  return full;
}

function randomTopHalf(rng, blockProbability) {
  const half = Array.from({ length: SIZE * 8 }, () => (rng() < blockProbability ? '#' : '.'));
  // enforce lr symmetry inside each top-half row
  for (let r = 0; r < 8; r += 1) {
    for (let c = 0; c < SIZE; c += 1) {
      const mirror = SIZE - 1 - c;
      if (half[idx(r, mirror)] === '#' && half[idx(r, c)] === '.') half[idx(r, c)] = '#';
      else if (half[idx(r, mirror)] === '.' && half[idx(r, c)] === '#') half[idx(r, mirror)] = '.';
    }
  }
  return half;
}

/** Fix runs shorter than 3 by adding blocks at symmetry-preserving spots. */
function repair(mask) {
  for (let pass = 0; pass < 12; pass += 1) {
    let changed = false;
    for (let r = 0; r < SIZE; r += 1) {
      for (const [start, len] of acrossRuns(mask, r)) {
        if (len >= 3) continue;
        // block off the short run at its boundary that keeps lr symmetry
        const options = [];
        if (start === 0) options.push([r, len]); // block cols 0..len-1? no: block the run's last col
        if (options.length === 0) {
          options.push([r, start + len - 1]);
          options.push([r, start - 1 >= 0 ? start - 1 : start + len - 1]);
        }
        for (const [rr, cc] of options) {
          const mirrored = SIZE - 1 - cc;
          if (!isBlock(mask, rr, cc)) { mask[idx(rr, cc)] = '#'; mask[idx(rr, SIZE - 1 - cc)] = '#'; changed = true; break; }
        }
      }
    }
    for (let c = 0; c < SIZE; c += 1) {
      for (const [start, len] of downRuns(mask, c)) {
        if (len >= 3) continue;
        const rr = start === 0 ? start + len - 1 : start - 1 >= 0 ? start - 1 : start + len - 1;
        if (!isBlock(mask, rr, c)) {
          mask[idx(rr, c)] = '#';
          mask[idx(SIZE - 1 - rr, c)] = '#';
          changed = true;
        }
      }
    }
    if (!changed) break;
  }
  return mask;
}

function downScore(mask) {
  const downs = downLengthStats(mask);
  let score = 0;
  for (const len of downs) {
    if (len <= 7) score += 2;
    else if (len <= 9) score += 0.5;
    else score -= (len - 8) * 1.5; // long downs are fill-risk
  }
  return score / Math.max(1, downs.length);
}

function acrossScore(mask) {
  const across = acrossLengthStats(mask);
  let score = 0;
  for (const len of across) {
    if (len <= 7) score += 2;
    else if (len <= 9) score += 0.5;
    else if (len <= 13) score -= 0.3;
    else score -= 1.2; // 14-15 letter slots need phrases, not web2 words
  }
  return score / Math.max(1, across.length);
}

function longRunCount(mask) {
  let count = 0;
  for (let r = 0; r < SIZE; r += 1) for (const [, len] of acrossRuns(mask, r)) if (len >= 13) count += 1;
  for (let c = 0; c < SIZE; c += 1) for (const [, len] of downRuns(mask, c)) if (len >= 13) count += 1;
  return count;
}

function openCenterScore(mask) {
  let open = 0;
  for (let r = 5; r <= 9; r += 1) for (let c = 5; c <= 9; c += 1) if (!isBlock(mask, r, c)) open += 1;
  return open;
}

function downLengthStats(mask) {
  const lengths = [];
  for (let c = 0; c < SIZE; c += 1) for (const [, len] of downRuns(mask, c)) lengths.push(len);
  return lengths;
}

function acrossLengthStats(mask) {
  const lengths = [];
  for (let r = 0; r < SIZE; r += 1) for (const [, len] of acrossRuns(mask, r)) lengths.push(len);
  return lengths;
}

/**
 * Plant 2-3 tall vertical block stacks in the top-left quadrant, mirror them
 * lr into the top half and tb into the bottom half. Stacks cap run lengths
 * the way human-drawn grids do; scattered single blocks (dust) do not.
 */
function plantStacks(rng) {
  const mask = Array.from({ length: SIZE * SIZE }, () => '.');
  const stackCount = 2 + Math.floor(rng() * 4);
  const usedColumns = new Set();
  for (let s = 0; s < stackCount; s += 1) {
    const col = 1 + Math.floor(rng() * 6);
    if (usedColumns.has(col)) continue;
    usedColumns.add(col);
    const row = Math.floor(rng() * 3);
    const height = 2 + Math.floor(rng() * 2);
    for (let h = 0; h < height; h += 1) {
      const r = row + h;
      if (r >= SIZE) break;
      mask[idx(r, col)] = '#';
      mask[idx(r, SIZE - 1 - col)] = '#';
      mask[idx(SIZE - 1 - r, col)] = '#';
      mask[idx(SIZE - 1 - r, SIZE - 1 - col)] = '#';
    }
  }
  if (rng() < 0.5) {
    const col = 1 + Math.floor(rng() * 5);
    const row = 3 + Math.floor(rng() * 3);
    mask[idx(row, col)] = '#';
    mask[idx(row, SIZE - 1 - col)] = '#';
    mask[idx(SIZE - 1 - row, col)] = '#';
    mask[idx(SIZE - 1 - row, SIZE - 1 - col)] = '#';
  }
  return mask;
}

const found = new Map();
let attempts = 0;
const foundList = [];
while (foundList.length < 80 && attempts < 3_000_000) {
  attempts += 1;
  const rng = mulberry32(attempts * 2654435761);
  let mask = repair(plantStacks(rng));
  if (!lrSymmetric(mask) || !tbSymmetric(mask)) continue; // repair keeps symmetry; paranoia
  const blocks = blockCount(mask);
  if (blocks < 26 || blocks > 36) continue;
  if (!minRunOk(mask) || !allChecked(mask) || !connected(mask) || !chunky(mask)) continue;
  // Single-word lexicon: no slot longer than 10 anywhere.
  let maxRun = 0;
  for (let i = 0; i < SIZE; i += 1) {
    for (const [, l] of acrossRuns(mask, i)) if (l > maxRun) maxRun = l;
    for (const [, l] of downRuns(mask, i)) if (l > maxRun) maxRun = l;
  }
  if (maxRun > 10) continue;
  const ds = downScore(mask);
  if (ds < 1.1) continue; // snappy downs
  const key = rowsOf(mask).join('|');
  if (found.has(key)) continue;
  found.set(key, true);
  foundList.push({ mask, blocks, ds, center: openCenterScore(mask) });
}

foundList.sort((a, b) => (b.ds) - (a.ds) || b.center - a.center);
console.log(`attempts=${attempts} found=${foundList.length}`);
for (const { mask, blocks, ds, center } of foundList.slice(0, 24)) {
  const downs = downLengthStats(mask);
  const across = acrossLengthStats(mask);
  const avg = (arr) => (arr.reduce((x, y) => x + y, 0) / arr.length).toFixed(2);
  console.log(`--- blocks=${blocks} downs=${downs.length} avgDown=${avg(downs)} avgAcross=${avg(across)} maxDown=${Math.max(...downs)} maxAcross=${Math.max(...across)} downScore=${ds.toFixed(2)} center=${center}`);
  for (const row of rowsOf(mask)) console.log(row);
  console.log();
}
