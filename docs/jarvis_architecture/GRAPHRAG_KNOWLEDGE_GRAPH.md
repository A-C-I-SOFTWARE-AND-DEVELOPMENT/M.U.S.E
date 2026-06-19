# muse — GraphRAG Knowledge Graph

A typed, source-backed knowledge graph over the muse **cognition
plane**. It *supplements* — never replaces — the Memory Tree, the Research
Vault, and the HyperAgent navigation substrates. Its job is to unify those
existing stores into one inspectable graph with three retrieval modes, so
that **coding tasks reuse existing implementations instead of duplicating
them**.

Everything here is deterministic, stdlib-only, local-first, and Termux-safe.
No embeddings, no network, no LLM in the graph itself.

## Where it lives

`hermes_cli/jarvis_prime/graphrag/`

| Module | Responsibility |
|---|---|
| `graph.py` | `NodeType` / `EdgeType` vocabulary, `KnowledgeGraph` (neighbors, communities, subgraph), provenance on every node + edge |
| `store.py` | `GraphStore` — JSON cache at `~/.hermes/jarvis_prime/graph/graph.json` (atomic write, `0o600`) |
| `indexers/` | `code`, `docs`, `evidence`, `memory`, `ledger` — each read-only over its source |
| `builder.py` | `build_graph` / `build_and_save` / `load_or_build` (deterministic order, best-effort) |
| `query.py` | `local_query`, `global_query`, `coding_query`, `related_items`, `GraphAnswer` |

## Schema

**Node types** — `file`, `module`, `function`, `class`, `screen`, `api`,
`route`, `worker`, `model`, `document`, `source`, `task`, `decision`.

**Edge types** — `calls`, `imports`, `owns`, `routes_to`, `tests`,
`verifies`, `cites`, `contradicts`, `supersedes`, `blocks`, `depends_on`.

Each `Node`/`Edge` carries `sources` — provenance pointers back to the repo
path, ledger entry, memory node, or research artifact it was derived from.
Nothing is invented; genuinely-absent values stay empty.

## Indexers (reuse, don't duplicate)

- **code** — wraps the existing `navigation.RepoIndex` / `SymbolGraph`: FILE,
  FUNCTION, CLASS, MODULE, SCREEN (`*Screen.kt`), API/ROUTE (cockpit route
  tables) nodes; `imports` / `depends_on` / `tests` / `calls` / `owns` /
  `routes_to` edges. Import/test resolution uses a single inverted index
  (linear, not O(files²)); `calls` resolves only unambiguous direct calls.
- **docs** — DOCUMENT nodes; `cites` edges to files a doc references.
- **evidence** — `ResearchVault` artifacts → SOURCE nodes + `cites` edges
  (evidence strength → edge weight).
- **memory** — `MemoryTreeStore` nodes → DECISION nodes; `cites` to their
  provenance, `supersedes` + `contradicts` from the contradiction graph.
  Only title + a short summary are copied — never raw text/secrets.
- **ledger** — orchestrator job ledger + decision ledger → TASK / WORKER /
  MODEL / DECISION nodes; `depends_on` / `verifies` / `owns` / `cites` edges.

## Query modes

- `local` — answer from the nodes nearest the question (seed by term overlap,
  expand one hop).
- `global` — summarize the relevant communities (deterministic label
  propagation), with per-cluster top nodes and edge-type counts.
- `coding` — seed code nodes, then pull their tests, the docs/sources that
  cite them, and prior decisions — the context a coding task needs to avoid
  re-implementing something that exists.

Every answer is a `GraphAnswer`: ranked nodes, the edges among them, and the
de-duplicated source citations. `render()` produces an inspectable summary.

## Entry points

- **CLI** — `python -m hermes_cli.jarvis_prime graph build|query|related`
  (`--mode local|global|coding`, `--indexers code,docs,…`).
- **Agent tool** — `graph_query` (in the core toolset): the agent consults
  the graph before writing code (reuse-before-duplicate). Read-only.
- **Cockpit REST** — `GET /v1/cockpit/graph/related`, `GET …/graph/query`,
  `POST …/graph/build` (see `docs/android/hermes-apk-api-contract.md` §10d).
- **Android** — a "Related in knowledge graph" panel on the Task (job),
  Audit, and Memory screens, plus a dedicated **Knowledge graph** screen
  (Settings → Knowledge graph) for ad-hoc local/global/coding queries.

## Guarantees

- **Supplements, not replaces.** The Memory Tree / Research Vault / navigation
  modules are read-only inputs. Existing RAG and memory tools are untouched.
- **Inspectable + source-backed.** Every node/edge cites where it came from.
- **Safe to delete.** The graph is an additive cache; removing
  `~/.hermes/jarvis_prime/graph/` is a complete rollback. `build` is
  read-only over the repo + local stores and is not owner-gated.
- **Owner gates preserved.** No new irreversible/external action is
  introduced; the graph never writes back to its sources.

## Scale

A full build over the Hermes repo takes well under a minute and produces
~33.5k nodes / ~63.3k edges across all node/edge types (measured 2026-06-10;
see the attestation below for the exact counts and command). The build is
on-demand and cached; queries read the cache. Earlier revisions of this doc
and the README quoted ~28.6k nodes / ~51.6k edges from a prior tree state;
those figures are superseded by the attestation.

## Attestation (2026-06-10)

Reproducible graph-size measurement against the current tree (ticket
**P1-02**, `docs/synapse/phase0/P1_CLAIMS_AUDIT.md` claim C12).

- **Commit:** `10b144c3cc32346c94f52ac24d2f1e41b851db3b` (`git rev-parse HEAD`)
- **Environment:** system Python 3.11.15, Linux; `HERMES_HOME` pointed at a
  fresh temp dir so the build wrote nowhere near `~/.hermes` and the
  evidence/memory/ledger indexers saw empty local stores — i.e. the counts
  below are the **repo-only** (code + docs) graph, which is exactly what the
  "over the repo" claim covers.
- **Command:**

  ```bash
  HERMES_HOME=$(mktemp -d) python -m hermes_cli.jarvis_prime graph build \
      --repo-root . --json
  ```

- **Result (run 1, wall time 42.8s):**

  ```json
  {
    "nodes": 33483,
    "edges": 63304,
    "by_node_type": {
      "api": 1, "class": 5920, "document": 2052, "file": 6024,
      "function": 19182, "module": 176, "route": 93, "screen": 35
    },
    "by_edge_type": {
      "calls": 5000, "cites": 3778, "depends_on": 10803, "imports": 10803,
      "owns": 27599, "routes_to": 93, "tests": 5228
    }
  }
  ```

- **Result (run 2, wall time 38.1s):** 33,483 nodes / 63,307 edges — node
  count and every edge type identical except `cites` (3,781 vs 3,778), a
  ±3-edge nondeterminism in citation extraction.
- **Measured figures:** **33,483 nodes / ~63.3k edges** (63,304–63,307
  across two runs). No LLM, embedding, or network calls were required; the
  build is pure-local and completed in under a minute both times.
