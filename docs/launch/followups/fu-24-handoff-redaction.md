# FU-24: Redact graph-derived citations/titles in context handoff

- **Status:** in-review
- **Risk class:** additive (defence-in-depth hardening)
- **Branch:** `claude/fu-24-handoff-redaction` · **Base:** `main` @ `e1ac6eed`
- **PR:** #377 (draft)
- **Owner-gate required to merge?** no — strictly additive screening; default
  packet schema and clean-graph output are byte-for-byte unchanged.

## Intent (one paragraph)

`hermes_cli/jarvis_prime/context_handoff.py` advertises secret-screening, but
before this change only the echoed `request` was run through
`secrets_policy.redact`. Graph-derived strings — node titles/refs (`_node_view`),
citation URIs/kinds (`answer.citations`), the `related_items` decision
titles/refs, and the `architecture_summary` lines — flowed into the packet
**unredacted**. That's low risk today (the graph indexes repo/docs), but it's an
assumption, not a guarantee. After this change every graph-derived string is
screened on the way *into* the packet using the existing never-raises `_redact`
wrapper, so a credential that somehow reached the index can't ride out via a
title, ref, citation, or community summary. For secret-free content (the normal
case) screening is a no-op: the rendered packet and `to_dict()` are unchanged.

## Owned files (the ONLY files this task may write)

- `hermes_cli/jarvis_prime/context_handoff.py`
- `tests/test_context_handoff.py`
- `docs/launch/followups/fu-24-handoff-redaction.md` (this snapshot)

> Disjoint from every other in-flight task. No shared files discovered.

## Plan (bounded steps)

1. Add `_redact_citation(citation)` — a never-raises helper that screens the
   string values of a citation dict (preserving shape and non-string fields;
   non-dict input returned unchanged).
2. Screen `_node_view` `title`/`ref` via `_redact` (covers `relevant_files`,
   `related_tests`, `graph_nodes`, and decision-type nodes).
3. Screen the `related_items` decision `title`/`ref`, the `answer.citations`
   list (via `_redact_citation`), and each composed `architecture_summary`
   line.
4. Keep the public API + packet schema, the never-raises contract, and the
   token-bounded `render()` clamp intact; test detection still runs on the raw
   node path (not the redacted view).
5. Tests: plant a `ghp_…`-shaped secret in a node title/ref, a citation URI, a
   decision, and a community top-title; assert it's redacted in the rendered
   packet and `to_dict()`; assert clean-graph round-trip is unchanged; assert
   never-raises on malformed node/citation/broken-query input.

## Validation

- `uv run ruff check hermes_cli/jarvis_prime/context_handoff.py tests/test_context_handoff.py` → **All checks passed**
- `uv run ty check hermes_cli/jarvis_prime/context_handoff.py tests/test_context_handoff.py` → **All checks passed** (no new diagnostics vs base)
- `python -m pytest tests/test_context_handoff.py -o addopts="" -q` → **14 passed**

## Residual / follow-on

- The redactor (`secrets_policy.redact`) only fires on word-boundary-anchored
  prefixes and high-entropy tokens; a secret concatenated mid-identifier with
  no boundary (e.g. `foo_ghp_…`) is not detected. That's the redactor's
  contract, not the handoff's — widening it is out of scope here. Tests plant
  secrets where a real leaked credential would actually sit (its own path
  segment / whitespace-delimited token).
- Citation field redaction screens all string values; if citation dicts ever
  carry deeply nested structures, those would need recursive screening — not
  the case today (flat `kind`/`uri`/`line_ref` dicts).
