#!/usr/bin/env python3
"""Blind clue bake-off (G1): prepare a judging sheet, then score the marks.

Typical use, on the machine that runs the local models (private directory, not
under docs/evidence):

  # 1. The current pipeline's clues for the same answers (needs the app deps):
  python3 scripts/clue-bakeoff.py pipeline --model llama3.2:3b \\
      --answers answers.json --out ~/crossword-bakeoff/current.json

  # 2. Draft the other arms and build the blind sheet:
  python3 scripts/clue-bakeoff.py prepare --answers answers.json \\
      --out-dir ~/crossword-bakeoff \\
      --arm current=file:~/crossword-bakeoff/current.json \\
      --arm small-lane=model:llama3.2:3b \\
      --arm mid-lane=model:gemma3:12b \\
      --arm cloud=model:cloud:<name>        # only with the cloud extension on

  # 3. Open ~/crossword-bakeoff/sheet.html, judge, click "Download results",
  #    then score it:
  python3 scripts/clue-bakeoff.py score --out-dir ~/crossword-bakeoff \\
      --results ~/Downloads/bakeoff-results.json \\
      --attest-out docs/evidence/private-clue-bakeoff-v1.<date>.json

answers.json is a list of {"id", "answer", "angle", "lane", "weekday"}; only
"answer" is required. Everything but the attestation is answer-bearing and stays
in the private directory. Counts are reported, never a winner.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.crossword import clue_bakeoff as bakeoff  # noqa: E402
from src.crossword.clue_specimens import is_scaffold_surface  # noqa: E402


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_prepare(args) -> int:
    out_dir = _path(args.out_dir)
    bakeoff.refuse_evidence_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    answers = bakeoff.load_answers(_path(args.answers))
    arms = [bakeoff.parse_arm_spec(spec) for spec in args.arm]
    if not 2 <= len(arms) <= len(bakeoff.LABELS):
        raise SystemExit(f"need between 2 and {len(bakeoff.LABELS)} arms")
    results = []
    for arm in arms:
        if arm.kind == "file":
            arm = bakeoff.Arm(arm.name, "file", str(_path(arm.value)), arm.prompt)
            results.append(bakeoff.load_file_arm(arm, answers))
        else:
            print(f"drafting arm {arm.name} with {arm.value} ...", file=sys.stderr)
            results.append(
                bakeoff.draft_model_arm(arm, answers, base_seed=args.seed, timeout=args.timeout)
            )
        done = results[-1]
        print(
            f"  {arm.name}: {len(done['clues'])}/{len(answers)} clues, "
            f"{len(done['failures'])} failures",
            file=sys.stderr,
        )
    cards, key = bakeoff.build_cards(answers, results, shuffle_seed=args.seed)
    _write_json(out_dir / "answers.json", answers)
    _write_json(out_dir / "arms.json", {"baseSeed": args.seed, "arms": results})
    _write_json(out_dir / "key.json", key)
    (out_dir / "sheet.html").write_text(bakeoff.build_sheet_html(cards), encoding="utf-8")
    print(f"wrote {out_dir / 'sheet.html'} ({len(cards)} cards)")
    return 0


def cmd_score(args) -> int:
    out_dir = _path(args.out_dir)
    key = json.loads((out_dir / "key.json").read_text(encoding="utf-8"))
    arms = json.loads((out_dir / "arms.json").read_text(encoding="utf-8"))
    results = json.loads(_path(args.results).read_text(encoding="utf-8"))
    summary = bakeoff.score(key, results)
    attestation = bakeoff.build_attestation(
        summary,
        arms["arms"],
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        base_seed=arms["baseSeed"],
    )
    print(json.dumps(summary, indent=1))
    if args.attest_out:
        _write_json(_path(args.attest_out), attestation)
        print(f"wrote {args.attest_out}", file=sys.stderr)
    return 0


def cmd_pipeline(args) -> int:
    """Run the current clue pipeline over the answers and save id -> clue."""
    from src.crossword import private_puzzle_generation as generation

    answers = bakeoff.load_answers(_path(args.answers))
    entries = [
        {"id": a["id"], "answer": a["answer"], "length": a["length"]} for a in answers
    ]
    context = {"_candidate_base_seed": args.seed}
    _title, clues = generation._make_clues(args.model, entries, context, answers[0]["weekday"])
    out = _path(args.out)
    bakeoff.refuse_evidence_dir(out.parent)
    out.parent.mkdir(parents=True, exist_ok=True)
    # A scaffold placeholder is the pipeline admitting it wrote no clue; it is
    # left out so the arm shows it as missing instead of the judge scoring it.
    real = {
        k: v
        for k, v in clues.items()
        if isinstance(v, str) and not is_scaffold_surface(v)
    }
    _write_json(out, real)
    print(f"wrote {out} ({len(real)} clues, {len(entries) - len(real)} scaffolds left out)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="draft arms and build the blind sheet")
    prepare.add_argument("--answers", required=True)
    prepare.add_argument("--out-dir", required=True)
    prepare.add_argument("--arm", action="append", required=True, help="NAME=model:<tag>|file:<path>")
    prepare.add_argument("--seed", type=int, default=20261006)
    prepare.add_argument("--timeout", type=float, default=120)
    prepare.set_defaults(func=cmd_prepare)

    pipeline = sub.add_parser("pipeline", help="clue the answers with the current pipeline")
    pipeline.add_argument("--model", required=True)
    pipeline.add_argument("--answers", required=True)
    pipeline.add_argument("--out", required=True)
    pipeline.add_argument("--seed", type=int, default=20261006)
    pipeline.set_defaults(func=cmd_pipeline)

    scoring = sub.add_parser("score", help="turn the judge's marks into counts")
    scoring.add_argument("--out-dir", required=True)
    scoring.add_argument("--results", required=True)
    scoring.add_argument("--attest-out")
    scoring.set_defaults(func=cmd_score)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
