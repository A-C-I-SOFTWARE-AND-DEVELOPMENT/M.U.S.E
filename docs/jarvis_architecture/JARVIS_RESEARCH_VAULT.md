# JARVIS Research Vault

Status: **shipped**. File: `hermes_cli/jarvis_prime/research_vault.py`.
Tests: `tests/test_jarvis_prime_research_vault.py`.

A first-class evidence store for papers, official docs, OSS practices,
model benchmark notes, courses, and skill proposals.

## Records
- `ResearchArtifact` — id, title, source URI, `SourceType`,
  `EvidenceStrength`, excerpt, summary, tags, freshness due, added_at.
- Cards: `ModelBenchmarkCard`, `OSSPracticeCard`, `CourseArtifactCard`,
  `SkillProposalCard`.

## Behavior
- `add(...)` summarizes **only** from the stored excerpt or an explicit
  summary — it never invents a summary.
- Source type + evidence strength recorded; vendor benchmarks use
  `EvidenceStrength.VENDOR_REPORTED` and map to `SourceTrust.UNVERIFIED`.
- `as_memory_source()` bridges an artifact into a Memory Tree provenance
  pointer, so durable memory can cite the vault.
- `export_audit_cards()` / `export_markdown()` for review.
- Local JSONL persistence, atomic writes, malformed-line tolerance, **no
  network** (tests never hit the network).

## Constraints
- Does **not** download copyrighted or private materials. The caller
  supplies the excerpt/citation text.

## CLI
```bash
python -m hermes_cli.jarvis_prime research add --title "vLLM" --uri https://docs.vllm.ai --source-type official_doc --strength primary --excerpt "..." --store PATH
python -m hermes_cli.jarvis_prime research list --json --store PATH
python -m hermes_cli.jarvis_prime research export-markdown --store PATH
```

## Owner gates / rollback / risks
- Owner gates: none.
- Rollback: additive module; revert branch.
- Risk: evidence strength is owner/operator-asserted, not auto-verified.

## See also
- [JARVIS Research Mode (the Evidence Engine)](../jarvis_research/JARVIS_RESEARCH_MODE.md)
  — the pipeline that gathers, ranks, and writes evidence into this vault, and
  exposes it on the Android Research screen.
