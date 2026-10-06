"""Blind clue bake-off (G1): several arms clue the same answers, the owners judge.

Nothing here decides a winner. It drafts one clue per answer per arm, shuffles
the arms per card so the judge cannot tell which is which, writes a
self-contained judging page, and later turns the judge's marks into counts.
The answer-bearing files (arms, key, sheet, results) live in a private
directory outside ``docs/evidence``; only a counts-and-digest attestation is
meant to be committed, per the evidence rules in the generation plan.

An arm is ``NAME=model:<tag>[,prompt=lane|plain]`` (drafted here through the
clue-model adapters) or ``NAME=file:<path>`` (clues produced elsewhere, such as
the current pipeline, as a JSON object mapping answer id to clue text). The
lane prompts below are a prototype for the bake-off; the grammar lanes (G4)
supersede them.
"""

from __future__ import annotations

import hashlib
import html
import json
import random
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .clue_model import ChatCall, resolve_adapter, run_chat
from .clue_quality_evaluation import canonical_clue_quality_json

VERSION = "private-clue-bakeoff-v1"
LABELS = "ABCDEFGH"
LANES = ("misdirection", "definition", "fill-blank", "spoken", "abbreviation", "language-cue")

_PLAIN_INSTRUCTION = (
    "Write original, lively crossword clues. One concise clue per entry id, fair "
    "and grammatical, matching the answer's part of speech, number, and tense. "
    "Never repeat the answer or its stem. Reply as JSON with a clues array of "
    "{id, text}."
)

# Prototype lane prompts: an instruction and original exemplars per grammar.
_LANE_PROMPTS: dict[str, dict[str, Any]] = {
    "misdirection": {
        "instruction": (
            "Write a ? clue. It must read naturally in one sense and resolve in "
            "another: use the given angle (the second sense, split or sound-alike) "
            "as the pivot, make the surface plausible on its own, and end with ?."
        ),
        "examples": [
            ("SCALES", "Piano student's daily workout?"),
            ("BANKS", "Places where you find interest and a current?"),
            ("WATCHES", "Keeps time and a lookout?"),
        ],
    },
    "definition": {
        "instruction": (
            "Write a fair definition-style clue that is indirect rather than "
            "literal: describe what the answer does, where it lives or what it "
            "is known for, without repeating the answer or its stem."
        ),
        "examples": [
            ("TIDE", "Moon-driven pull"),
            ("OPERA", "Where the big numbers are sung"),
            ("CURIE", "Name behind a radioactivity unit"),
        ],
    },
    "fill-blank": {
        "instruction": (
            "Write a fill-in-the-blank clue: a familiar phrase with the answer "
            "replaced by ___ (three underscores)."
        ),
        "examples": [
            ("BEANS", "Spill the ___"),
            ("BEAUTY", "___ and the Beast"),
            ("A", "Once upon ___ time"),
        ],
    },
    "spoken": {
        "instruction": (
            "Write a spoken-equivalent clue: a quoted utterance (in double quotes) "
            "that someone might say, which the answer completes or matches."
        ),
        "examples": [
            ("NOWAY", '"Not a chance!"'),
            ("ISEE", '"Ah, that makes sense"'),
            ("LETSGO", '"Time to head out!"'),
        ],
    },
    "abbreviation": {
        "instruction": (
            "Write a clue for an abbreviation, signalled with 'for short', "
            "'briefly' or 'abbr.'. Only expand what the letters plainly spell."
        ),
        "examples": [
            ("ASAP", "Memo urgency, for short"),
            ("ETC", "List ender, briefly"),
            ("EST", "Zone east of Chicago, in brief"),
        ],
    },
    "language-cue": {
        "instruction": (
            "Write a clue whose answer is a word in another language, signalled "
            "by a place or language cue (a city's article, a country's 'yes')."
        ),
        "examples": [
            ("DER", "Berlin article"),
            ("TAK", "Warsaw's \"yes\""),
            ("AMIGO", "Madrid pal"),
        ],
    },
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "clues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                "required": ["id", "text"],
            },
        }
    },
    "required": ["clues"],
}


@dataclass(frozen=True)
class Arm:
    name: str
    kind: str  # "model" or "file"
    value: str  # a model tag or a file path
    prompt: str = "lane"


def parse_arm_spec(spec: str) -> Arm:
    if "=" not in spec:
        raise ValueError(f"arm {spec!r} must look like NAME=model:<tag> or NAME=file:<path>")
    name, rest = spec.split("=", 1)
    prompt = "lane"
    if ",prompt=" in rest:
        rest, prompt = rest.rsplit(",prompt=", 1)
    if ":" not in rest:
        raise ValueError(f"arm {spec!r} must name a kind (model or file)")
    kind, value = rest.split(":", 1)
    if not name.strip() or kind not in {"model", "file"} or not value.strip():
        raise ValueError(f"arm {spec!r} is not NAME=model:<tag> or NAME=file:<path>")
    if prompt not in {"lane", "plain"}:
        raise ValueError(f"arm {spec!r} prompt must be lane or plain")
    return Arm(name.strip(), kind, value.strip(), prompt)


def load_answers(path: Path) -> list[dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("answers file must be a non-empty JSON list")
    answers, seen = [], set()
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"answers[{index}] must be an object")
        answer = str(item.get("answer", "")).strip().upper()
        entry_id = str(item.get("id") or f"A{index + 1:02d}")
        if not answer.isalpha() or entry_id in seen:
            raise ValueError(f"answers[{index}] needs a unique id and an A-Z answer")
        seen.add(entry_id)
        answers.append(
            {
                "id": entry_id,
                "answer": answer,
                "length": len(answer),
                "angle": str(item.get("angle") or "").strip(),
                "lane": item.get("lane") if item.get("lane") in LANES else "definition",
                "weekday": str(item.get("weekday") or "wednesday").lower(),
            }
        )
    return answers


def derived_seed(base_seed: int, arm_name: str, entry_id: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{arm_name}:{entry_id}".encode()).hexdigest()
    return int(digest[:8], 16) % (2**31)


def build_messages(entry: Mapping[str, Any], prompt: str) -> list[dict]:
    if prompt == "plain":
        system = _PLAIN_INSTRUCTION
        item = {"id": entry["id"], "answer": entry["answer"], "length": entry["length"]}
    else:
        lane = _LANE_PROMPTS[entry["lane"]]
        examples = "\n".join(f'  {answer} -> {clue}' for answer, clue in lane["examples"])
        system = (
            f"{lane['instruction']} Weekday: {entry['weekday']}. Never repeat the "
            f"answer or its stem. Examples (original):\n{examples}\n"
            "Reply as JSON with a clues array of {id, text}."
        )
        item = {"id": entry["id"], "answer": entry["answer"], "length": entry["length"]}
        if entry.get("angle"):
            item["angle"] = entry["angle"]
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": json.dumps({"entries": [item]}, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def _parse_clue(text: str, entry_id: str) -> str | None:
    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        clues = value.get("clues") if isinstance(value, dict) else None
        for clue in clues if isinstance(clues, list) else []:
            if isinstance(clue, dict) and clue.get("id") == entry_id:
                clue_text = clue.get("text")
                if isinstance(clue_text, str) and clue_text.strip():
                    return clue_text.strip()
    return None


def draft_model_arm(
    arm: Arm,
    answers: Sequence[Mapping[str, Any]],
    *,
    base_seed: int,
    environ: Mapping[str, str] | None = None,
    timeout: float = 120,
    tokens: int = 120,
    temperature: float = 0.7,
    chat: Callable[[ChatCall], Any] | None = None,
) -> dict:
    """Draft one clue per answer. A failure is recorded, never papered over."""
    adapter = resolve_adapter(arm.value, environ)
    send = chat or (lambda call: run_chat(adapter, call))
    clues: dict[str, str] = {}
    failures: dict[str, str] = {}
    seeds: dict[str, int] = {}
    started = time.monotonic()
    for entry in answers:
        seed = derived_seed(base_seed, arm.name, entry["id"])
        seeds[entry["id"]] = seed
        call = ChatCall(
            model=arm.value,
            messages=build_messages(entry, arm.prompt),
            schema=_SCHEMA,
            timeout=timeout,
            tokens=tokens,
            temperature=temperature,
            seed=seed,
            purpose="bakeoff",
        )
        try:
            response = send(call)
            content = response.json()["message"]["content"]
        except Exception as error:  # noqa: BLE001 - one bad call must not end the arm
            failures[entry["id"]] = type(error).__name__
            continue
        clue = _parse_clue(content, entry["id"])
        if clue is None:
            failures[entry["id"]] = "unparseable"
        else:
            clues[entry["id"]] = clue
    return {
        "arm": arm.name,
        "kind": "model",
        "model": arm.value,
        "prompt": arm.prompt,
        "adapter": adapter.receipt(),
        "seeds": seeds,
        "clues": clues,
        "failures": failures,
        "seconds": round(time.monotonic() - started, 3),
    }


def load_file_arm(arm: Arm, answers: Sequence[Mapping[str, Any]]) -> dict:
    raw = json.loads(Path(arm.value).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{arm.value} must be a JSON object mapping answer id to clue")
    clues = {
        entry["id"]: raw[entry["id"]].strip()
        for entry in answers
        if isinstance(raw.get(entry["id"]), str) and raw[entry["id"]].strip()
    }
    missing = {entry["id"]: "missing" for entry in answers if entry["id"] not in clues}
    return {
        "arm": arm.name,
        "kind": "file",
        "model": None,
        "prompt": None,
        "adapter": {"adapter": "file"},
        "seeds": {},
        "clues": clues,
        "failures": missing,
        "seconds": None,
    }


def build_cards(
    answers: Sequence[Mapping[str, Any]], arm_results: Sequence[Mapping[str, Any]], *, shuffle_seed: int
) -> tuple[list[dict], dict]:
    """Per-answer cards with arms shuffled and labelled, plus the secret key."""
    rng = random.Random(shuffle_seed)
    cards, key = [], {}
    for entry in answers:
        present = [r["arm"] for r in arm_results if entry["id"] in r["clues"]]
        rng.shuffle(present)
        key[entry["id"]] = {LABELS[i]: arm for i, arm in enumerate(present)}
        by_name = {r["arm"]: r for r in arm_results}
        cards.append(
            {
                "id": entry["id"],
                "answer": entry["answer"],
                "length": entry["length"],
                "weekday": entry["weekday"],
                "clues": {
                    LABELS[i]: by_name[arm]["clues"][entry["id"]] for i, arm in enumerate(present)
                },
            }
        )
    return cards, key


def build_sheet_html(cards: Sequence[Mapping[str, Any]], title: str = "Clue bake-off") -> str:
    payload = json.dumps(list(cards), ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:0 auto;padding:1rem 16px;color:#1d1d1f;background:#fff}}
@media (prefers-color-scheme:dark){{body{{color:#eee;background:#161618}}.card{{border-color:#444}}}}
.card{{border:1px solid #ccc;border-radius:10px;padding:.75rem 1rem;margin:1rem 0}}
.answer{{font-weight:700;letter-spacing:.08em}} .meta{{opacity:.7;font-size:.85rem}}
.clue{{display:flex;gap:.6rem;align-items:flex-start;margin:.5rem 0;flex-wrap:wrap}}
.clue b{{min-width:1.5rem}} .clue .t{{flex:1 1 14rem}} label{{white-space:nowrap;font-size:.9rem}}
button{{font:inherit;padding:.5rem 1rem}} #bar{{position:sticky;top:0;padding:.5rem 0;background:inherit}}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p>For each answer, mark clues you would <em>keep</em>, mark any whose wordplay you
<em>enjoyed</em>, and pick the single best one. Arms are shuffled and unlabelled.</p>
<div id="bar"><span id="count"></span> <button id="save">Download results</button></div>
<div id="cards"></div>
<script id="data" type="application/json">{payload}</script>
<script>
const cards = JSON.parse(document.getElementById('data').textContent);
const state = {{}};
const root = document.getElementById('cards');
cards.forEach(c => {{
  state[c.id] = {{best: null, keep: {{}}, wit: {{}}}};
  const div = document.createElement('div'); div.className = 'card';
  const head = document.createElement('div');
  head.innerHTML = '<span class="answer"></span> <span class="meta"></span>';
  head.children[0].textContent = c.answer;
  head.children[1].textContent = c.length + ' letters · ' + c.weekday;
  div.appendChild(head);
  Object.entries(c.clues).forEach(([label, text]) => {{
    const row = document.createElement('div'); row.className = 'clue';
    row.innerHTML = '<b></b><span class="t"></span>' +
      '<label><input type="checkbox" data-k="keep"> keep</label>' +
      '<label><input type="checkbox" data-k="wit"> enjoyed the wordplay</label>' +
      '<label><input type="radio" name="best-' + c.id + '"> best</label>';
    row.children[0].textContent = label; row.children[1].textContent = text;
    row.querySelectorAll('input').forEach(input => input.addEventListener('change', () => {{
      if (input.type === 'radio') state[c.id].best = label;
      else state[c.id][input.dataset.k][label] = input.checked;
      update();
    }}));
    div.appendChild(row);
  }});
  root.appendChild(div);
}});
function update() {{
  const done = cards.filter(c => state[c.id].best).length;
  document.getElementById('count').textContent = done + ' of ' + cards.length + ' have a best pick';
}}
document.getElementById('save').addEventListener('click', () => {{
  const blob = new Blob([JSON.stringify({{version: '{VERSION}-results', cards: state}}, null, 1)],
    {{type: 'application/json'}});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'bakeoff-results.json'; a.click();
}});
update();
</script></body></html>
"""


def score(key: Mapping[str, Mapping[str, str]], results: Mapping[str, Any]) -> dict:
    """Counts per arm from the judge's marks. Counts only: no clue text."""
    cards = results.get("cards") if isinstance(results, Mapping) else None
    if not isinstance(cards, Mapping):
        raise ValueError("results must carry a cards object")
    shown, kept, enjoyed, best = Counter(), Counter(), Counter(), Counter()
    judged = 0
    for card_id, labels in key.items():
        mark = cards.get(card_id)
        for arm in labels.values():
            shown[arm] += 1
        if not isinstance(mark, Mapping) or not mark.get("best"):
            continue
        judged += 1
        for label, arm in labels.items():
            kept[arm] += bool((mark.get("keep") or {}).get(label))
            enjoyed[arm] += bool((mark.get("wit") or {}).get(label))
        if mark.get("best") in labels:
            best[labels[mark["best"]]] += 1
    return {
        "cardsTotal": len(key),
        "cardsJudged": judged,
        "arms": {
            arm: {
                "cluesShown": shown[arm],
                "keep": kept[arm],
                "wordplayEnjoyed": enjoyed[arm],
                "best": best[arm],
            }
            for arm in sorted(shown)
        },
    }


def build_attestation(
    summary: Mapping[str, Any], arm_results: Sequence[Mapping[str, Any]], *, generated_at: str, base_seed: int
) -> dict:
    """Counts, timing and a digest. The clues themselves are never included."""
    report = {
        "version": VERSION,
        "generatedAt": generated_at,
        "kind": "owner-judged-blind",
        "scope": "one blind bake-off over a fixed answer list",
        "interpretation": "owner marks over shuffled, unlabelled arms; counts only",
        "uncertainty": [
            "a small card count bounds any rate only loosely",
            "arms differ in prompt, model and seed; this does not isolate one factor",
        ],
        "baseSeed": base_seed,
        "summary": summary,
        "arms": [
            {
                "arm": r["arm"],
                "kind": r["kind"],
                "model": r["model"],
                "prompt": r["prompt"],
                "adapter": r["adapter"],
                "clues": len(r["clues"]),
                "failures": len(r["failures"]),
                "seconds": r["seconds"],
            }
            for r in arm_results
        ],
    }
    report["studyDigest"] = "sha256:" + hashlib.sha256(
        canonical_clue_quality_json(report).encode("utf-8")
    ).hexdigest()
    return report


def refuse_evidence_dir(path: Path) -> None:
    """Answer-bearing files must not be written into the evidence tree."""
    parts = Path(path).resolve().parts
    for index in range(len(parts) - 1):
        if parts[index] == "docs" and parts[index + 1] == "evidence":
            raise ValueError("answer-bearing bake-off files must live outside docs/evidence")
