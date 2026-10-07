"""Tests for the blind clue bake-off (G1). Offline; models are fixtures."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from crossword import clue_bakeoff as bo
from crossword import clue_model as cm
from crossword.clue_quality_evaluation import canonical_clue_quality_json

ROOT = Path(__file__).resolve().parents[1]
ANSWERS = [
    {"id": "A01", "answer": "scales", "angle": "musical scales vs fish scales", "lane": "misdirection"},
    {"id": "A02", "answer": "Tide"},
    {"id": "A03", "answer": "NOWAY", "lane": "spoken", "weekday": "Thursday"},
]


@pytest.fixture(autouse=True)
def _clean():
    cm.clear_trace()
    cm.clear_fixtures()
    yield
    cm.clear_trace()
    cm.clear_fixtures()


@pytest.fixture
def answers(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(ANSWERS), encoding="utf-8")
    return bo.load_answers(path)


def echo_responder(call):
    entry = json.loads(call.messages[1]["content"])["entries"][0]
    return json.dumps({"clues": [{"id": entry["id"], "text": f"Clue for {entry['answer'].lower()}"}]})


def test_arm_specs():
    assert bo.parse_arm_spec("small=model:llama3.2:3b") == bo.Arm("small", "model", "llama3.2:3b", "lane")
    assert bo.parse_arm_spec("plain=model:gemma3:12b,prompt=plain").prompt == "plain"
    assert bo.parse_arm_spec("cloud=model:cloud:muse").value == "cloud:muse"
    assert bo.parse_arm_spec("cur=file:/tmp/x.json").kind == "file"
    for bad in ("nokind", "x=thing:y", "x=model:", "=model:y", "x=model:y,prompt=wild"):
        with pytest.raises(ValueError):
            bo.parse_arm_spec(bad)


def test_answers_are_normalised_and_validated(answers, tmp_path):
    assert [a["answer"] for a in answers] == ["SCALES", "TIDE", "NOWAY"]
    assert answers[1]["lane"] == "definition" and answers[1]["weekday"] == "wednesday"
    assert answers[2]["weekday"] == "thursday"
    assert answers[0]["length"] == 6
    duplicate_ids = [{"id": "A01", "answer": "B"}, {"id": "A01", "answer": "C"}]
    for index, bad in enumerate(([], [{"answer": "NO WAY"}], duplicate_ids)):
        path = tmp_path / f"bad{index}.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            bo.load_answers(path)


def test_seeds_are_deterministic_and_vary_by_arm_and_entry():
    assert bo.derived_seed(1, "a", "A01") == bo.derived_seed(1, "a", "A01")
    assert len({bo.derived_seed(1, "a", "A01"), bo.derived_seed(1, "b", "A01"), bo.derived_seed(1, "a", "A02"), bo.derived_seed(2, "a", "A01")}) == 4


def test_lane_prompt_carries_angle_and_examples_plain_does_not(answers):
    lane = bo.build_messages(answers[0], "lane")
    plain = bo.build_messages(answers[0], "plain")
    assert "SCALES" in lane[0]["content"] and "Piano student" in lane[0]["content"]
    assert json.loads(lane[1]["content"])["entries"][0]["angle"] == "musical scales vs fish scales"
    assert "angle" not in json.loads(plain[1]["content"])["entries"][0]
    assert "Examples" not in plain[0]["content"]


def test_every_prompt_passes_the_cloud_payload_guard(answers):
    for entry in answers:
        for style in ("lane", "plain"):
            keys = cm._payload_keys(bo.build_messages(entry, style))
            assert keys is not None and keys <= cm.CLOUD_PAYLOAD_KEYS


def test_draft_arm_uses_adapters_pins_seeds_and_records_failures(answers):
    calls = []

    def responder(call):
        calls.append(call)
        entry = json.loads(call.messages[1]["content"])["entries"][0]
        if entry["id"] == "A02":
            return "I cannot do this"
        if entry["id"] == "A03":
            raise ConnectionError("down")
        return echo_responder(call)

    cm.register_fixture("mixed", responder)
    arm = bo.Arm("m", "model", "fixture:mixed")
    result = bo.draft_model_arm(arm, answers, base_seed=5)
    assert result["clues"] == {"A01": "Clue for scales"}
    assert result["failures"] == {"A02": "unparseable", "A03": "ConnectionError"}
    assert result["seeds"] == {e["id"]: bo.derived_seed(5, "m", e["id"]) for e in answers}
    assert all(c.purpose == "bakeoff" and c.seed == result["seeds"][json.loads(c.messages[1]["content"])["entries"][0]["id"]] for c in calls)
    assert result["adapter"]["adapter"] == "fixture"


def test_cloud_arm_fails_loudly_when_the_extension_is_off(answers):
    with pytest.raises(cm.CloudDisabled):
        bo.draft_model_arm(bo.Arm("c", "model", "cloud:muse"), answers, base_seed=1, environ={})


def test_json_wrapped_in_prose_is_still_parsed():
    text = 'Sure! {"clues":[{"id":"A01","text":"Fine clue"}]} hope that helps'
    assert bo._parse_clue(text, "A01") == "Fine clue"
    assert bo._parse_clue(text, "A02") is None
    assert bo._parse_clue('{"clues":[{"id":"A01","text":"  "}]}', "A01") is None


def make_results(answers):
    cm.register_fixture("echo", echo_responder)
    first = bo.draft_model_arm(bo.Arm("first", "model", "fixture:echo"), answers, base_seed=1)
    second = {**first, "arm": "second", "clues": {k: v + " too" for k, v in first["clues"].items()}}
    third = {**first, "arm": "third", "clues": {"A01": "Only one"}, "failures": {"A02": "x", "A03": "x"}}
    return [first, second, third]


def test_cards_are_shuffled_deterministically_and_skip_missing_clues(answers):
    arms = make_results(answers)
    cards, key = bo.build_cards(answers, arms, shuffle_seed=3)
    assert (cards, key) == bo.build_cards(answers, arms, shuffle_seed=3)
    assert set(key["A01"].values()) == {"first", "second", "third"}
    assert set(key["A02"].values()) == {"first", "second"}
    assert all(set(card["clues"]) == set(key[card["id"]]) for card in cards)
    assert "first" not in json.dumps(cards) and "arm" not in json.dumps(cards)
    orders = {tuple(bo.build_cards(answers, arms, shuffle_seed=s)[1]["A01"].values()) for s in range(12)}
    assert len(orders) > 1


def test_sheet_is_self_contained_and_escapes_clue_text():
    cards = [{"id": "A01", "answer": "X", "length": 1, "weekday": "wednesday",
              "clues": {"A": "</script><img src=x onerror=alert(1)>"}}]
    page = bo.build_sheet_html(cards, title="T <b>")
    assert "</script><img" not in page
    assert "<\\/script>" in page
    assert "T &lt;b&gt;" in page
    assert "http://" not in page and "https://" not in page


def test_scoring_counts_per_arm(answers):
    arms = make_results(answers)
    _cards, key = bo.build_cards(answers, arms, shuffle_seed=3)
    label_of = {card_id: {arm: label for label, arm in labels.items()} for card_id, labels in key.items()}
    results = {"cards": {
        "A01": {"best": label_of["A01"]["second"],
                "keep": {label_of["A01"]["second"]: True, label_of["A01"]["first"]: True},
                "wit": {label_of["A01"]["second"]: True}},
        "A02": {"best": label_of["A02"]["first"], "keep": {}, "wit": {}},
    }}
    summary = bo.score(key, results)
    assert summary["cardsTotal"] == 3 and summary["cardsJudged"] == 2
    assert summary["arms"]["second"] == {"cluesShown": 3, "keep": 1, "wordplayEnjoyed": 1, "best": 1}
    assert summary["arms"]["first"]["keep"] == 1 and summary["arms"]["first"]["best"] == 1
    assert summary["arms"]["third"]["cluesShown"] == 1 and summary["arms"]["third"]["best"] == 0
    with pytest.raises(ValueError):
        bo.score(key, {})


def test_attestation_is_counts_only_and_its_digest_verifies(answers):
    arms = make_results(answers)
    _cards, key = bo.build_cards(answers, arms, shuffle_seed=3)
    summary = bo.score(key, {"cards": {}})
    report = bo.build_attestation(summary, arms, generated_at="2026-10-06T00:00:00+00:00", base_seed=1)
    text = json.dumps(report)
    for entry in answers:
        assert entry["answer"] not in text
    assert "Clue for" not in text and "Only one" not in text
    claimed = report.pop("studyDigest")
    recomputed = "sha256:" + hashlib.sha256(canonical_clue_quality_json(report).encode()).hexdigest()
    assert claimed == recomputed
    assert report["version"] == "private-clue-bakeoff-v1"
    assert {a["arm"]: a["clues"] for a in report["arms"]} == {"first": 3, "second": 3, "third": 1}
    assert {a["arm"]: a["failures"] for a in report["arms"]} == {"first": 0, "second": 0, "third": 2}


def test_answer_bearing_files_refuse_the_evidence_tree():
    with pytest.raises(ValueError):
        bo.refuse_evidence_dir(ROOT / "docs" / "evidence" / "x")
    bo.refuse_evidence_dir(ROOT / "docs" / "other")


def test_cli_prepare_and_score_end_to_end_with_file_arms(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("clue_bakeoff_cli", ROOT / "scripts" / "clue-bakeoff.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps(ANSWERS), encoding="utf-8")
    one, two = tmp_path / "one.json", tmp_path / "two.json"
    one.write_text(json.dumps({"A01": "First take", "A02": "Another", "A03": "Third"}), encoding="utf-8")
    two.write_text(json.dumps({"A01": "Second take", "A03": "Spoken"}), encoding="utf-8")
    out = tmp_path / "private"
    assert cli.main(["prepare", "--answers", str(answers), "--out-dir", str(out),
                     "--arm", f"one=file:{one}", "--arm", f"two=file:{two}"]) == 0
    assert {p.name for p in out.iterdir()} == {"answers.json", "arms.json", "key.json", "sheet.html"}
    key = json.loads((out / "key.json").read_text())
    assert set(key) == {"A01", "A02", "A03"} and len(key["A02"]) == 1
    marks = {"cards": {cid: {"best": next(iter(labels)), "keep": {next(iter(labels)): True}, "wit": {}}
                       for cid, labels in key.items()}}
    results = tmp_path / "results.json"
    results.write_text(json.dumps(marks), encoding="utf-8")
    attest = tmp_path / "attest.json"
    assert cli.main(["score", "--out-dir", str(out), "--results", str(results),
                     "--attest-out", str(attest)]) == 0
    report = json.loads(attest.read_text())
    assert report["summary"]["cardsJudged"] == 3
    assert "First take" not in attest.read_text()
    with pytest.raises(SystemExit):
        cli.main(["prepare", "--answers", str(answers), "--out-dir", str(out), "--arm", f"one=file:{one}"])
    with pytest.raises(ValueError):
        cli.main(["prepare", "--answers", str(answers), "--out-dir", str(ROOT / "docs" / "evidence" / "z"),
                  "--arm", f"one=file:{one}", "--arm", f"two=file:{two}"])
