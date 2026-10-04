import json

import src.crossword.private_domain_hints as domain_hints


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_missing_private_domain_hints_are_explicitly_not_configured(monkeypatch):
    monkeypatch.delenv(domain_hints.PRIVATE_DOMAIN_HINTS_ENV, raising=False)

    result = domain_hints.load_private_domain_hints(fill_words=set())

    assert result["status"] == "not-configured"
    assert result["terms"] == []
    assert result["admissionStatus"] == "private-unadmitted"


def test_private_domain_hints_keep_only_placeable_terms_and_bind_file_digest(
    tmp_path,
):
    path = tmp_path / "physics.json"
    _write(
        path,
        {
            "version": domain_hints.PRIVATE_DOMAIN_HINTS_VERSION,
            "domainId": "physics",
            "label": "Physics",
            "terms": ["ENTROPY", "BOHR", "QUARK"],
            "source": {
                "id": "local-physics-notes",
                "version": "2026-09",
                "artifactSha256": "a" * 64,
            },
        },
    )

    result = domain_hints.load_private_domain_hints(
        path=path,
        fill_words={"ENTROPY", "QUARK"},
    )

    assert result["status"] == "loaded"
    assert result["terms"] == ["BOHR", "ENTROPY", "QUARK"]
    assert result["placeableTerms"] == ["ENTROPY", "QUARK"]
    assert len(result["artifactSha256"]) == 64
    assert result["semanticStatus"] == "not-established"
    assert result["admissionStatus"] == "private-unadmitted"
    receipt = domain_hints.private_domain_hint_receipt(result)
    assert receipt == {
        "version": domain_hints.PRIVATE_DOMAIN_HINTS_VERSION,
        "status": "loaded",
        "semanticStatus": "not-established",
        "admissionStatus": "private-unadmitted",
        "termCount": 3,
        "placeableCount": 2,
        "uncertainty": ["local-hint-file-unreviewed", "semantic-sense-unverified"],
        "domainId": "physics",
        "label": "Physics",
        "artifactSha256": result["artifactSha256"],
        "source": {
            "id": "local-physics-notes",
            "version": "2026-09",
            "artifactSha256": "a" * 64,
        },
    }


def test_malformed_configured_private_domain_hints_fail_closed(tmp_path):
    path = tmp_path / "bad.json"
    _write(
        path,
        {
            "version": domain_hints.PRIVATE_DOMAIN_HINTS_VERSION,
            "domainId": "physics",
            "label": "Physics",
            "terms": ["ENTROPY", "ENTROPY"],
        },
    )

    result = domain_hints.load_private_domain_hints(path=path, fill_words={"ENTROPY"})

    assert result["status"] == "unavailable"
    assert result["terms"] == []
    assert result["reason"] == "domain-term-duplicate"


def test_theme_prompt_prioritizes_placeable_domain_terms_without_claiming_grounding(
    monkeypatch,
):
    captured = {}

    def fake_chat(_model, messages, _schema, **_kwargs):
        captured["system"] = messages[0]["content"]
        captured["user"] = messages[1]["content"]
        return {"themes": ["ECHO", "MOSS", "THREAD"]}

    monkeypatch.setattr(domain_hints, "load_private_domain_hints", lambda **_kwargs: {
        "version": domain_hints.PRIVATE_DOMAIN_HINTS_VERSION,
        "status": "loaded",
        "domainId": "physics",
        "label": "Physics",
        "terms": ["BOHR", "QUARK"],
        "placeableTerms": ["BOHR", "QUARK"],
        "semanticStatus": "not-established",
        "admissionStatus": "private-unadmitted",
    })
    monkeypatch.setattr(
        domain_hints,
        "private_domain_hint_receipt",
        lambda value: {"status": value.get("status")},
    )
    # The generator imports the function symbols directly; patch its binding too.
    monkeypatch.setattr(
        "src.crossword.private_puzzle_generation.load_private_domain_hints",
        lambda **_kwargs: {
            "version": domain_hints.PRIVATE_DOMAIN_HINTS_VERSION,
            "status": "loaded",
            "domainId": "physics",
            "label": "Physics",
            "terms": ["BOHR", "QUARK"],
            "placeableTerms": ["BOHR", "QUARK"],
            "semanticStatus": "not-established",
            "admissionStatus": "private-unadmitted",
        },
    )
    monkeypatch.setattr(
        "src.crossword.private_puzzle_generation._chat", fake_chat
    )

    from src.crossword import private_puzzle_generation as generator

    context = generator._profile_context(
        type("Starting", (), {"profile": {}, "draft": {}})(),
        {"projection": {"claims": [], "associations": [], "knowledge": []}},
    )
    themes = generator._make_themes("gemma4:26b", context, "wednesday")

    assert themes[:2] == ["BOHR", "QUARK"]
    assert "private and unadmitted" in captured["system"]
    assert "BOHR" in captured["user"]
