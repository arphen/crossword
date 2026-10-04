"""Contract checks for the authored first calibration stimulus bank."""

from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re

import pytest


CATALOG_PATH = Path(__file__).parents[1] / "src" / "crossword" / "future_catalog.json"
EXPECTED_KINDS = {
    "object",
    "abstract_form",
    "texture_material",
    "color",
    "numeral",
    "word",
    "typographic_mark",
}
ALLOWED_TRANSFORMATIONS = {
    "rotate_quarter_turn",
    "flip_horizontal",
    "scale_uniform",
    "translate",
    "monochrome",
}
SALIENCE_GROUPS = {"low", "medium", "high"}
KNOWN_LEGACY_IDS = {
    "thread",
    "stone",
    "cube",
    "key",
    "circle",
    "zero",
    "fork",
    "map",
    "dots",
    "seed",
    "shell",
    "orbit",
    "echo",
    "elsewhere",
    "moss",
    "03:17",
    "almost",
    "∴",
    "afterglow",
    "threshold",
    "salt",
    "between",
    "again",
    "?",
}
TRACE_TOKENS = {
    "echo",
    "elsewhere",
    "moss",
    "03:17",
    "almost",
    "∴",
    "afterglow",
    "threshold",
    "salt",
    "between",
    "again",
    "?",
}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")


def load_catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def validate_stimuli_bank(bank):
    """Validate the authored V1 fields, salience balance, and inventory bounds."""
    if not isinstance(bank, dict) or bank.get("version") != 1:
        raise ValueError("unsupported stimuli bank version")
    if bank.get("schema") != "StimulusV1":
        raise ValueError("unsupported stimulus schema")
    if set(bank.get("kinds", [])) != EXPECTED_KINDS:
        raise ValueError("unexpected stimulus kinds")

    items = bank.get("items")
    if not isinstance(items, list) or not 48 <= len(items) <= 72:
        raise ValueError("stimulus bank must contain 48–72 items")

    ids = []
    asset_refs = []
    kind_counts = Counter()
    salience_by_kind = defaultdict(Counter)
    salience_counts = Counter()
    legacy_id_owners = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("stimulus must be an object")
        required = {
            "id",
            "version",
            "kind",
            "asset_ref",
            "description",
            "accessible_label",
            "language",
            "facets",
            "association_seeds",
            "provenance",
            "salience_group",
            "contrast_family",
            "allowed_transformations",
        }
        if not required <= item.keys():
            raise ValueError("stimulus is missing required fields")
        if (
            not isinstance(item["id"], str)
            or not ID_PATTERN.fullmatch(item["id"])
            or type(item["version"]) is not int
            or item["version"] != 1
        ):
            raise ValueError("invalid stable stimulus identity")
        if item["kind"] not in EXPECTED_KINDS:
            raise ValueError("invalid stimulus kind")
        if not isinstance(item["asset_ref"], str) or item["asset_ref"] != (
            f"catalog://future/stimuli/v1/{item['id']}"
        ):
            raise ValueError("asset reference must be stable and id-addressed")
        if item["id"] in ids:
            raise ValueError("duplicate stimulus ids")
        ids.append(item["id"])
        asset_refs.append(item["asset_ref"])

        if (
            not isinstance(item["description"], str)
            or not 20 <= len(item["description"]) <= 240
            or not isinstance(item["accessible_label"], str)
            or not 4 <= len(item["accessible_label"]) <= 120
        ):
            raise ValueError("description or accessible label is outside bounds")
        language = item["language"]
        if language is not None and (
            not isinstance(language, str) or not LANGUAGE_PATTERN.fullmatch(language)
        ):
            raise ValueError("invalid optional language tag")
        if item["kind"] == "word" and language is None:
            raise ValueError("word stimuli require a language tag")
        legacy = item.get("legacy_ids", [])
        if (
            not isinstance(legacy, list)
            or any(
                not isinstance(value, str) or value not in KNOWN_LEGACY_IDS
                for value in legacy
            )
            or len(legacy) != len(set(legacy))
        ):
            raise ValueError("invalid legacy rendering bindings")
        for value in legacy:
            if value in legacy_id_owners:
                raise ValueError("legacy rendering id is bound more than once")
            legacy_id_owners[value] = item["id"]

        swatch = item.get("swatch_hex")
        if item["kind"] == "color":
            if not isinstance(swatch, str) or not re.fullmatch(
                r"#[0-9A-Fa-f]{6}", swatch
            ):
                raise ValueError("color stimulus needs an explicit hex swatch")
        elif swatch is not None:
            raise ValueError("only color stimuli may define a color swatch")

        facets = item["facets"]
        if (
            not isinstance(facets, list)
            or not 2 <= len(facets) <= 6
            or any(
                not isinstance(facet, str) or not 2 <= len(facet) <= 40
                for facet in facets
            )
            or len({facet.casefold() for facet in facets if isinstance(facet, str)})
            != len(facets)
        ):
            raise ValueError("invalid descriptive facets")
        seeds = item["association_seeds"]
        if (
            not isinstance(seeds, list)
            or not 3 <= len(seeds) <= 6
            or any(
                not isinstance(seed, str) or not 2 <= len(seed) <= 40 for seed in seeds
            )
            or len({seed.casefold() for seed in seeds if isinstance(seed, str)})
            != len(seeds)
        ):
            raise ValueError("invalid association seeds")

        provenance = item["provenance"]
        if (
            not isinstance(provenance, dict)
            or not isinstance(provenance.get("source"), str)
            or not provenance["source"].strip()
            or provenance.get("creator") != "Crossword project"
            or provenance.get("asset_ref") != item["asset_ref"]
            or provenance.get("third_party_material") is not False
        ):
            raise ValueError("missing explicit first-party provenance")
        if item["salience_group"] not in SALIENCE_GROUPS:
            raise ValueError("invalid salience group")
        if (
            not isinstance(item["contrast_family"], str)
            or not item["contrast_family"].strip()
        ):
            raise ValueError("missing contrast family")
        transformations = item["allowed_transformations"]
        if (
            not isinstance(transformations, list)
            or not 1 <= len(transformations) <= 4
            or len(set(transformations)) != len(transformations)
            or not set(transformations) <= ALLOWED_TRANSFORMATIONS
        ):
            raise ValueError("invalid allowed transformations")

        kind_counts[item["kind"]] += 1
        salience_by_kind[item["kind"]][item["salience_group"]] += 1
        salience_counts[item["salience_group"]] += 1

    if len(ids) != len(set(ids)):
        raise ValueError("duplicate stimulus ids")
    if len(asset_refs) != len(set(asset_refs)):
        raise ValueError("duplicate stimulus asset refs")
    if set(legacy_id_owners) != KNOWN_LEGACY_IDS:
        raise ValueError("legacy rendering bindings must cover existing choices")
    if (
        set(kind_counts) != EXPECTED_KINDS
        or min(kind_counts.values()) < 8
        or max(kind_counts.values()) > 14
    ):
        raise ValueError("stimulus kinds are missing or underrepresented")
    if (
        set(salience_counts) != SALIENCE_GROUPS
        or max(salience_counts.values()) - min(salience_counts.values()) > 1
    ):
        raise ValueError("salience groups are imbalanced")
    for groups in salience_by_kind.values():
        if (
            set(groups) != SALIENCE_GROUPS
            or max(groups.values()) - min(groups.values()) > 1
        ):
            raise ValueError("salience is imbalanced within a stimulus kind")


def validate_trace_bindings(catalog):
    traces = catalog["traces"]
    if len(traces) != 12 or len(set(traces)) != len(traces):
        raise ValueError("legacy trace choices must be twelve unique tokens")
    owners = {}
    for item in catalog["stimuli"]["items"]:
        for token in item.get("legacy_ids", []):
            if token in traces:
                if token in owners:
                    raise ValueError("trace token is bound more than once")
                if item["kind"] not in {"word", "numeral", "typographic_mark"}:
                    raise ValueError("trace must map to a lexical or sign stimulus")
                owners[token] = item
    if set(owners) != set(traces):
        raise ValueError("every legacy trace needs one stable stimulus binding")


def test_authored_stimuli_bank_has_versioned_coverage_and_balanced_salience():
    catalog = load_catalog()
    assert {"objects", "companions", "traces", "days", "languages"} <= catalog.keys()
    assert len(catalog["objects"]) == 6
    assert len(catalog["companions"]) == 6
    assert len(catalog["traces"]) == 12
    assert len(catalog["days"]) == 7

    bank = catalog["stimuli"]
    validate_stimuli_bank(bank)
    assert len(bank["items"]) == 64
    assert Counter(item["kind"] for item in bank["items"]) == {
        "object": 9,
        "abstract_form": 8,
        "texture_material": 8,
        "color": 8,
        "numeral": 9,
        "word": 14,
        "typographic_mark": 8,
    }
    validate_trace_bindings(catalog)
    trace_owners = {
        token: item
        for item in bank["items"]
        for token in item.get("legacy_ids", [])
        if token in TRACE_TOKENS
    }
    assert set(TRACE_TOKENS) == set(catalog["traces"])
    assert set(trace_owners) == set(catalog["traces"])
    assert all(
        item["kind"] in {"word", "numeral", "typographic_mark"}
        for item in trace_owners.values()
    )
    assert (
        len({item["swatch_hex"] for item in bank["items"] if item["kind"] == "color"})
        == 8
    )


@pytest.mark.parametrize("corruption", ["duplicate", "missing"])
def test_trace_bindings_require_exactly_one_stable_stimulus(corruption):
    catalog = load_catalog()
    if corruption == "duplicate":
        echo = next(
            item for item in catalog["stimuli"]["items"] if item["id"] == "word-echo"
        )
        echo["legacy_ids"].append("moss")
        message = "trace token is bound more than once"
    else:
        moss = next(
            item for item in catalog["stimuli"]["items"] if item["id"] == "word-moss"
        )
        moss["legacy_ids"].remove("moss")
        message = "every legacy trace needs one stable stimulus binding"

    with pytest.raises(ValueError, match=message):
        validate_trace_bindings(catalog)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_id", "duplicate stimulus ids"),
        ("bad_language", "invalid optional language tag"),
        ("too_few_facets", "invalid descriptive facets"),
        ("too_many_seeds", "invalid association seeds"),
        ("unknown_transform", "invalid allowed transformations"),
        ("duplicate_legacy_id", "legacy rendering id is bound more than once"),
        ("invalid_swatch", "color stimulus needs an explicit hex swatch"),
        ("unbalanced_kind", "stimulus kinds are missing or underrepresented"),
    ],
)
def test_catalog_validation_rejects_malformed_stimuli(mutation, message):
    bank = deepcopy(load_catalog()["stimuli"])
    first = bank["items"][0]
    if mutation == "duplicate_id":
        bank["items"].append(deepcopy(first))
    elif mutation == "bad_language":
        first["language"] = "English"
    elif mutation == "too_few_facets":
        first["facets"] = [first["facets"][0]]
    elif mutation == "too_many_seeds":
        first["association_seeds"] = [
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
        ]
    elif mutation == "unknown_transform":
        first["allowed_transformations"].append("change_semantic_meaning")
    elif mutation == "duplicate_legacy_id":
        bank["items"][1]["legacy_ids"] = ["thread"]
    elif mutation == "invalid_swatch":
        next(item for item in bank["items"] if item["kind"] == "color")[
            "swatch_hex"
        ] = "blue"
    elif mutation == "unbalanced_kind":
        first["kind"] = "abstract_form"
        bank["items"][1]["kind"] = "abstract_form"

    with pytest.raises(ValueError, match=message):
        validate_stimuli_bank(bank)
