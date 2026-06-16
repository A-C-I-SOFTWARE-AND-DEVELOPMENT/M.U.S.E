"""Tests for the MUSE System Contract — doc<->code sync and MUSE branding.

These mirror the Constitution's doc-sync guard: the spec
(``docs/muse-system-contract.md``) and the code mirror
(``hermes_cli/jarvis_prime/system_contract.py``) must agree, and the contract
must be branded to MUSE — it must never adopt a foreign assistant's identity.
"""

from __future__ import annotations

import re

from hermes_cli.jarvis_prime import system_contract as sc


def test_validate_is_clean():
    # The contract's own self-check must pass with no problems.
    assert sc.validate() == []


def test_version_recorded_in_doc():
    doc = sc.load_doc()
    assert f"System Contract **v{sc.CONTRACT_VERSION}**" in doc


def test_every_section_has_matching_doc_header():
    doc = sc.load_doc()
    for s in sc.sections():
        assert f"## {s.id} — {s.title}" in doc, f"missing doc header for {s.id}"


def test_no_doc_section_without_code_mirror():
    doc = sc.load_doc()
    doc_ids = set(re.findall(r"^## (SC\d+) ", doc, flags=re.MULTILINE))
    assert doc_ids == set(sc.section_ids())


def test_section_ids_unique_and_in_order():
    ids = sc.section_ids()
    assert len(ids) == len(set(ids)), "duplicate section id"
    nums = [int(i[2:]) for i in ids]
    assert nums == sorted(nums), "section ids out of order"
    assert nums == list(range(1, len(nums) + 1)), "section ids must be contiguous SC1..SCn"


def test_preamble_is_compact_and_complete():
    preamble = sc.render_preamble()
    assert preamble.startswith(f"# MUSE System Contract v{sc.CONTRACT_VERSION}")
    # Every section is represented in the digest.
    for s in sc.sections():
        assert s.id in preamble and s.title in preamble
    # Compact: the digest is far smaller than the full doc.
    assert len(preamble) < len(sc.render())


def test_branding_is_muse_not_a_foreign_assistant():
    # MUSE identity is present...
    assert "MUSE" in sc.render()
    assert "muse" in sc.render_preamble().lower()
    # ...and no foreign-assistant *identity* claim leaks in (naming a backing
    # model as the engine is fine; claiming to BE it is not).
    blob = (sc.render() + "\n" + sc.render_preamble()).lower()
    for marker in sc._FOREIGN_IDENTITY_MARKERS:
        assert marker not in blob, f"foreign-identity leak: {marker!r}"


def test_live_injection_is_opt_in_and_owner_gated():
    # Default off (injecting the contract changes default runtime behavior).
    assert sc.is_enabled({}) is False
    assert sc.is_enabled({sc.CONTRACT_ENV_FLAG: "1"}) is True
    assert sc.is_enabled({sc.CONTRACT_ENV_FLAG: "true"}) is True
    assert sc.is_enabled({sc.CONTRACT_ENV_FLAG: "0"}) is False
