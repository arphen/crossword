#!/usr/bin/env python3
"""
Extract and analyze NYT grid topologies from the local corpus.

Outputs (to /tmp/nyt_topo):
- stats.json: per-day structural statistics (block density, slot lengths,
  symmetry types, common long-slot counts)
- masks/<day>/<count>.txt: deduplicated valid masks (180-degree rotational
  symmetry, min run 3, all white cells checked, connected) per weekday
- answer_freq.json: answer frequency across the corpus (for the staple prior)

Private analysis input: derived from the household's local NYT archive; the
 emitted masks are structural patterns used for private construction, and
 clue/answer text stays out of any public artifact.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

CORPUS = Path('/Users/arphen/projectc/nyt_crosswords')
OUT = Path('/tmp/nyt_topo')
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def mask_from_grid(grid, rows, cols):
    return ''.join('#' if ch == '.' else '.' for ch in grid)


def runs(line):
    out = []
    start = -1
    for i, ch in enumerate(str(line) + '#'):
        if ch == '.' and start < 0:
            start = i
        elif ch != '.' and start >= 0:
            out.append((start, i - start))
            start = -1
    return out


def analyze(mask, w, h):
    across = []
    down = []
    for r in range(len(mask) // w):
        line = mask[r * w:(r + 1) * w]
        across.extend(l for l in runs(line) if l[1] > 0)
    for c in range(w):
        line = ''.join(mask[r * w + c] for r in range(len(mask) // w))
        down.extend((s, l) for s, l in runs(line) if l > 0)
    return across, down


def rot180(mask, w):
    h = len(mask) // w
    return ''.join(mask[(h - 1 - r) * w + (w - 1 - c)] for r in range(h) for c in range(w))


def lr(mask, w):
    h = len(mask) // w
    return all(mask[r * w + c] == mask[r * w + (w - 1 - c)] for r in range(h) for c in range(w))


def tb(mask, w):
    h = len(mask) // w
    return all(mask[r * w + c] == mask[(h - 1 - r) * w + c] for r in range(h) for c in range(w))


def min_run_ok(mask, w, minlen=3):
    h = len(mask) // w
    for r in range(h):
        for _, l in analyze_runs(mask, r, w, True):
            if l < minlen:
                return False
    for c in range(w):
        for _, l in analyze_runs(mask, c, w, False):
            if l < minlen:
                return False
    return True


def analyze_runs(mask, line, w, is_across):
    h = len(mask) // w
    seq = ''.join(mask[line * w + c] for c in range(w)) if is_across else ''.join(mask[r * w + line] for r in range(h))
    return [x for x in runs(seq) if x[1] > 0]


def checked_ok(mask, w):
    h = len(mask) // w
    for r in range(h):
        for c in range(w):
            if mask[r * w + c] == '#':
                continue
            ina = any(s <= c < s + l and l >= 2 for s, l in analyze_runs(mask, r, w, True))
            ind = any(s <= r < s + l and l >= 2 for s, l in analyze_runs(mask, c, w, False))
            if not (ina and ind):
                return False
    return True


def connected(mask, w):
    h = len(mask) // w
    whites = [i for i, ch in enumerate(mask) if ch == '.']
    if not whites:
        return False
    seen = {whites[0]}
    stack = [whites[0]]
    while stack:
        cur = stack.pop()
        r, c = divmod(cur, w)
        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= nr < h and 0 <= nc < w and mask[nr * w + nc] == '.':
                n = nr * w + nc
                if n not in seen:
                    seen.add(n)
                    stack.append(n)
    return len(seen) == len(whites)


def valid(mask, w):
    if w != 15 and w != 21:
        return False
    if len(mask) != w * w:
        return False
    rot = rot180(mask, w)
    if mask != rot:
        return False
    return min_run_ok(mask, w) and checked_ok(mask, w) and connected(mask, w)


def rot180(mask, w):
    return mask[::-1]


def main():
    (OUT / 'masks').mkdir(parents=True, exist_ok=True)
    stats = defaultdict(lambda: {
        'count': 0, 'valid': 0, 'lr': 0, 'blocks': Counter(),
        'slot_len': Counter(), 'long_slots': Counter(), 'max_slot': Counter(),
    })
    seen = set()
    answer_freq = Counter()
    errors = 0

    for year_dir in sorted(CORPUS.iterdir()):
        if not year_dir.is_dir():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            for f in sorted(month_dir.glob('*.json')):
                try:
                    p = json.loads(f.read_text())
                except Exception:
                    errors += 1
                    continue
                size = p.get('size') or {}
                cols, rows = size.get('cols'), size.get('rows')
                grid = p.get('grid') or []
                if not cols or not rows or len(grid) != cols * rows:
                    errors += 1
                    continue
                dow = p.get('dow')
                if dow not in DAYS:
                    continue
                s = stats[dow]
                s['count'] += 1
                mask = mask_from_grid(grid, cols, rows)
                s['lr'] += 1 if lr(mask, cols) else 0
                blocks = mask.count('#')
                s['blocks'][blocks] += 1
                answers = p.get('answers') or {}
                for a in answers.get('across', []):
                    answer_freq[a] += 1
                for a in answers.get('down', []):
                    answer_freq[a] += 1
                if not valid(mask, cols):
                    continue
                s['valid'] += 1
                key = (cols, mask)
                if key in seen:
                    continue
                seen.add(key)
                slots = [x for r in range(cols) for x in analyze_runs(mask, r, cols, True)] + [x for c in range(cols) for x in analyze_runs(mask, c, cols, False)]
                lengths = [l for _, l in slots]
                s['slot_len'].update(lengths)
                s['long_slots'][sum(1 for l in lengths if l >= 12)] += 1
                s['max_slot'][max(lengths)] += 1
                day_dir = OUT / 'masks' / dow
                day_dir.mkdir(parents=True, exist_ok=True)
                (day_dir / f'{s["valid"]:05d}.txt').write_text(mask)

    out_stats = {}
    for day, s in stats.items():
        total_slots = sum(s['slot_len'].values())
        out_stats[day] = {
            'count': s['count'], 'valid': s['valid'], 'lr_symmetric': s['lr'],
            'block_histogram': dict(s['blocks'].most_common(10)),
            'avg_slot_length': round(sum(l * n for l, n in s['slot_len'].items()) / max(1, total_slots), 2) if (total_slots := sum(s['slot_len'].values())) else 0,
            'slot_len_histogram': dict(sorted(s['slot_len'].items())),
            'long_slot_histogram': dict(sorted(s['long_slots'].items())),
        }
    (OUT / 'stats.json').write_text(json.dumps(out_stats, indent=2))
    (OUT / 'answer_freq.json').write_text(json.dumps(answer_freq))
    print('errors:', errors)
    for day in DAYS:
        s = stats[day]
        print(day, 'count', s['count'], 'valid', s['valid'])


if __name__ == '__main__':
    sys.exit(main())
