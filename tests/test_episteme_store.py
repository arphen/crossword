from types import SimpleNamespace

import pytest

import src.crossword.episteme_store as store


@pytest.mark.parametrize(
    ("stderr", "error_type"),
    [
        ("Error: Cannot find module 'typescript'", store.EpistemeRuntimeUnavailable),
        ('{"error":"Invalid episteme command"}', store.EpistemeCommandRejected),
        (
            '{"error":"Stale profile revision: expected 2, received 1"}',
            store.EpistemeRevisionConflict,
        ),
    ],
)
def test_reducer_bridge_separates_host_failures_from_command_errors(
    monkeypatch, stderr, error_type
):
    monkeypatch.setattr(store.shutil, "which", lambda _name: "/usr/bin/node")
    monkeypatch.setattr(
        store.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=2, stderr=stderr, stdout=""),
    )

    with pytest.raises(error_type):
        store.run_reducer({"operation": "apply"})
