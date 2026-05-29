# TokenJuice — Context Compiler

Status: **shipped**. File: `hermes_cli/jarvis_prime/tokenjuice.py`. Tests:
`tests/test_jarvis_prime_tokenjuice.py`.

A deterministic compiler that packs task-relevant material into an
ordered, token-bounded prompt packet.

## Inputs
mission, work packet, Memory Tree store (+ query/namespaces), research
artifacts, explicit repo snippets `(path, text)`.

## Output
`CompiledContext` with ordered `ContextSection`s (kinds: `mission`,
`packet`, `memory`, `research`, `repo`), `used_tokens`, and a `dropped`
list naming sections that did not fit.

## Guarantees
- Hard token budget: sections are **dropped whole**, never truncated
  mid-source, once the budget is exhausted.
- Provenance: memory/research/repo sections carry their source URIs/paths.
- Stale/contested memory deprioritized (it relies on `MemoryTreeStore`
  ranking, which penalizes stale and excludes contested by default).
- Secrets are re-screened with the Memory Tree secret detector and
  redacted before inclusion.
- Deterministic ordering (priority desc, then kind, then title) → stable,
  testable output for identical input.

## Usage
```python
from hermes_cli.jarvis_prime.tokenjuice import TokenJuiceCompiler
ctx = TokenJuiceCompiler().compile(
    "add memory tree support", token_budget=4000,
    work_packet=packet, memory_store=store, memory_query="memory tree",
    research_artifacts=[...], repo_snippets=[("path.py", "...")],
)
print(ctx.render())
```

## Owner gates / rollback / risks
- Owner gates: none.
- Rollback: additive module; revert branch.
- Risk: token estimate is a ~4-chars/token heuristic, not a tokenizer;
  budgets should keep headroom for the target model's real tokenizer.
