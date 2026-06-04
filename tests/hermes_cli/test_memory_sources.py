"""Tests for MCP knowledge-source ingestion into memory (fake MCP caller)."""

from __future__ import annotations

import json

from hermes_cli.jarvis_prime import memory_sources as ms
from plugins.memory.holographic.store import MemoryStore


def _fake_caller(result):
    calls = {}

    def caller(tool_name, args):
        calls["tool"] = tool_name
        calls["args"] = args
        return result

    caller.calls = calls
    return caller


def test_available_sources_includes_expected():
    names = ms.available_sources()
    for expected in ("gmail", "gdrive", "notion", "slack", "pubmed", "icd10", "era"):
        assert expected in names


def test_disabled_source_refuses(tmp_path):
    report = ms.ingest(
        "pubmed", "senescence", apply=False, config={}, tool_caller=_fake_caller([])
    )
    assert report.fetched == 0
    assert any("disabled" in e for e in report.errors)


def test_unknown_source():
    report = ms.ingest("nope", "x", config={"nope": {"enabled": True}})
    assert any("unknown source" in e for e in report.errors)


def test_dry_run_maps_results_with_provenance():
    result = {
        "articles": [
            {"title": "Cellular senescence", "abstract": "A review of senescence.", "url": "https://pubmed/1"},
            {"title": "Telomeres", "summary": "Telomere attrition.", "id": "PMID:2"},
        ]
    }
    cfg = {"pubmed": {"enabled": True}}
    report = ms.ingest("pubmed", "longevity", apply=False, config=cfg, tool_caller=_fake_caller(result))
    assert report.dry_run is True
    assert report.fetched == 2
    assert report.written == 0
    c0 = report.candidates[0]
    assert "Cellular senescence" in c0.content
    assert c0.source_uri == "https://pubmed/1"
    assert "source:pubmed" in c0.tags
    assert "trust:primary" in c0.tags
    assert c0.importance >= 0.9  # primary source


def test_personal_source_is_redacted():
    result = {"threads": [{"subject": "key", "snippet": "my key is sk-ABCDEF123456 ok"}]}
    cfg = {"gmail": {"enabled": True}}
    report = ms.ingest("gmail", "secrets", apply=False, config=cfg, tool_caller=_fake_caller(result))
    assert report.candidates
    assert "sk-ABCDEF123456" not in report.candidates[0].content


def test_apply_writes_to_store(tmp_path):
    result = {"results": [{"title": "Deploy runbook", "text": "Run make deploy to ship."}]}
    cfg = {"notion": {"enabled": True}}
    store = MemoryStore(db_path=tmp_path / "m.db")
    try:
        report = ms.ingest(
            "notion", "deploy", apply=True, config=cfg,
            tool_caller=_fake_caller(result), store=store,
        )
        assert report.written == 1
        rows = store.list_facts(min_trust=0.0)
        assert any("make deploy" in r["content"] for r in rows)
        # Re-ingest is idempotent (dedup by content): no duplicate facts.
        report2 = ms.ingest(
            "notion", "deploy", apply=True, config=cfg,
            tool_caller=_fake_caller(result), store=store,
        )
        assert report2.written == 1  # add_fact returns existing id, still counted
        assert len(store.list_facts(min_trust=0.0)) == len(rows)
    finally:
        store.close()


def test_string_json_result_is_parsed():
    raw = json.dumps({"files": [{"name": "notes.md", "snippet": "meeting notes"}]})
    cfg = {"gdrive": {"enabled": True}}
    report = ms.ingest("gdrive", "notes", apply=False, config=cfg, tool_caller=_fake_caller(raw))
    assert report.fetched == 1
    assert "meeting notes" in report.candidates[0].content


def test_tool_call_failure_is_reported():
    def boom(tool, args):
        raise RuntimeError("server down")

    report = ms.ingest("pubmed", "x", config={"pubmed": {"enabled": True}}, tool_caller=boom)
    assert any("tool call failed" in e for e in report.errors)
