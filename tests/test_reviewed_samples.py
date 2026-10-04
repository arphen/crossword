"""Contract tests for the model-free reviewed warm-up route."""

from tests.test_api_isolated import api, no_network  # noqa: F401


def test_reviewed_sample_is_registered_and_replayable(api):
    response = api.app.test_client().get(
        "/api/future/reviewed-samples/sator-square-v1?weekday=thursday"
    )

    assert response.status_code == 200
    payload = response.json
    assert payload["provenance"] == {
        "source": "reviewed-sample",
        "version": "reviewed-sample-v1",
        "sampleId": "sator-square-v1",
        "weekday": "thursday",
        "seed": 0,
        "experimental": False,
        "review": {
            "status": "reviewed-authored",
            "license": "CC0-1.0",
            "answerSource": "hand-authored-word-square",
            "semanticStatus": "authored-sample",
        },
    }
    assert payload["metadata"]["title"] == "The First Square"
    assert len(payload["entries"]) == 10
    assert payload["puzzleManifest"]["integrity"]["algorithm"] == "sha256"
    assert len(payload["puzzleManifest"]["integrity"]["value"]) == 64

    replay = api.app.test_client().get(
        "/api/future/reviewed-samples/sator-square-v1?weekday=thursday"
    )
    assert replay.status_code == 200
    assert replay.json["puzzleManifest"] == payload["puzzleManifest"]


def test_reviewed_sample_rejects_unknown_id_and_weekday(api):
    client = api.app.test_client()
    assert client.get("/api/future/reviewed-samples/unknown").status_code == 404
    invalid = client.get(
        "/api/future/reviewed-samples/sator-square-v1?weekday=not-a-day"
    )
    assert invalid.status_code == 400
    assert invalid.json == {"error": "Invalid weekday"}
