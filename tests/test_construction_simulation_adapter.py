from src.crossword import construction_simulation_adapter as adapter


def _grid():
    return {
        "fill": ["CAT", "ARE", "TEN"],
        "entries": [
            {"num": 1, "dir": "A", "row": 0, "col": 0, "len": 3, "answer": "CAT"},
            {"num": 1, "dir": "D", "row": 0, "col": 1, "len": 3, "answer": "ARE"},
        ],
    }


def _estimate_envelope(**overrides):
    value = {
        "version": adapter.ESTIMATE_PROVENANCE_VERSION,
        "sourceKind": adapter.ESTIMATE_SOURCE,
        "sourceId": "fixture/editorial-assumptions-v1",
        "attestedBy": "fixture-reviewer",
        "calibrationStatus": "uncalibrated",
        "estimateFields": list(adapter.ESTIMATE_FIELDS),
        "assumptions": {
            "clueFamiliarity": "editorial prior for the supplied clue surface",
            "entryDifficulty": "editorial retrieval bucket for the supplied answer",
            "letterSupport": "editorial estimate of partial-pattern lift",
        },
        "derivedFillSignals": {
            "status": "excluded",
            "fields": list(adapter.DERIVED_FILL_SIGNALS),
            "reason": "construction-signals-never-become-player-estimates",
        },
    }
    value.update(overrides)
    return value


def _clue_entries(fill_score=None):
    entries = [
        {
            "id": "1A",
            "clueFamiliarity": 0.9,
            "entryDifficulty": 0.1,
            "letterSupport": 0.6,
        },
        {
            "id": "1D",
            "clueFamiliarity": 0.8,
            "entryDifficulty": 0.2,
            "letterSupport": 0.5,
        },
    ]
    if fill_score is not None:
        for entry in entries:
            entry["fillScore"] = fill_score
            entry["needsFoothold"] = fill_score < 60
    return entries


def _request(*, clue_entries=None, envelope=None):
    return adapter.build_simulation_request(
        _grid(),
        _clue_entries() if clue_entries is None else clue_entries,
        {"1A": "Feline", "1D": "Exist"},
        board_digest="sha256:" + "a" * 64,
        source_digest="sha256:" + "b" * 64,
        estimate_envelope=(_estimate_envelope() if envelope is None else envelope),
    )


def test_missing_explicit_estimates_is_not_invoked_without_fill_score_defaults():
    entries = [{"id": "1A"}, {"id": "1D"}]
    request = adapter.build_simulation_request(
        _grid(),
        entries,
        {"1A": "Feline", "1D": "Exist"},
        board_digest="sha256:" + "a" * 64,
        estimate_envelope=_estimate_envelope(),
    )

    assert request is None
    receipt = adapter.run_sibling_simulation(request)
    assert receipt["status"] == "not-invoked"
    assert receipt["reason"] == "explicit-estimates-required"
    assert receipt["requestDigest"] is None


def test_explicit_estimates_require_caller_attestation_envelope():
    request = adapter.build_simulation_request(
        _grid(),
        _clue_entries(),
        {"1A": "Feline", "1D": "Exist"},
    )

    assert request is None


def test_request_binds_typed_estimate_provenance_to_estimates_and_board():
    request = _request()

    assert request is not None
    provenance = request["estimateProvenance"]
    assert provenance["version"] == "sibling-estimate-provenance-v1"
    assert provenance["sourceKind"] == "caller-attested-assumptions"
    assert provenance["calibrationStatus"] == "uncalibrated"
    assert provenance["envelope"]["derivedFillSignals"]["status"] == "excluded"
    assert provenance["envelopeDigest"].startswith("sha256:")
    assert provenance["estimateDigest"].startswith("sha256:")
    assert provenance["bindingDigest"].startswith("sha256:")
    assert provenance["uncertainty"] == adapter.ESTIMATE_UNCERTAINTY


def test_derived_fill_signal_source_is_rejected_even_with_numeric_estimates():
    envelope = _estimate_envelope(sourceKind="derived-fill-signals")

    assert _request(envelope=envelope) is None


def test_fill_signals_are_excluded_and_cannot_change_estimate_binding():
    low = _request(clue_entries=_clue_entries(fill_score=3))
    high = _request(clue_entries=_clue_entries(fill_score=97))

    assert low is not None and high is not None
    assert low["entries"] == high["entries"]
    assert low["estimateProvenance"] == high["estimateProvenance"]
    assert low["estimateProvenance"]["envelope"]["derivedFillSignals"][
        "fields"
    ] == list(adapter.DERIVED_FILL_SIGNALS)


def test_estimate_provenance_changes_when_assumption_or_value_changes():
    baseline = _request()
    altered_values = _clue_entries()
    altered_values[0]["clueFamiliarity"] = 0.2
    changed_estimate = _request(clue_entries=altered_values)
    changed_source = _request(
        envelope=_estimate_envelope(
            sourceId="fixture/editorial-assumptions-v2",
        )
    )

    assert baseline is not None
    assert changed_estimate is not None
    assert changed_source is not None
    assert (
        baseline["estimateProvenance"]["estimateDigest"]
        != changed_estimate["estimateProvenance"]["estimateDigest"]
    )
    assert (
        baseline["estimateProvenance"]["bindingDigest"]
        != changed_estimate["estimateProvenance"]["bindingDigest"]
    )
    assert (
        baseline["estimateProvenance"]["envelopeDigest"]
        != changed_source["estimateProvenance"]["envelopeDigest"]
    )


def test_request_has_deterministic_crossings_and_digest_bound_inputs():
    request = _request()

    assert request is not None
    assert request["crossings"] == [
        {"entryId": "1A", "position": 1, "otherEntryId": "1D", "otherPosition": 0}
    ]
    assert adapter.run_sibling_simulation(None)["status"] == "not-invoked"


def test_run_rejects_tampered_or_unbound_provenance_before_bridge(monkeypatch):
    request = _request()
    assert request is not None
    request["estimateProvenance"]["bindingDigest"] = "sha256:" + "f" * 64
    monkeypatch.setattr(
        adapter,
        "_invoke_bridge",
        lambda _request: (_ for _ in ()).throw(
            AssertionError("invalid provenance must not reach the bridge")
        ),
    )

    receipt = adapter.run_sibling_simulation(request)

    assert receipt["status"] == "failed"
    assert receipt["reason"] == "estimate-provenance-invalid"
    assert receipt["estimateProvenanceDigest"] is None


def test_unavailable_bridge_fails_closed_without_fabricating_a_simulation(monkeypatch):
    request = _request()
    monkeypatch.setattr(
        adapter,
        "_invoke_bridge",
        lambda _request: {"status": "unavailable", "reason": "package-missing"},
    )

    receipt = adapter.run_sibling_simulation(request)

    assert receipt["status"] == "failed"
    assert receipt["reason"] == "package-missing"
    assert receipt["requestDigest"].startswith("sha256:")
    assert receipt["estimateSource"] == "caller-attested-assumptions"
    assert (
        receipt["estimateProvenanceDigest"]
        == request["estimateProvenance"]["bindingDigest"]
    )
    assert receipt["resultDigest"] is None
    assert "completionProbability" not in receipt


def test_invoked_result_binds_request_and_result_digests(monkeypatch):
    request = _request()
    monkeypatch.setattr(
        adapter,
        "_invoke_bridge",
        lambda _request: {
            "status": "invoked",
            "simulator": {"source": "fixture"},
            "result": {"status": "simulated", "route": [], "stalledEntries": []},
        },
    )

    receipt = adapter.run_sibling_simulation(request)

    assert receipt["status"] == "invoked"
    assert receipt["requestDigest"] == adapter._digest(request)
    assert receipt["resultDigest"] == adapter._digest(receipt["result"])
    assert receipt["estimateProvenance"] == request["estimateProvenance"]
    assert receipt["uncertainty"] == adapter.ESTIMATE_UNCERTAINTY


def test_pinned_sibling_source_bridge_can_invoke_real_simulator():
    request = _request()

    receipt = adapter.run_sibling_simulation(request)

    assert receipt["status"] == "invoked"
    assert receipt["simulator"]["protocol"] == "explicit-estimates-greedy-v1"
    assert receipt["result"]["status"] in {"simulated", "invalid"}
