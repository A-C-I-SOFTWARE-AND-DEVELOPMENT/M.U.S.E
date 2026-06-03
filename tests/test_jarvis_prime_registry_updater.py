"""REG-1 model-registry updater tests.

Covers the pure diff, the owner-gated proposal emission, and the fail-open
end-to-end pass. No network: the live manifest is injected or monkeypatched.
"""

from typing import Any, cast
from unittest.mock import patch

from hermes_cli.jarvis_prime.registry_updater import (
    RegistryDelta,
    diff_provider_models,
    load_local_catalog,
    propose_registry_updates,
    render_deltas,
    run_registry_update,
)
from hermes_cli.jarvis_prime.self_update import (
    ProposalBook,
    ProposalKind,
    ProposalStatus,
)


def _catalog(providers: dict) -> dict:
    return {"version": 1, "providers": providers}


# -- pure diff --------------------------------------------------------------


def test_diff_detects_added_and_removed():
    local = _catalog({"openrouter": {"models": [{"id": "a"}, {"id": "b"}]}})
    remote = _catalog({"openrouter": {"models": [{"id": "b"}, {"id": "c"}]}})
    deltas = diff_provider_models(local, remote)
    assert len(deltas) == 1
    d = deltas[0]
    assert d.provider == "openrouter"
    assert d.added_ids == ("c",)
    assert d.removed_ids == ("a",)


def test_diff_in_sync_returns_empty():
    cat = _catalog({"novita": {"models": [{"id": "x"}, {"id": "y"}]}})
    assert diff_provider_models(cat, cat) == []


def test_diff_ignores_provider_absent_from_remote():
    # A provider with no live manifest block is "no opinion" — never proposed
    # for deletion of its repo entries.
    local = _catalog({"ollama-local": {"models": [{"id": "llama3.2"}]}})
    remote = _catalog({})
    assert diff_provider_models(local, remote) == []


def test_diff_handles_bare_string_ids():
    local = _catalog({"nous": {"models": ["hermes-3"]}})
    remote = _catalog({"nous": {"models": ["hermes-3", "hermes-4"]}})
    deltas = diff_provider_models(local, remote)
    assert deltas[0].added_ids == ("hermes-4",)


def test_diff_tolerates_garbage_input():
    # Deliberately wrong types — the function must be defensive, not raise.
    assert diff_provider_models(None, None) == []
    assert diff_provider_models(cast(Any, "oops"), cast(Any, {"providers": "nope"})) == []


def test_diff_matches_across_id_conventions():
    # Repo keys on a bare id plus a fully-qualified model slug; the live
    # manifest keys on the slug as its id. The same model must NOT be reported
    # as both added and removed.
    local = _catalog(
        {"openrouter": {"models": [{"id": "llama-3.3-70b", "model": "meta-llama/llama-3.3-70b-instruct"}]}}
    )
    remote = _catalog(
        {"openrouter": {"models": [{"id": "meta-llama/llama-3.3-70b-instruct"}]}}
    )
    assert diff_provider_models(local, remote) == []


# -- risk classification ----------------------------------------------------


def test_added_models_are_rc3_new_surface():
    d = RegistryDelta(provider="p", added_ids=("new",))
    assert d.risk_class == "RC3"


def test_only_removals_are_rc2():
    d = RegistryDelta(provider="p", removed_ids=("old",))
    assert d.risk_class == "RC2"


# -- proposal emission (owner-gated) ----------------------------------------


def test_proposals_are_queued_not_applied():
    deltas = [RegistryDelta(provider="openrouter", added_ids=("c",), removed_ids=("a",))]
    book = ProposalBook()
    proposals = propose_registry_updates(deltas, book)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.kind is ProposalKind.MODEL_REGISTRY_UPDATE
    assert p.target_path == "config/model-catalog.yaml"
    # RC3 (has additions) ⇒ explicitly needs owner approval; nothing applied.
    assert p.risk_class == "RC3"
    assert p.status == ProposalStatus.NEEDS_OWNER_APPROVAL
    assert p.status != ProposalStatus.APPLIED
    assert book.pending()
    assert "add 1 model" in p.diff_intent
    assert "remove 1 stale model" in p.diff_intent


def test_empty_deltas_emit_no_proposals():
    book = ProposalBook()
    assert propose_registry_updates([], book) == []
    assert not book.pending()


# -- end-to-end (fail-open) -------------------------------------------------


def test_run_registry_update_no_op_when_offline():
    book = ProposalBook()
    with patch("hermes_cli.model_catalog.get_catalog", return_value={}):
        assert run_registry_update(book) == []
    assert not book.pending()


def test_run_registry_update_proposes_on_drift(tmp_path):
    local_yaml = tmp_path / "model-catalog.yaml"
    local_yaml.write_text(
        "version: 1\nproviders:\n  openrouter:\n    models:\n      - id: keep\n",
        encoding="utf-8",
    )
    remote = _catalog({"openrouter": {"models": [{"id": "keep"}, {"id": "brand-new"}]}})
    book = ProposalBook()
    with patch("hermes_cli.model_catalog.get_catalog", return_value=remote):
        proposals = run_registry_update(book, catalog_path=local_yaml)
    assert len(proposals) == 1
    assert "brand-new" in proposals[0].diff_intent
    assert proposals[0].status == ProposalStatus.NEEDS_OWNER_APPROVAL


def test_load_local_catalog_failopen(tmp_path):
    assert load_local_catalog(tmp_path / "does-not-exist.yaml") == {}


def test_render_deltas_readable():
    assert "in sync" in render_deltas([])
    out = render_deltas([RegistryDelta(provider="p", added_ids=("x",))])
    assert "REG-1" in out and "p:" in out and "risk=RC3" in out


# -- CLI handler (hermetic, no network) -------------------------------------


def test_cli_registry_update_persists_to_store(tmp_path, monkeypatch, capsys):
    import argparse

    from hermes_cli.jarvis_prime.__main__ import (
        _cmd_registry_update,
        _load_proposals,
        _proposals_store_path,
    )

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    remote = _catalog({"openrouter": {"models": [{"id": "brand-new"}]}})
    # Repo catalog is loaded from the real config; force a known small one.
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.registry_updater.load_local_catalog",
        lambda *a, **k: _catalog({"openrouter": {"models": [{"id": "old"}]}}),
    )
    with patch("hermes_cli.model_catalog.get_catalog", return_value=remote):
        ns = argparse.Namespace(check=False, no_refresh=False, json=False)
        rc = _cmd_registry_update(ns)
    assert rc == 0
    items = _load_proposals(_proposals_store_path())
    assert any(p["kind"] == "model_registry_update" for p in items)
    out = capsys.readouterr().out
    assert "queued" in out


def test_cli_registry_update_check_is_dry_run(tmp_path, monkeypatch, capsys):
    import argparse

    from hermes_cli.jarvis_prime.__main__ import _cmd_registry_update, _proposals_store_path

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    remote = _catalog({"openrouter": {"models": [{"id": "brand-new"}]}})
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.registry_updater.load_local_catalog",
        lambda *a, **k: _catalog({"openrouter": {"models": [{"id": "old"}]}}),
    )
    with patch("hermes_cli.model_catalog.get_catalog", return_value=remote):
        ns = argparse.Namespace(check=True, no_refresh=False, json=False)
        rc = _cmd_registry_update(ns)
    assert rc == 0
    # --check must not write the store.
    assert not _proposals_store_path().exists()
