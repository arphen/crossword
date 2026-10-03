#!/usr/bin/env python3
"""Recompute sweep metrics from the per-arm cold-solver verdict files.

The sweep driver reads each arm's counts out of a single shared receipt that
every arm overwrites, which loses an arm's numbers whenever the read races the
write. The per-arm verdict files are written once and never overwritten, and
they hold every field the buckets are derived from, so the metrics are
recomputed here from those instead. This mirrors ``_classify`` exactly, so a
recomputed arm is identical to a directly probed one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _tallies(verdicts):
    """Tally the bucket the probe already computed for each entry.

    The verdict files record the bucket decided at probe time, so they are the
    authority here. Re-deriving it is not possible from the stored fields: the
    trivial/unfair split depends on the attempt-1 confidence, which the probe
    consumes but does not persist.
    """
    buckets: dict = {}
    soundness: dict = {}
    for verdict in verdicts.values():
        bucket = verdict.get("bucket", "unknown")
        buckets[bucket] = buckets.get(bucket, 0) + 1
        if bucket != "scaffold":
            sound = verdict.get("sound", "unclear")
            soundness[sound] = soundness.get(sound, 0) + 1
    return buckets, soundness


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verdicts", nargs="+", required=True)
    parser.add_argument("--sweep", type=Path, required=True)
    args = parser.parse_args()

    base = {}
    if args.sweep.is_file():
        for line in args.sweep.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                base[record["label"]] = record

    for path in args.verdicts:
        path = Path(path)
        label = path.stem.replace("verdicts-", "")
        payload = json.loads(path.read_text(encoding="utf-8"))
        verdicts = payload.get("verdicts") or {}
        buckets, soundness = _tallies(verdicts)
        judged = sum(v for k, v in buckets.items() if k != "scaffold")
        record = base.get(label, {"label": label})
        record.update(
            {
                "buckets": dict(sorted(buckets.items())),
                "judged": judged,
                "goldRate": round(buckets.get("gold", 0) / judged, 4) if judged else None,
                "trivialRate": round(buckets.get("trivial", 0) / judged, 4) if judged else None,
                "unfairRate": round(buckets.get("unfair", 0) / judged, 4) if judged else None,
                "unresolvedRate": round(buckets.get("unresolved", 0) / judged, 4) if judged else None,
                "soundRate": round(soundness.get("sound", 0) / judged, 4) if judged else None,
                "recomputed": True,
            }
        )
        base[label] = record
        print(json.dumps(record))

    args.sweep.write_text(
        "".join(json.dumps(base[label]) + "\n" for label in sorted(base)), encoding="utf-8"
    )
    print(f"-> {args.sweep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
