# Snapshot — g-graphrag-parity (FU-20, GraphRAG arm)

**Grain:** Bring GraphRAG `global_query` to citation/ranking parity with the
other query modes (`local_query` / `coding_query`).

**Branch:** `claude/g-graphrag-parity`
**Base commit:** `ba2c12dfd0ff005f8f0a36f5adbaac96edff681d` (`origin/main`)
**Status:** in-review (DRAFT PR — not merged)

## Intent

`local_query` and `coding_query` hand back a `GraphAnswer` whose `nodes` are
ranked by a single deterministic contract — relevance score (`_score_node`)
first, node id second — with de-duplicated, source-backed citations collected
over exactly that node + edge set (`_collect_citations`).

`global_query` was the parity laggard: it already collected citations and was
deterministic across runs, but its surfaced `nodes` were ordered by
community-block-then-intra-cluster-degree, so the `nodes` field did **not**
match the ranking contract the other two modes expose. Verified empirically on
the baseline: `global` node order != the `(-_score_node, id)` order the other
modes produce.

## Change (additive parity, no behavior break)

`hermes_cli/jarvis_prime/graphrag/query.py` — in `global_query`, after the
per-community summaries are built, re-rank the assembled `shown_nodes` by the
**same** key `local_query`/`coding_query` use:

```python
shown_nodes.sort(key=lambda n: (-_score_node(n, terms), n.id))
```

- Reuses the existing `_score_node` helper — **no** duplicated ranking logic.
- Citations still flow through the shared `_collect_citations(shown_nodes, edges)`.
- The per-community degree sort that *selects* the top-6 representatives is
  untouched; this only fixes their final, cross-cluster order.
- `community` summaries (global's unique contribution), signature, never-raises
  contract, and offline/in-memory operation (no network, no model) all
  preserved. One-line diff in the function body + an explanatory comment.

## Owned files

- `hermes_cli/jarvis_prime/graphrag/query.py` (modified — 1 logic line + comment)
- `tests/jarvis_prime/graphrag/test_query_parity.py` (new)
- `tests/jarvis_prime/__init__.py`, `tests/jarvis_prime/graphrag/__init__.py`
  (new — empty package markers required to make the grain-mandated nested test
  path discoverable under the repo's packaged `tests/` root; no behavior)
- `docs/launch/followups/g-graphrag-parity.md` (this snapshot)

No other files touched. Did **not** edit `docs/launch/10_10_followups_ledger.md`.

## Tests

`tests/jarvis_prime/graphrag/test_query_parity.py` builds a small in-memory
`KnowledgeGraph` (two source-backed clusters) and asserts:

- `global_query` populates citations (source-backed uri+kind).
- Those citations equal `_collect_citations(ans.nodes, ans.edges)` — same
  collection behavior as the other modes.
- `global_query.nodes` are ordered by the `local_query` ranking key.
- Stable order/edges/citations/communities across two runs.
- All three modes (`local` / `coding` / `global`) satisfy the one ranking
  contract.
- Communities + full `GraphAnswer` shape preserved.
- Never-raises on an empty graph and on an empty/stopword-only question.

## Validation (local)

- `uv run ruff check hermes_cli/jarvis_prime/graphrag/query.py tests/jarvis_prime/graphrag/test_query_parity.py`
  → **All checks passed!**
- `uv run --extra dev ty check hermes_cli/jarvis_prime/graphrag/query.py tests/jarvis_prime/graphrag/test_query_parity.py`
  → **All checks passed!** (baseline `query.py` @ origin/main also clean — zero
  new diagnostics; no pytest false-positive to exempt)
- `python -m pytest tests/jarvis_prime/graphrag/test_query_parity.py tests/test_graphrag_query.py tests/test_graphrag_graph.py -o addopts="" -q`
  → **23 passed** (8 new + 15 existing graphrag query/graph tests — no regression)
- `python -m pytest tests/test_graphrag_indexers.py -o addopts="" -q`
  → **6 passed** (extra regression guard; indexers import `query`)

## Residual risk

Low. Strictly additive: the only behavior change is the *final ordering* of
`global_query.nodes`, which now matches the other modes (citations, communities,
edges, signature, never-raises all unchanged). No new dependency; stdlib-only;
deterministic; offline. Behavior-affecting (node order changes), so PR opened as
**DRAFT** and left for owner review per the merge-gating contract — not
auto-merged.
